"""
api_v2.py - Day 3 part 2: the new FastAPI backend (replaces the old api.py; api.py is untouched).

Start (from the repo root):
    python -m uvicorn api_v2:app --port 8001
Interactive docs: http://127.0.0.1:8001/docs

All data is loaded ONCE at startup from data/processed (species, sources, purpose scores, site points, site_scores).
Palette and matching come from pipeline/palettes.py, pipeline/matching.py and pipeline/run_plan.py (not re-implemented here).
Every value shown carries its source id, URL and rank where one exists (resolved from species_sources); inputs that come from a
file rather than a cited source (site elevation, slope, soil code) say which file.
"""
import dataclasses, json, math, re, sqlite3, sys, unicodedata
from collections import OrderedDict
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, Optional

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "pipeline"))
import advisory as adv  # noqa: E402
import field_verify as fv  # noqa: E402
import field_kit as fk  # noqa: E402
import matching as mt  # noqa: E402
import palettes as pal  # noqa: E402
import run_plan as rp  # noqa: E402
import score_sites as ss  # noqa: E402

# =====================================================================================================================
# CONFIG - every tunable number lives here. PROVISIONAL unless stated.
# =====================================================================================================================
API_CFG = {
    "data_dir": "data/processed",
    "barangay_shp": "data/BRGY_BOUNDARY.shp",
    "port": 8001,                                   # python -m uvicorn api_v2:app --port 8001 (the old api.py uses another port)
    "cors_origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
    "nearest_point_max_m": 150.0,                   # /rank: the nearest grid point must be this close to the coordinate
    "ring_step_m": 100.0,                           # /nearest-viable: width of each search ring
    "ring_max_m": 5000.0,                           # /nearest-viable: give up beyond this distance
    "plan_min_saplings": 1,
    "plan_max_saplings": 2000,
    "default_seed": 42,                             # POST /plan-event when no seed is given
    "polygon_max_vertices": 5000,                   # larger polygons are rejected
    "rank_default_limit": 10,                       # /rank: species returned (max = all species)
    "municipal_default_limit": 15,                  # /rank/municipal: species returned
    "search_max_results": 20,
    "place_aliases": {"sta": "santa", "sto": "santo"},
    "site_crs": mt.CFG["site_crs"],
    "kits_dir": "kits",                             # <work>/kits (field kits built by POST /plans/{id}/field-kit)
    "cache_dir": "cache",                           # <work>/cache (forecast cache, git-ignored)
    "plans_list_default_limit": 20,                 # GET /plans
    "plans_list_max_limit": 100,
    "plan_id_max_len": 100,                         # plan ids are letters, digits, underscore, hyphen only
    "advisory_area_margin_deg": 0.1,                # /advisory/seasonal: the coordinate must be this close (degrees) to the mapped grid
    "boundary_simplify_deg": 0.00005,               # /geo/boundaries: first simplification tolerance (degrees, ~5 m)
    "boundary_simplify_max_deg": 0.002,             # ... never simplify beyond this (~200 m)
    "boundary_max_bytes": 300_000,                  # /geo/boundaries: the tolerance grows until the response is under this size
    "coord_decimals": 5,                            # coordinates in /geo/boundaries and /grid (5 decimals ~ 1 m)
    "grid_w_decimals": 3,                           # W in /grid
    "grid_max_bytes": 250_000,                      # /grid should stay under this size (checked by the tests)
    "missing_marker": -1,                           # /grid: the explicit "no value" marker (never null)
    "grid_cache_seconds": 300,                      # Cache-Control max-age of /geo/boundaries and /grid
    "landuse_shp": "data/LandUses.shp",             # /geo/zones
    "zone_max_bytes": 300_000,                      # /geo/zones: the tolerance grows until the response is under this size
    "multi_cache_max": 48,                          # /grid with species_ids: how many different selections stay cached in memory
    "areas_cache_max": 64,                          # /areas/rank: how many different requests stay cached in memory
    "area_mix_saplings": 100,                       # POST /rank/area: saplings the suggested mix is worked out for (shares barely depend on it)
    "field_db": "data/field/field_checks.db",       # saved field checks (append-only events, git-ignored)
    "field_exclude_not_plantable": True,            # THE SWITCH: points whose latest field check is not_plantable are left out of rankings and plans
    "field_list_default_limit": 100,                # GET /field-checks
    "field_list_max_limit": 1000,
}
LIMITS = [
    "Soil pH is not scored (there is no real pH layer); rainfall, temperature, canopy and exposure are not scored either.",
    "Slope comes from ~100 m grid cells (finite differences); about 22% of cells have a one-axis slope that may under-estimate it.",
    "The soil texture mapping is a legacy mapping and is UNVERIFIED; by default a texture mismatch only lowers the score and is flagged soil_unverified_mismatch.",
    "All weights, caps, thresholds and purpose scores are PROVISIONAL until the agriculturist signs off.",
    "Suitability S comes from rules written from the species dataset, not from field survival data.",
    "Each point is a ~100 m grid cell, so a plan places at most one tree per cell.",
    "Species data marked species_data_unverified cites a source file that was not provided.",
    "Scores are not valid outside the mapped municipality of San Mateo, Rizal.",
    "Field checks (verified plantable / not plantable / needs recheck) carry a name only: there is no login yet, and anyone with access to the dashboard can add one.",
    "While the field-check switch is on, points whose latest check is 'not plantable' are left out of rankings and plans; 'verified plantable' only adds a badge and never changes a score.",
]
FIELD_LIMITS = LIMITS[-2:]
# =====================================================================================================================

Purpose = Literal["urban", "planting", "watershed"]
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def py(v):
    """JSON-safe Python value (numpy scalars -> Python, NaN/NA -> None)."""
    if v is None or v is pd.NA:
        return None
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if math.isnan(v) else float(v)
    return v


def norm_text(s):
    """Lower case, accents removed, punctuation -> spaces."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s.lower())).strip()


def norm_place(s, aliases):
    return " ".join(aliases.get(t, t) for t in norm_text(s).split())


def compass(de, dn):
    return COMPASS[int(((math.degrees(math.atan2(de, dn)) + 22.5) % 360) // 45)]


# ---------------------------------------------------------------------------------------------------------------------
# startup
# ---------------------------------------------------------------------------------------------------------------------
def display_name(name, aliases):
    """'STA ANA' -> 'Santa Ana': the place-search aliases (Sta -> Santa, Sto -> Santo), accents removed, Title Case, roman numerals kept."""
    words = [aliases.get(t, t) for t in norm_text(name).split()]
    return " ".join(w.upper() if re.fullmatch(r"[ivx]+", w) else w.capitalize() for w in words)


def round_coords(c, nd):
    if isinstance(c, (list, tuple)):
        if c and isinstance(c[0], (int, float)):
            return [round(float(x), nd) for x in c]
        return [round_coords(x, nd) for x in c]
    return c


def _bbox_outward(bounds, nd):
    f = 10 ** nd
    return [math.floor(bounds[0] * f) / f, math.floor(bounds[1] * f) / f, math.ceil(bounds[2] * f) / f, math.ceil(bounds[3] * f) / f]


def build_boundaries(gs, names, display, point_barangay, cfg):
    """
    GeoJSON FeatureCollection: feature 'municipality' = union of the barangay polygons, then one feature per barangay (sorted by name).
    The barangays are simplified together (shared edges stay shared) with a tolerance that grows until the JSON is under boundary_max_bytes.
    Returns (json bytes, info dict).
    """
    import shapely
    from shapely.geometry import mapping
    import geopandas as gpd
    nd = cfg["coord_decimals"]
    geoms = gs.geometry.values
    union_full = shapely.union_all(geoms)
    area_km2 = float(gpd.GeoSeries([union_full], crs=gs.crs).to_crs(cfg["site_crs"]).area.iloc[0] / 1e6)
    counts = np.bincount(point_barangay[point_barangay >= 0], minlength=len(names))
    tol = cfg["boundary_simplify_deg"]
    while True:
        try:
            simp = shapely.coverage_simplify(geoms, tol, simplify_boundary=True)
        except Exception:                                                  # not a clean coverage: simplify each polygon on its own
            simp = np.array([shapely.simplify(g_, tol, preserve_topology=True) for g_ in geoms], dtype=object)
        outline = shapely.union_all(simp)
        bbox = _bbox_outward(outline.bounds, nd)
        feats = [{"type": "Feature", "id": "municipality",
                  "properties": {"kind": "municipality", "name": "San Mateo", "display_name": "San Mateo", "bbox": bbox, "area_km2": round(area_km2, 1)},
                  "geometry": {"type": mapping(outline)["type"], "coordinates": round_coords(mapping(outline)["coordinates"], nd)}}]
        for i, g_ in enumerate(simp):
            lp = shapely.point_on_surface(g_)
            m = mapping(g_)
            feats.append({"type": "Feature", "id": f"brgy-{i}",
                          "properties": {"kind": "barangay", "name": names[i], "display_name": display[i], "key": norm_place(names[i], cfg["place_aliases"]),
                                         "label_point": {"lon": round(lp.x, nd), "lat": round(lp.y, nd)}, "bbox": _bbox_outward(g_.bounds, nd),
                                         "legal_grid_points": int(counts[i])},
                          "geometry": {"type": m["type"], "coordinates": round_coords(m["coordinates"], nd)}})
        doc = {"type": "FeatureCollection", "bbox": bbox, "features": feats, "crs": "EPSG:4326 (longitude, latitude)",
               "source": "data/BRGY_BOUNDARY.shp (BRGY_NAME); the municipal outline is the union of the barangay polygons",
               "simplify_tolerance_deg": tol, "coordinate_decimals": nd,
               "name_rule": "display_name: Sta -> Santa, Sto -> Santo, accents removed, Title Case (same aliases as /search/place); name is as written in the shapefile",
               "points_outside_every_barangay": int((point_barangay < 0).sum())}
        body = json.dumps(doc, separators=(",", ":")).encode("utf-8")
        if len(body) <= cfg["boundary_max_bytes"] or tol >= cfg["boundary_simplify_max_deg"]:
            return body, {"bytes": len(body), "tolerance_deg": tol, "bbox": bbox, "area_km2": round(area_km2, 1)}
        tol = min(tol * 1.5, cfg["boundary_simplify_max_deg"])


def lru_get(cache, key):
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    return None


def lru_put(cache, key, value, max_entries):
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > max_entries:
        cache.popitem(last=False)


def _grid_doc(d, purpose, w, best, n_el, species_id, species_ids, mode, w_def, best_meaning, n_scope):
    ctx, cfg = d.ctx, d.cfg
    miss = cfg["missing_marker"]
    nd = cfg["coord_decimals"]
    if d.ex_mask.any():                                                # points marked not plantable in the field: W = 0, no best species
        w, best, n_el = np.where(d.ex_mask, 0.0, w), np.where(d.ex_mask, miss, best), np.where(d.ex_mask, 0, np.asarray(n_el))
    doc = {"purpose": purpose, "species_id": species_id, "species_ids": species_ids, "mode": mode, "n": int(len(ctx.sites)),
           "w_definition": w_def, "best_species_meaning": best_meaning, "n_eligible_scope": n_scope,
           "columns": {"point_id": ctx.sites.point_id.astype(int).tolist(), "lon": np.round(ctx.sites.lon.to_numpy(), nd).tolist(),
                       "lat": np.round(ctx.sites.lat.to_numpy(), nd).tolist(), "W": np.round(w, cfg["grid_w_decimals"]).tolist(),
                       "best_species_id": best.astype(int).tolist(), "n_eligible_species": np.asarray(n_el).astype(int).tolist(),
                       "barangay": d.point_barangay.tolist()},
           "barangays": d.barangay_names, "barangays_display": d.barangay_display,
           "missing": {"marker": miss,
                       "columns": {"species_id": f"{miss} = no single species was chosen (none, or several: see species_ids)",
                                   "best_species_id": f"{miss} = no suitable species at this point (W is then 0)",
                                   "barangay": f"{miss} = the point lies outside every barangay polygon"},
                       "note": "No column contains null. W = 0 means 'not suitable here', it is not a missing value. barangay is an index into barangays (and barangays_display)."},
           "rounding": {"lon_lat_decimals": nd, "W_decimals": cfg["grid_w_decimals"]}}
    if field_active(d):
        doc["field"] = field_block(d)
    return json.dumps(doc, separators=(",", ":")).encode("utf-8")


def grid_body(d, purpose, species_id=None):
    """JSON bytes of /grid for a purpose (best species at each legal point) or a purpose + ONE species (that species only). Cached in memory."""
    key = (purpose, species_id)
    if key in d.grid_cache:
        return d.grid_cache[key]
    ctx, cfg = d.ctx, d.cfg
    miss = cfg["missing_marker"]
    W, feas = mt.weights(ctx.S, ctx.P[purpose])
    ids = ctx.species.species_id.to_numpy(dtype=int)
    if species_id is None:
        k = W.argmax(axis=1)
        w = W[np.arange(len(W)), k]
        best = np.where(w > 0, ids[k], miss)
        body = _grid_doc(d, purpose, w, best, feas.sum(axis=1), miss, [], "best",
                         "W = S x P if S >= 0.50 else 0. Per point: the best W over all species", "the species with the highest W at the point",
                         "all species")
    else:
        w = W[:, d.species_idx[species_id]]
        best = np.where(w > 0, species_id, miss)
        body = _grid_doc(d, purpose, w, best, feas.sum(axis=1), species_id, [species_id], "single",
                         f"W = S x P if S >= 0.50 else 0, for species {species_id} only", "the chosen species (when W > 0)", "all species")
    d.grid_cache[key] = body
    return body


def parse_species_ids(d, raw):
    """'1,2,3' -> [1, 2, 3] (sorted, no duplicates). An empty list is a 422, an unknown id a 404, text that is not numbers a 422."""
    toks = [t.strip() for t in str(raw).split(",") if t.strip() != ""]
    if not toks:
        raise HTTPException(422, "species_ids must list at least one species id, for example species_ids=1,2,3")
    try:
        ids = sorted({int(t) for t in toks})
    except ValueError:
        raise HTTPException(422, f"species_ids must be whole numbers separated by commas, got '{raw}'")
    unknown = [i for i in ids if i not in d.species_idx]
    if unknown:
        raise HTTPException(404, f"species_id {unknown} not found (valid ids: {int(d.ctx.species.species_id.min())}-{int(d.ctx.species.species_id.max())})")
    return ids


def combined_scores(d, purpose, ids, mode):
    """
    Score of every legal point for a set of species. W_k = S x P if S >= 0.50 else 0 for each selected species k.
      mode 'all': W = the lowest W_k, and 0 unless EVERY selected species has S >= 0.50 (best = the limiting species, the lowest W_k);
      mode 'any': W = the highest W_k (best = that species).
    Returns (W, best species id or the missing marker, number of selected species suitable at the point).
    """
    ctx = d.ctx
    ks = [d.species_idx[i] for i in ids]
    Wk, feas = mt.weights(ctx.S[:, ks], ctx.P[purpose][ks])
    arr = np.array(ids)
    if mode == "all":
        j = Wk.argmin(axis=1)
        w = np.where(feas.all(axis=1), Wk.min(axis=1), 0.0)
    else:
        j = Wk.argmax(axis=1)
        w = Wk.max(axis=1)
    best = np.where(w > 0, arr[j], d.cfg["missing_marker"])
    n_sel = feas.sum(axis=1)
    if d.ex_mask.any():
        w, best, n_sel = np.where(d.ex_mask, 0.0, w), np.where(d.ex_mask, d.cfg["missing_marker"], best), np.where(d.ex_mask, 0, n_sel)
    return w, best, n_sel


def grid_body_multi(d, purpose, ids, mode):
    key = (purpose, tuple(ids), mode)
    hit = lru_get(d.multi_cache, key)
    if hit is not None:
        return hit
    w, best, n_sel = combined_scores(d, purpose, ids, mode)
    rule = ("W is the LOWEST W over the selected species, and 0 unless every selected species has S >= 0.50" if mode == "all"
            else "W is the HIGHEST W over the selected species")
    body = _grid_doc(d, purpose, w, best, n_sel, d.cfg["missing_marker"], ids, mode,
                     f"Per species W = S x P if S >= 0.50 else 0. Mode {mode}: {rule}",
                     "the limiting species (lowest W)" if mode == "all" else "the selected species with the highest W",
                     "selected species (how many of the selected species are suitable at the point)")
    lru_put(d.multi_cache, key, body, d.cfg["multi_cache_max"])
    return body


def area_tables(d, by):
    """(index of the area of every legal point or the marker, names, display names, bboxes) for by = 'barangay' or 'zone'."""
    if by == "barangay":
        return d.point_barangay, d.barangay_names, d.barangay_display, d.barangay_bbox
    return d.point_zone, d.zone_names, d.zone_names, d.zone_bbox


def areas_rank_body(d, purpose, ids, mode, by):
    """Ranked table of barangays or zones for the selected species: mean W over ALL legal points of the area (0 where not suitable)."""
    key = (purpose, tuple(ids), mode, by)
    hit = lru_get(d.areas_cache, key)
    if hit is not None:
        return hit
    miss = d.cfg["missing_marker"]
    w, _, _ = combined_scores(d, purpose, ids, mode)
    idx, names, disp, bbox = area_tables(d, by)
    ok = (idx >= 0) & ~d.ex_mask                                       # points marked not plantable are not candidate land
    n = len(names)
    ex_cnt = np.bincount(idx[(idx >= 0) & d.ex_mask], minlength=n)
    cnt = np.bincount(idx[ok], minlength=n)
    sw = np.bincount(idx[ok], weights=w[ok], minlength=n)
    su = np.bincount(idx[ok], weights=(w[ok] > 0).astype(float), minlength=n)
    rows = []
    for i in range(n):
        if cnt[i] == 0:
            continue
        suit = int(su[i])
        rows.append({"name": names[i], "display_name": disp[i], "legal_points": int(cnt[i]), "mean_W": round(float(sw[i] / cnt[i]), 3),
                     "mean_W_where_suitable": round(float(sw[i] / suit), 3) if suit else miss, "share_suitable": round(suit / int(cnt[i]), 4),
                     "suitable_points": suit, "bbox": bbox[i],
                     **({"not_plantable_points": int(ex_cnt[i])} if field_active(d) else {})})
    rows.sort(key=lambda r: (-r["mean_W"], -r["share_suitable"], r["name"]))
    for k, r in enumerate(rows, 1):
        r["rank"] = k
    doc = {"purpose": purpose, "species_ids": ids, "mode": mode, "by": by, "n_areas": len(rows), "legal_points": int(ok.sum()), "areas": rows,
           "score_definition": ("Per point: mode all = the lowest W over the selected species, and 0 unless every selected species has S >= 0.50; "
                                "mode any = the highest W. mean_W = the average of that score over ALL legal points of the area (0 where not suitable); "
                                "share_suitable = suitable points / legal points."),
           "missing": {"marker": miss, "columns": {"mean_W_where_suitable": f"{miss} = no suitable point in the area"},
                       "note": "No value is null. mean_W = 0 means 'nowhere suitable'."}}
    body = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    lru_put(d.areas_cache, key, body, d.cfg["areas_cache_max"])
    return body


def polys_only(geom):
    import shapely
    from shapely.geometry import MultiPolygon
    parts = [p for p in shapely.get_parts(geom) if p.geom_type == "Polygon" and not p.is_empty]
    parts = [q for p in parts for q in ([p] if p.geom_type == "Polygon" else [])]
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def build_zones(d, cfg):
    """GeoJSON of the legal land-use zones (dissolved by name from data/LandUses.shp), simplified to stay under zone_max_bytes."""
    import shapely
    import geopandas as gpd
    from shapely.geometry import mapping
    nd = cfg["coord_decimals"]
    lu = gpd.read_file(ROOT / cfg["landuse_shp"])
    lu = lu[lu.DESCRIPTIO.isin(d.zone_names) & lu.geometry.notna()].copy()
    lu["geometry"] = lu.geometry.map(shapely.make_valid)
    full = [polys_only(shapely.union_all(lu[lu.DESCRIPTIO == n].geometry.values)) for n in d.zone_names]
    counts = np.bincount(d.point_zone[d.point_zone >= 0], minlength=len(d.zone_names))
    tol = cfg["boundary_simplify_deg"]
    while True:
        feats, bboxes = [], []
        for i, g_ in enumerate(full):
            s_ = shapely.simplify(g_, tol, preserve_topology=True)
            s_ = s_ if not s_.is_empty else g_
            m = mapping(s_)
            bb = _bbox_outward(s_.bounds, nd)
            bboxes.append(bb)
            lp = shapely.point_on_surface(s_)
            feats.append({"type": "Feature", "id": f"zone-{i}",
                          "properties": {"kind": "zone", "name": d.zone_names[i], "display_name": d.zone_names[i], "bbox": bb,
                                         "label_point": {"lon": round(lp.x, nd), "lat": round(lp.y, nd)}, "legal_grid_points": int(counts[i])},
                          "geometry": {"type": m["type"], "coordinates": round_coords(m["coordinates"], nd)}})
        doc = {"type": "FeatureCollection", "features": feats, "crs": "EPSG:4326 (longitude, latitude)",
               "source": "data/LandUses.shp (DESCRIPTIO), dissolved by zone name; only the zones that contain legal grid points",
               "simplify_tolerance_deg": tol, "coordinate_decimals": nd,
               "note": "Zone names are written exactly as in the land-use layer (including the LGU spelling 'General Institutional Zonec')."}
        body = json.dumps(doc, separators=(",", ":")).encode("utf-8")
        if len(body) <= cfg["zone_max_bytes"] or tol >= cfg["boundary_simplify_max_deg"]:
            return body, bboxes
        tol = min(tol * 1.5, cfg["boundary_simplify_max_deg"])


def find_barangay(d, text):
    """Index of a barangay from its name as written, its display name or an alias spelling (Sta -> Santa, accents ignored); None if unknown."""
    key = norm_place(text, d.cfg["place_aliases"])
    return d.barangay_keys.index(key) if key and key in d.barangay_keys else None


def resolve_area(d, req):
    """(boolean mask over the legal points, info dict) for the ONE area of a POST /rank/area request."""
    given = [k for k in ("polygon", "barangay", "zone") if getattr(req, k) is not None]
    if len(given) != 1:
        raise HTTPException(422, "Give exactly one area: polygon (GeoJSON), barangay (name) or zone (name)" + (f"; got {', '.join(given)}" if given else "; got none"))
    sites = d.ctx.sites
    if req.barangay is not None:
        b = find_barangay(d, req.barangay)
        if b is None:
            raise HTTPException(400, f"Unknown barangay '{req.barangay}'. Barangays: {', '.join(d.barangay_display)}")
        return d.point_barangay == b, {"type": "barangay", "name": d.barangay_names[b], "display_name": d.barangay_display[b], "bbox": d.barangay_bbox[b]}
    if req.zone is not None:
        z = [n.strip().lower() for n in d.zone_names].index(req.zone.strip().lower()) if req.zone.strip().lower() in [n.strip().lower() for n in d.zone_names] else None
        if z is None:
            raise HTTPException(400, f"Unknown zone '{req.zone}'. Zones: {', '.join(d.zone_names)}")
        return d.point_zone == z, {"type": "zone", "name": d.zone_names[z], "display_name": d.zone_names[z], "bbox": d.zone_bbox[z]}
    mask = polygon_mask(sites, req.polygon, d.cfg["polygon_max_vertices"])
    if not mask.any():
        raise HTTPException(400, "The area contains no legal-zone grid points (it may lie outside San Mateo or only cover non-planting zones).")
    nd = d.cfg["coord_decimals"]
    sel = sites[mask]
    return mask, {"type": "polygon", "name": "Drawn area", "display_name": "Drawn area",
                  "bbox": [round(float(sel.lon.min()), nd), round(float(sel.lat.min()), nd), round(float(sel.lon.max()), nd), round(float(sel.lat.max()), nd)]}


def area_mean_confidence(d, point_ids):
    """{species_id: mean site confidence over the given points} from the scores database (empty if only a csv is available)."""
    if not d.is_db:
        return {}
    ids = [int(x) for x in point_ids]
    sums, cnts = {}, {}
    con = sqlite3.connect(d.ctx.scores_path)
    for i in range(0, len(ids), 900):
        chunk = ids[i:i + 900]
        q = f"SELECT species_id, SUM(confidence), COUNT(*) FROM site_scores WHERE point_id IN ({','.join('?' * len(chunk))}) GROUP BY species_id"
        for sid, s_, c_ in con.execute(q, chunk):
            sums[sid] = sums.get(sid, 0.0) + s_
            cnts[sid] = cnts.get(sid, 0) + c_
    con.close()
    return {sid: sums[sid] / cnts[sid] for sid in sums}


def refresh_field(d):
    """
    Re-read the saved field checks and rebuild everything that depends on them: the current status of every point, the mask of points that are
    left out (not_plantable, when the switch is on) and the cached grids / area tables (they are rebuilt on the next request).
    """
    cur = fv.current_status(d.field_db)
    d.field_current = cur
    d.field_ex_ids = fv.excluded_ids(cur) if d.cfg["field_exclude_not_plantable"] else set()
    d.ex_mask = d.ctx.sites.point_id.isin(d.field_ex_ids).to_numpy() if d.field_ex_ids else np.zeros(len(d.ctx.sites), dtype=bool)
    d.field_n_events = fv.n_events(d.field_db)
    for cache in (d.grid_cache, d.multi_cache, d.areas_cache):
        cache.clear()


def field_active(d):
    return d.field_n_events > 0


def barangay_display_of(d, point_id):
    i = d.point_index.get(int(point_id))
    if i is None or d.point_barangay[i] < 0:
        return None
    return d.barangay_display[d.point_barangay[i]]


def field_view(d, point_id):
    """The current field status of a point as shown by the API (None if the point has never been checked)."""
    c = d.field_current.get(int(point_id))
    if c is None:
        return None
    i = d.point_index.get(int(point_id))
    return {**c, "barangay": barangay_display_of(d, point_id), "left_out_of_rankings": int(point_id) in d.field_ex_ids,
            "lon": py(d.ctx.sites.lon.iloc[i]) if i is not None else None, "lat": py(d.ctx.sites.lat.iloc[i]) if i is not None else None}


def field_extra(d, point_id):
    v = field_view(d, point_id)
    return {} if v is None else {"field_check": v}


def field_block(d):
    """The compact list of field-checked points of /grid: positions in the column arrays and a status code per position (only checked points)."""
    items = sorted((d.point_index[pid], fv.status_code(c)) for pid, c in d.field_current.items() if pid in d.point_index)
    return {"index": [i for i, _ in items], "status": [s for _, s in items],
            "codes": {"1": "verified_plantable", "2": "not_plantable", "3": "needs_recheck", "+4": "disputed: the latest two checks come from different observers and disagree"},
            "left_out_of_rankings": sorted(d.field_ex_ids), "exclude_switch": bool(d.cfg["field_exclude_not_plantable"]),
            "note": "Points with status 2 have W = 0 and best_species_id = the missing marker while the switch is on. verified (1) never changes a score."}


def field_flags_for_plan(d, plan):
    """Add field_verified / field_needs_recheck / field_disputed to the flags of planned points that have a field check (no score changes)."""
    if plan.empty or not d.field_current:
        return plan
    plan = plan.copy()
    out = []
    for pid, fl in zip(plan.point_id.astype(int), plan["flags"].fillna("").astype(str)):
        c = d.field_current.get(pid)
        extra = []
        if c is not None:
            extra.append({"verified_plantable": "field_verified", "needs_recheck": "field_needs_recheck", "not_plantable": "field_not_plantable"}[c["status"]])
            if c["disputed"]:
                extra.append("field_disputed")
        out.append(";".join(x for x in (fl.split(";") if fl else []) + extra if x))
    plan["flags"] = out
    return plan


def load_data(cfg=None):
    cfg = API_CFG if cfg is None else cfg
    root = ROOT / cfg["data_dir"]
    ctx = mt.load_context(root)
    sources = pd.read_csv(root / "species_sources.csv")
    refs = pd.read_csv(root / "species_references.csv")
    ps = pd.read_csv(root / "purpose_scores.csv")
    all_points = pd.read_csv(root / "site_points_clean.csv")
    d = SimpleNamespace(cfg=cfg, root=root, work=root, ctx=ctx, sources=sources, refs=refs, purpose_scores=ps, all_points=all_points)
    d.tree_all = cKDTree(all_points[["utm_e", "utm_n"]].to_numpy(dtype=float))
    d.tree_legal = cKDTree(ctx.sites[["utm_e", "utm_n"]].to_numpy(dtype=float))
    d.legal_index = {int(p): i for i, p in enumerate(ctx.sites.point_id)}
    d.src_by_id = {int(r.source_id): r for r in sources.itertuples(index=False)}
    d.src_by_sf = {(int(r.species_id), r.field_name): int(r.source_id) for r in sources.itertuples(index=False)}
    d.species_idx = {int(s): i for i, s in enumerate(ctx.species.species_id)}
    d.ps_by_key = {(int(r.species_id), r.purpose): r for r in ps.itertuples(index=False)}
    from pyproj import Transformer
    d.to_utm = Transformer.from_crs("EPSG:4326", cfg["site_crs"], always_xy=True)
    d.to_wgs = Transformer.from_crs(cfg["site_crs"], "EPSG:4326", always_xy=True)
    # dataset version, and the mean site confidence per species, from the databases
    con = sqlite3.connect(root / "optimizing_survival.db")
    v = pd.read_sql_query("SELECT * FROM dataset_versions ORDER BY dataset_version_id DESC LIMIT 1", con)
    con.close()
    d.dataset = {k: py(x) for k, x in v.iloc[0].to_dict().items()} if len(v) else {}
    d.is_db = ctx.scores_path.suffix == ".db"
    if d.is_db:
        con = sqlite3.connect(ctx.scores_path)
        mc = pd.read_sql_query("SELECT species_id, AVG(confidence) AS c FROM site_scores GROUP BY species_id", con)
        con.close()
        d.mean_conf = dict(zip(mc.species_id.astype(int), mc.c))
    else:
        d.mean_conf = {}
    # municipal ranking per purpose (cheap, computed once)
    d.municipal = {}
    for purpose in mt.PURPOSES:
        st = pal.species_stats(ctx.S, ctx.P[purpose], mt.CFG["s_min"])
        st.insert(0, "species_id", ctx.species.species_id.to_numpy())
        d.municipal[purpose] = st.sort_values(["score", "species_id"], ascending=[False, True]).reset_index(drop=True)
    # barangays
    import geopandas as gpd
    g = gpd.read_file(ROOT / cfg["barangay_shp"])
    proj = g.to_crs(cfg["site_crs"])
    cen = proj.centroid.to_crs("EPSG:4326")
    d.places = [{"name": str(r.BRGY_NAME), "key": norm_place(r.BRGY_NAME, cfg["place_aliases"]),
                 "centroid": {"lon": round(float(cen.iloc[i].x), 6), "lat": round(float(cen.iloc[i].y), 6)},
                 "bounds": [round(float(x), 6) for x in r.geometry.bounds]} for i, r in enumerate(g.itertuples(index=False))]
    # barangay outlines and the barangay of every legal point (computed once; /geo/boundaries and /grid are served from memory)
    gs = g.sort_values("BRGY_NAME").reset_index(drop=True)
    d.barangay_names = [str(n) for n in gs.BRGY_NAME]
    d.barangay_display = [display_name(n, cfg["place_aliases"]) for n in d.barangay_names]
    pts = gpd.GeoDataFrame({"i": np.arange(len(ctx.sites))}, geometry=gpd.points_from_xy(ctx.sites.lon, ctx.sites.lat), crs=gs.crs)
    joined = gpd.sjoin(pts, gs[["geometry"]].reset_index().rename(columns={"index": "b"}), how="left", predicate="intersects")
    joined = joined.drop_duplicates("i", keep="first").set_index("i").b.reindex(range(len(ctx.sites)))
    d.point_barangay = joined.fillna(cfg["missing_marker"]).astype(int).to_numpy()
    d.boundaries_body, d.boundaries_info = build_boundaries(gs, d.barangay_names, d.barangay_display, d.point_barangay, cfg)
    d.barangay_keys = [norm_place(n, cfg["place_aliases"]) for n in d.barangay_names]
    d.barangay_bbox = [f["properties"]["bbox"] for f in json.loads(d.boundaries_body)["features"][1:]]
    d.zone_names = sorted(str(z) for z in ctx.sites.zone_desc.dropna().unique())
    d.point_zone = pd.Categorical(ctx.sites.zone_desc, categories=d.zone_names).codes.astype(int)
    d.zones_body, d.zone_bbox = build_zones(d, cfg)
    d.grid_cache = {}
    d.multi_cache = OrderedDict()
    d.areas_cache = OrderedDict()
    from shapely.geometry import shape as _shape
    d.muni_geom = _shape(json.loads(d.boundaries_body)["features"][0]["geometry"]).buffer(fv.CFG["municipality_buffer_deg"])
    d.point_index = d.legal_index
    d.field_db = ROOT / cfg["field_db"]
    fv.connect(d.field_db).close()                                    # creates data/field/ and the table on the first start
    refresh_field(d)
    for purpose in mt.PURPOSES:
        grid_body(d, purpose, None)
    return d


@asynccontextmanager
async def lifespan(app):
    app.state.data = load_data()
    yield


app = FastAPI(title="San Mateo Optimizing Survival API (v2)", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=API_CFG["cors_origins"], allow_credentials=False,
                   allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])


def D(request: Request):
    return request.app.state.data


# ---------------------------------------------------------------------------------------------------------------------
# helpers: sources
# ---------------------------------------------------------------------------------------------------------------------
def source(d, sid):
    r = d.src_by_id.get(int(sid))
    if r is None:
        return {"source_id": int(sid), "field": None, "url": None, "rank": None}
    return {"source_id": int(sid), "field": r.field_name, "url": py(r.source_url), "rank": py(r.source_rank),
            "rank_basis": py(r.rank_basis), "off_list": py(r.off_list), "flags": py(r.flags)}


def sources_map(d, ids):
    return {str(i): source(d, i) for i in sorted({int(x) for x in ids})}


def species_field_ids(d, species_id, fields):
    return [d.src_by_sf[(species_id, f)] for f in fields if (species_id, f) in d.src_by_sf]


def purpose_breakdown(d, species_id, purpose):
    r = d.ps_by_key[(species_id, purpose)]
    crit = json.loads(r.breakdown_json)
    out = {}
    for name, c in crit.items():
        out[name] = {"score": c["score"], "weight": c["weight"], "missing": c["missing"], "parts": c["parts"],
                     "sources": [source(d, i) for i in c["src"]], "other_inputs": c.get("ext", [])}
    return {"p_score": py(r.p_score), "rank_in_purpose": int(r.rank), "confidence": py(r.confidence), "n_missing": int(r.n_missing),
            "weights_status": r.weights_status, "criteria": out}


def purpose_source_ids(d, species_id, purpose):
    crit = json.loads(d.ps_by_key[(species_id, purpose)].breakdown_json)
    return sorted({i for c in crit.values() for i in c["src"]})


def pair_rows(d, point_id):
    """{species_id: (confidence, breakdown dict)} for one point from site_scores (database or csv)."""
    path = d.ctx.scores_path
    if d.is_db:
        con = sqlite3.connect(path)
        rows = con.execute("SELECT species_id, confidence, breakdown_json FROM site_scores WHERE point_id=?", (int(point_id),)).fetchall()
        con.close()
        return {int(s): (c, json.loads(b)) for s, c, b in rows}
    df = pd.read_csv(path, usecols=["point_id", "species_id", "confidence", "breakdown_json"])
    df = df[df.point_id == point_id]
    return {int(r.species_id): (r.confidence, json.loads(r.breakdown_json)) for r in df.itertuples(index=False)}


def flags_for(d, species_id, breakdown, conf):
    fl = list(breakdown.get("flags", [])) + [f"gate_failed:{g}" for g in breakdown.get("gate_failed", [])]
    fl += d.ctx.species_flags.get(species_id, [])
    if conf is not None and conf == conf and conf < rp.CFG["low_confidence_below"]:
        fl.append("low_confidence")
    return list(dict.fromkeys(fl))


# ---------------------------------------------------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------------------------------------------------
@app.get("/health")
def health(d=Depends(D)):
    ctx = d.ctx
    return {"status": "ok", "dataset_version": d.dataset.get("tag"), "dataset_file_hash": d.dataset.get("file_hash"),
            "dataset": d.dataset, "scores_file": str(ctx.scores_path.relative_to(ROOT)) if ctx.scores_path.is_relative_to(ROOT) else str(ctx.scores_path),
            "counts": {"species": len(ctx.species), "grid_points": len(d.all_points), "legal_points": len(ctx.sites),
                       "species_point_scores": int(ctx.S.size), "sources": len(d.sources), "barangays": len(d.places)},
            "purposes": list(mt.PURPOSES), "limits": LIMITS,
            "field_checks": {"events": d.field_n_events, "points_checked": len(d.field_current), "left_out_of_rankings": len(d.field_ex_ids),
                             "exclude_not_plantable": bool(d.cfg["field_exclude_not_plantable"])}}


KEY_FIELDS = {"common_name": "common_name", "scientific_name": "scientific_name", "elev_min_m": "elev_min_m", "elev_max_m": "elev_max_m",
              "max_slope_pct": "max_slope_pct", "origin": "category", "planting_months": "months_raw"}


@app.get("/species")
def species_list(d=Depends(D)):
    sp, items, ids = d.ctx.species, [], set()
    for r in sp.itertuples(index=False):
        sid = int(r.species_id)
        fid = {f: d.src_by_sf[(sid, s)] for f, s in KEY_FIELDS.items() if (sid, s) in d.src_by_sf}
        ids |= set(fid.values())
        items.append({"species_id": sid, "common_name": r.common_name, "scientific_name": r.scientific_name, "genus": py(r.genus),
                      "origin": py(r.origin), "elev_min_m": py(r.elev_min_m), "elev_max_m": py(r.elev_max_m),
                      "max_slope_pct": py(r.max_slope_pct), "planting_months": py(r.planting_months), "is_dioecious": py(r.is_dioecious),
                      "confidence": {"share_of_cells_with_rank1_or_2_source": py(r.confidence_r12), "cells_cited": py(r.n_cells_cited),
                                     "cells_rank1_or_2": py(r.n_cells_rank12)},
                      "purpose_scores": {p: {"p_score": py(d.ps_by_key[(sid, p)].p_score), "confidence": py(d.ps_by_key[(sid, p)].confidence)}
                                         for p in mt.PURPOSES},
                      "flags": d.ctx.species_flags.get(sid, []), "source_ids": fid})
    return {"count": len(items), "species": items, "sources": sources_map(d, ids),
            "note": "GET /species/{species_id} lists every field with its source URL and rank"}


@app.get("/species/{species_id}")
def species_detail(species_id: int, d=Depends(D)):
    i = d.species_idx.get(species_id)
    if i is None:
        raise HTTPException(404, f"species_id {species_id} not found (valid ids: {int(d.ctx.species.species_id.min())}-{int(d.ctx.species.species_id.max())})")
    row = d.ctx.species.iloc[i]
    rows = d.sources[d.sources.species_id == species_id]
    fields = [{"field_name": r.field_name, "value_as_written": py(r.value_text), "source_id": int(r.source_id), "source_url": py(r.source_url),
               "source_rank": py(r.source_rank), "rank_basis": py(r.rank_basis), "off_list": py(r.off_list), "flags": py(r.flags)}
              for r in rows.itertuples(index=False)]
    return {"species_id": species_id, "common_name": row.common_name, "scientific_name": row.scientific_name,
            "confidence": {"share_of_cells_with_rank1_or_2_source": py(row.confidence_r12), "cells_cited": py(row.n_cells_cited),
                           "cells_rank1_or_2": py(row.n_cells_rank12)},
            "flags": d.ctx.species_flags.get(species_id, []),
            "fields": fields, "clean_values": {k: py(v) for k, v in row.items()},
            "provisional_note": "root_urban_safety_prov and root_soil_binding_prov are provisional scores from tag_maps_root.csv, not sourced facts; "
                                "is_high_value_crop is a team decision",
            "reference_urls": d.refs[d.refs.species_id == species_id].reference_url.tolist(),
            "purpose_scores": {p: purpose_breakdown(d, species_id, p) for p in mt.PURPOSES}}


@app.get("/rank")
def rank(purpose: Purpose, lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180),
         limit: int = Query(API_CFG["rank_default_limit"], ge=1, le=100), d=Depends(D)):
    e, n = d.to_utm.transform(lon, lat)
    dist, i = d.tree_all.query([e, n])
    if dist > d.cfg["nearest_point_max_m"]:
        raise HTTPException(404, f"The nearest grid point is {dist:.0f} m away (limit {d.cfg['nearest_point_max_m']:.0f} m): "
                                 "the coordinate is outside the mapped area of San Mateo.")
    pt = d.all_points.iloc[int(i)]
    if not bool(pt.is_legal_zone):
        zone = py(pt.zone_desc) or "outside the zoning map"
        raise HTTPException(404, f"The nearest grid point (id {int(pt.point_id)}, {dist:.0f} m away) is not in a legal planting zone ({zone}); no ranking is given.")
    j = d.legal_index[int(pt.point_id)]
    if d.ex_mask[j]:
        c = d.field_current[int(pt.point_id)]
        raise HTTPException(404, f"This point (id {int(pt.point_id)}) was marked not plantable in the field ({c['reason']}) by {c['observer']} on {c['observed_at'][:10]}"
                                 f"{': ' + c['note'] if c['note'] else ''}. It is left out of the ranking. Its history: GET /field-checks/{int(pt.point_id)}.")
    S_row, P = d.ctx.S[j], d.ctx.P[purpose]
    W, feas = mt.weights(S_row[None, :], P)
    pairs = pair_rows(d, pt.point_id)
    items = []
    for k, sid in enumerate(d.ctx.species.species_id.astype(int)):
        conf, bd = pairs.get(sid, (None, {}))
        items.append((bool(feas[0, k]), float(W[0, k]), float(S_row[k]), k, sid, conf, bd))
    items.sort(key=lambda t: (not t[0], -t[1], -t[2], t[4]))
    out, ids = [], set()
    for rnk, (el, w, s, k, sid, conf, bd) in enumerate(items[:limit], 1):
        terms = {t: {"value": v["value"], "weight": v["weight"], "sources": [source(d, x) for x in v["src"]]} for t, v in bd.get("terms", {}).items()}
        out.append({"rank": rnk, "species_id": sid, "common_name": d.ctx.species.common_name.iloc[k], "S": round(s, 4), "P": round(float(P[k]), 4),
                    "W": round(w, 4), "eligible": el, "confidence": py(conf), "flags": flags_for(d, sid, bd, conf),
                    "site_breakdown": {"gate_failed": bd.get("gate_failed", []), "terms": terms},
                    "purpose_breakdown": purpose_breakdown(d, sid, purpose)})
    return {"purpose": purpose, "query": {"lat": lat, "lon": lon},
            "point": {"point_id": int(pt.point_id), "lon": py(pt.lon), "lat": py(pt.lat), "utm_e": py(pt.utm_e), "utm_n": py(pt.utm_n),
                      "distance_m": round(float(dist), 1), "zone": py(pt.zone_desc), "elev_m": py(pt.elev_m), "slope_pct": py(pt.slope_pct),
                      "slope_method": py(pt.slope_method), "soil_texture_legacy": py(pt.soil_texture_legacy),
                      "soil_mapping_status": py(pt.soil_mapping_status),
                      "site_inputs_source": "backend/Working_Points.csv (elevation, soil code); slope by finite differences on elevation; soil texture = legacy mapping (unverified)"},
            "species_eligible": int(sum(t[0] for t in items)), "species_total": len(items), "returned": len(out), "ranking": out,
            "limits": LIMITS, "w_definition": "W = S x P if S >= 0.50 else 0", **field_extra(d, int(pt.point_id))}


@app.get("/rank/municipal")
def rank_municipal(purpose: Purpose, limit: int = Query(API_CFG["municipal_default_limit"], ge=1, le=100), d=Depends(D)):
    st = d.municipal[purpose].head(limit)
    ctx, items, ids = d.ctx, [], set()
    for rnk, r in enumerate(st.itertuples(index=False), 1):
        sid = int(r.species_id)
        s_ids = species_field_ids(d, sid, [f for fs in ss.TERM_FIELDS.values() for f in fs])
        p_ids = purpose_source_ids(d, sid, purpose)
        ids |= set(s_ids) | set(p_ids)
        k = d.species_idx[sid]
        items.append({"rank": rnk, "species_id": sid, "common_name": ctx.species.common_name.iloc[k], "species_score": round(float(r.score), 4),
                      "mean_W_where_eligible": round(float(r.mean_w), 4), "eligible_points": int(r.n_eligible),
                      "share_of_points_eligible": round(float(r.eligible_share), 4), "P": round(float(ctx.P[purpose][k]), 4),
                      "p_confidence": py(d.ps_by_key[(sid, purpose)].confidence), "mean_site_confidence": py(d.mean_conf.get(sid)),
                      "flags": ctx.species_flags.get(sid, []), "source_ids": {"site_score": s_ids, "purpose_score": p_ids}})
    return {"purpose": purpose, "legal_points": len(ctx.sites), "species_total": len(ctx.species), "returned": len(items),
            "score_definition": "species_score = mean W over points where S >= 0.50, times the share of points where S >= 0.50",
            "ranking": items, "sources": sources_map(d, ids), "limits": LIMITS}


@app.get("/search/species")
def search_species(q: str = Query(min_length=1), d=Depends(D)):
    needle = norm_text(q)
    if not needle:
        raise HTTPException(422, "q must contain letters or digits")
    out = []
    for r in d.ctx.species.itertuples(index=False):
        hit = [f for f, v in (("common_name", r.common_name), ("scientific_name", r.scientific_name)) if needle in norm_text(v)]
        if hit:
            sid = int(r.species_id)
            out.append({"species_id": sid, "common_name": r.common_name, "scientific_name": r.scientific_name, "matched_on": hit,
                        "source_ids": species_field_ids(d, sid, ["common_name", "scientific_name"]), "url": f"/species/{sid}"})
    out = out[:d.cfg["search_max_results"]]
    ids = {i for o in out for i in o["source_ids"]}
    return {"query": q, "count": len(out), "results": out, "sources": sources_map(d, ids)}


@app.get("/search/place")
def search_place(q: str = Query(min_length=1), d=Depends(D)):
    key = norm_place(q, d.cfg["place_aliases"])
    if not key:
        raise HTTPException(422, "q must contain letters or digits")
    out = [{"name": p["name"], "centroid": p["centroid"], "bounds": p["bounds"],
            "bounds_order": "minlon,minlat,maxlon,maxlat", "source": "data/BRGY_BOUNDARY.shp (BRGY_NAME)"}
           for p in d.places if key in p["key"]]
    return {"query": q, "normalised_query": key, "count": len(out), "results": out[:d.cfg["search_max_results"]],
            "note": "Sta -> Santa, Sto -> Santo; accents and punctuation are ignored"}


@app.get("/nearest-viable")
def nearest_viable(purpose: Purpose, lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180), d=Depends(D)):
    ctx, cfg = d.ctx, d.cfg
    e, n = d.to_utm.transform(lon, lat)
    W, feas = mt.weights(ctx.S, ctx.P[purpose])
    viable = feas.any(axis=1) & ~d.ex_mask                          # a point marked not plantable is never offered

    def best(j):
        k = int(np.argmax(np.where(feas[j], W[j], -1.0)))
        sid = int(ctx.species.species_id.iloc[k])
        return {"species_id": sid, "common_name": ctx.species.common_name.iloc[k], "S": round(float(ctx.S[j, k]), 4),
                "P": round(float(ctx.P[purpose][k]), 4), "W": round(float(W[j, k]), 4),
                "source_ids": {"site_score": species_field_ids(d, sid, [f for fs in ss.TERM_FIELDS.values() for f in fs]),
                               "purpose_score": purpose_source_ids(d, sid, purpose)}}

    def point(j, dist, ring, already):
        r = ctx.sites.iloc[j]
        b = best(j)
        ids = set(b["source_ids"]["site_score"]) | set(b["source_ids"]["purpose_score"])
        return {"purpose": purpose, "query": {"lat": lat, "lon": lon}, "already_viable": already, "search_ring": ring,
                "ring_step_m": cfg["ring_step_m"], "distance_m": round(float(dist), 1),
                "direction": None if already else compass(r.utm_e - e, r.utm_n - n),
                "point": {"point_id": int(r.point_id), "lon": py(r.lon), "lat": py(r.lat), "utm_e": py(r.utm_e), "utm_n": py(r.utm_n), "zone": py(r.zone_desc)},
                "best_species": b, "sources": sources_map(d, ids), "limits": LIMITS}

    dist, i = d.tree_all.query([e, n])
    if dist <= cfg["nearest_point_max_m"]:                           # the spot itself
        pid = int(d.all_points.point_id.iloc[int(i)])
        j = d.legal_index.get(pid)
        if j is not None and viable[j]:
            return point(j, dist, 0, True)
    dx = np.hypot(ctx.sites.utm_e.to_numpy() - e, ctx.sites.utm_n.to_numpy() - n)
    k = 1
    while (k - 1) * cfg["ring_step_m"] < cfg["ring_max_m"]:
        ring = (dx > (k - 1) * cfg["ring_step_m"]) & (dx <= k * cfg["ring_step_m"]) & viable
        if ring.any():
            j = int(np.where(ring)[0][np.argmin(dx[ring])])
            return point(j, dx[j], k, False)
        k += 1
    raise HTTPException(404, f"No point with an eligible species (S >= 0.50) was found within {cfg['ring_max_m']:.0f} m of this spot.")


class PlanRequest(BaseModel):
    purpose: Purpose
    n_saplings: int = Field(ge=API_CFG["plan_min_saplings"], le=API_CFG["plan_max_saplings"])
    polygon: Optional[dict] = Field(None, description="GeoJSON Polygon / MultiPolygon (or a Feature holding one), lon/lat")
    zone: Optional[str] = Field(None, description="zone_desc, e.g. 'Forest Zone'")
    seed: Optional[int] = None


def polygon_mask(sites, polygon, max_vertices):
    import shapely
    from shapely.geometry import shape
    geom = polygon.get("geometry") if polygon.get("type") == "Feature" else polygon
    try:
        g = shape(geom)
    except Exception:
        g = None
    if g is None or g.geom_type not in ("Polygon", "MultiPolygon") or g.is_empty or not g.is_valid or g.area <= 0:
        raise HTTPException(422, "polygon must be a valid, non-empty GeoJSON Polygon or MultiPolygon with lon/lat coordinates "
                                 "(closed rings, no self-intersections)")
    if len(shapely.get_coordinates(g)) > max_vertices:
        raise HTTPException(422, f"polygon has too many vertices (limit {max_vertices})")
    return shapely.contains_xy(g, sites.lon.to_numpy(), sites.lat.to_numpy())


def render_plan(d, plan, summary, plan_id=None, extra=None):
    """The JSON shown for a plan (a fresh one from POST /plan-event or a saved one from GET /plans/{id})."""
    purpose = summary["purpose"]
    ids, items = set(), []
    for r in plan.itertuples(index=False):
        s_ids = [int(x) for x in str(r.site_scores_src_ids).split(";") if x] if isinstance(r.site_scores_src_ids, str) else []
        ids |= set(s_ids)
        items.append({"point_id": int(r.point_id), "lon": py(r.lon), "lat": py(r.lat), "utm_e": py(r.utm_e), "utm_n": py(r.utm_n), "zone": py(r.zone_desc),
                      "species_id": int(r.species_id), "species": r.species, "S": py(r.S), "P": py(r.P), "W": py(r.W), "confidence": py(r.confidence),
                      "flags": [f for f in str(r.flags).split(";") if f] if isinstance(r.flags, str) else [], "site_scores_source_ids": s_ids})
    palette = []
    for p in summary["palette"]:
        p_ids = purpose_source_ids(d, p["species_id"], purpose)
        ids |= set(p_ids)
        palette.append({**p, "purpose_score_source_ids": p_ids})
    pal_by_name = {p["species"]: p for p in summary["palette"]}
    rest = {k: v for k, v in summary.items() if k not in ("palette", "limits")}
    out = {"plan_id": plan_id, "purpose": purpose, "n_saplings_requested": summary["n_saplings_requested"], "seed": summary.get("seed"),
           "palette": palette, "plan": items, "summary": rest,
           "unmatched": {"saplings_unmatched": summary["saplings_unmatched"], "saplings_unallocated_by_caps": summary["saplings_unallocated"],
                         "unused_candidate_points": summary["unused_candidate_points"],
                         "unmatched_by_species": {n: p["unmatched"] for n, p in pal_by_name.items() if p["unmatched"]}},
           "sources": sources_map(d, ids), "limits": list(dict.fromkeys(summary.get("limits", []) + LIMITS))}
    if extra:
        out.update(extra)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# saved plans: the plan CSV and its summary JSON live in <work>/plans exactly as pipeline/run_plan.py writes them
# ---------------------------------------------------------------------------------------------------------------------
PLAN_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


def valid_plan_id(plan_id, max_len=None):
    """Strict: letters, digits, underscore, hyphen only (no dots, slashes, drive letters, spaces, empty)."""
    n = API_CFG["plan_id_max_len"] if max_len is None else max_len
    return isinstance(plan_id, str) and 0 < len(plan_id) <= n and PLAN_ID_RE.fullmatch(plan_id) is not None


def check_plan_id(plan_id):
    if not valid_plan_id(plan_id):
        raise HTTPException(400, "Invalid plan_id: use only letters, digits, underscore and hyphen (for example plan_urban_20261005_021810).")


def plans_dir(d):
    return (d.work / rp.CFG["plans_dir"]).resolve()


def plan_files(d, plan_id):
    """(plan csv, summary json) of a saved plan; the path is built from the validated id only and must stay inside the plans folder."""
    check_plan_id(plan_id)
    root = plans_dir(d)
    csv, js = (root / f"{plan_id}.csv").resolve(), (root / f"{plan_id}_summary.json").resolve()
    if csv.parent != root or js.parent != root or not csv.is_file() or not js.is_file():
        raise HTTPException(404, f"Plan '{plan_id}' was not found. List the saved plans with GET /plans.")
    return csv, js


def kit_zip_path(d, plan_id):
    return (d.work / d.cfg["kits_dir"] / f"field_kit_{fk.safe_name(plan_id)}.zip").resolve()


def save_plan(d, purpose, plan, summary):
    base = datetime.now().strftime(rp.CFG["timestamp_format"])
    root = plans_dir(d)
    stamp, k = base, 1
    while (root / f"plan_{purpose}_{stamp}.csv").exists():             # two plans in the same second never overwrite each other
        k += 1
        stamp = f"{base}-{k}"
    f, sj = rp.write_plan(d.work, purpose, plan, summary, stamp)
    return f.stem, f, sj


@app.post("/plan-event")
def plan_event(req: PlanRequest, d=Depends(D)):
    ctx = d.ctx
    seed = d.cfg["default_seed"] if req.seed is None else req.seed
    if req.zone:
        zones = {z.strip().lower() for z in ctx.sites.zone_desc.dropna()}
        if req.zone.strip().lower() not in zones:
            raise HTTPException(400, f"Unknown zone '{req.zone}'. Legal zones: {sorted(ctx.sites.zone_desc.dropna().unique())}")
    sub = ctx
    if req.polygon is not None:
        m = polygon_mask(ctx.sites, req.polygon, d.cfg["polygon_max_vertices"])
        if not m.any():
            raise HTTPException(400, "The polygon contains no legal-zone grid points (it may lie outside San Mateo or only cover non-planting zones).")
        sub = dataclasses.replace(ctx, sites=ctx.sites[m].reset_index(drop=True), S=ctx.S[m])
    excluded_in_area = 0
    if d.field_ex_ids:                                                # points marked not plantable in the field are never planned
        gone = sub.sites.point_id.isin(d.field_ex_ids).to_numpy()
        in_zone = (sub.sites.zone_desc.fillna("").str.strip().str.lower() == req.zone.strip().lower()).to_numpy() if req.zone else np.ones(len(sub.sites), dtype=bool)
        excluded_in_area = int((gone & in_zone).sum())
        if gone.any():
            sub = dataclasses.replace(sub, sites=sub.sites[~gone].reset_index(drop=True), S=sub.S[~gone])
        if len(sub.sites) == 0:
            raise HTTPException(400, "Every planting point of this area is marked not plantable in the field, so no plan can be made.")
    try:
        plan, summary = rp.make_plan(sub, req.purpose, req.n_saplings, zone=req.zone, seed=seed)
    except ValueError as ex:
        raise HTTPException(400, f"{ex}" + (" (the zone has no legal points inside the polygon)" if req.zone and req.polygon is not None else ""))
    if not summary["palette"]:
        raise HTTPException(400, "No species has eligible points (S >= 0.50) in this area, so no plan can be made. "
                                 f"{' '.join(summary['palette_warnings'])}".strip())
    summary["field_checks"] = {"exclude_not_plantable": bool(d.cfg["field_exclude_not_plantable"]), "excluded_points": excluded_in_area,
                               "note": "Points whose latest field check is not_plantable were left out of this plan." if d.cfg["field_exclude_not_plantable"]
                               else "The field-check switch is off: not_plantable points were NOT left out."}
    plan = field_flags_for_plan(d, plan)
    plan_id, f, sj = save_plan(d, req.purpose, plan, summary)
    return render_plan(d, plan, summary, plan_id,
                       {"saved": {"plan_csv": f.name, "summary_json": sj.name, "folder": f"{d.cfg['data_dir']}/{rp.CFG['plans_dir']}"},
                        "next": {"plan": f"/plans/{plan_id}", "build_field_kit": f"POST /plans/{plan_id}/field-kit"}})


@app.get("/plans")
def plans_list(limit: int = Query(API_CFG["plans_list_default_limit"], ge=1, le=API_CFG["plans_list_max_limit"]), d=Depends(D)):
    root = plans_dir(d)
    items = []
    for sj in (root.glob("plan_*_summary.json") if root.is_dir() else []):
        plan_id = sj.name[:-len("_summary.json")]
        if not valid_plan_id(plan_id) or not (root / f"{plan_id}.csv").is_file():
            continue
        try:
            s = json.loads(sj.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        m = re.search(r"_(\d{8})_(\d{6})", plan_id)
        when = (datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").isoformat() if m
                else datetime.fromtimestamp(sj.stat().st_mtime).isoformat(timespec="seconds"))
        items.append({"plan_id": plan_id, "purpose": s.get("purpose"), "n_saplings_requested": s.get("n_saplings_requested"),
                      "n_placed": s.get("saplings_placed"), "n_unmatched": s.get("saplings_unmatched"), "date": when,
                      "field_kit_built": kit_zip_path(d, plan_id).is_file()})
    items.sort(key=lambda x: (x["date"], x["plan_id"]), reverse=True)
    return {"count": len(items[:limit]), "total_saved": len(items), "plans": items[:limit]}


@app.get("/plans/{plan_id}")
def plan_get(plan_id: str, d=Depends(D)):
    csv, js = plan_files(d, plan_id)
    plan = pd.read_csv(csv)
    summary = json.loads(js.read_text(encoding="utf-8"))
    return render_plan(d, plan, summary, plan_id,
                       {"saved": {"plan_csv": csv.name, "summary_json": js.name}, "field_kit_built": kit_zip_path(d, plan_id).is_file(),
                        "next": {"build_field_kit": f"POST /plans/{plan_id}/field-kit", "download": f"/kits/{plan_id}.zip"}})


@app.post("/plans/{plan_id}/field-kit")
def build_field_kit(plan_id: str, d=Depends(D)):
    csv, _ = plan_files(d, plan_id)
    try:
        r = fk.make_kit(csv, d.work / d.cfg["kits_dir"], pdf=True, data_dir=d.root)
    except FileNotFoundError as ex:
        raise HTTPException(404, str(ex))
    except ValueError as ex:
        raise HTTPException(400, f"The field kit could not be built: {ex}")
    pdf_ok = (r["kit_dir"] / "field-map.pdf").is_file()
    return {"plan_id": plan_id, "check_code": r["check_code"], "download_url": f"/kits/{plan_id}.zip", "zip_size_bytes": r["zip"].stat().st_size,
            "pdf_included": pdf_ok, "pdf_note": None if pdf_ok else (r["pdf_note"] or "field-map.pdf was not built"), "manifest": r["manifest"]}


@app.get("/kits/{filename}")
def download_kit(filename: str, d=Depends(D)):
    if not filename.endswith(".zip"):
        raise HTTPException(404, "Field kits are downloaded as /kits/<plan_id>.zip")
    plan_id = filename[:-len(".zip")]
    check_plan_id(plan_id)
    path = kit_zip_path(d, plan_id)
    if path.parent != (d.work / d.cfg["kits_dir"]).resolve() or not path.is_file():
        raise HTTPException(404, f"No field kit has been built for plan '{plan_id}' yet. Build it with POST /plans/{plan_id}/field-kit.")
    return FileResponse(path, media_type="application/zip", filename=path.name)


# ---------------------------------------------------------------------------------------------------------------------
# weather advisory
# ---------------------------------------------------------------------------------------------------------------------
@app.get("/advisory/seasonal")
def advisory_seasonal(species_id: int, lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180), d=Depends(D)):
    i = d.species_idx.get(species_id)
    if i is None:
        raise HTTPException(404, f"species_id {species_id} not found (valid ids: {int(d.ctx.species.species_id.min())}-{int(d.ctx.species.species_id.max())})")
    m, a = d.cfg["advisory_area_margin_deg"], d.all_points
    if not (a.lat.min() - m <= lat <= a.lat.max() + m and a.lon.min() - m <= lon <= a.lon.max() + m):
        raise HTTPException(422, "The coordinate is outside the San Mateo area; the advisory is only offered for the mapped municipality.")
    try:
        fc = adv.fetch_forecast(lat, lon, d.work / d.cfg["cache_dir"])
    except adv.ForecastUnavailable as ex:
        raise HTTPException(503, str(ex))
    row = d.ctx.species.iloc[i]
    out = adv.build_advisory({"species_id": species_id, "common_name": row.common_name, "planting_months": py(row.planting_months),
                              "drought_tol": py(row.drought_tol)}, fc)
    ids = species_field_ids(d, species_id, ["months_raw", "drought_tol"])
    return {"species": {"species_id": species_id, "common_name": row.common_name, "planting_months": py(row.planting_months),
                        "planting_months_names": [adv.CFG["month_names"][mm - 1] for mm in (adv.parse_months(py(row.planting_months)) or [])],
                        "drought_tol": py(row.drought_tol),
                        "source_ids": {f: d.src_by_sf[(species_id, f)] for f in ("months_raw", "drought_tol") if (species_id, f) in d.src_by_sf}},
            "location": {"lat": lat, "lon": lon, "forecast_for_lat": round(lat, adv.CFG["cache_coord_decimals"]),
                         "forecast_for_lon": round(lon, adv.CFG["cache_coord_decimals"])},
            "cached": fc["cached"], "cache_age_minutes": fc["cache_age_minutes"], "cache_stale": fc["stale"], "forecast_fetched_at": fc["fetched_at"],
            "network_error": fc["network_error"], **out, "sources": sources_map(d, ids)}


# ---------------------------------------------------------------------------------------------------------------------
# map layers: boundaries and the grid of scored points (both built once at startup and served from memory)
# ---------------------------------------------------------------------------------------------------------------------
def _cached_json(body, d, live=False):
    """JSON bytes kept in memory by the server. live=True: the answer depends on saved field checks, so the BROWSER must ask again every time
    (max-age=0): otherwise a reloaded page could be shown an old grid that does not know the newest field checks."""
    cc = "public, max-age=0, must-revalidate" if live else f"public, max-age={d.cfg['grid_cache_seconds']}"
    return Response(content=body, media_type="application/json", headers={"Cache-Control": cc})


@app.get("/geo/boundaries")
def geo_boundaries(d=Depends(D)):
    """GeoJSON: the municipal outline (feature 'municipality') and the 15 barangays with their names, a bbox, simplified to stay small."""
    return _cached_json(d.boundaries_body, d)


@app.get("/grid")
def grid(purpose: Purpose,
         species_id: Optional[int] = Query(None, description="colour by this ONE species only (the original parameter)"),
         species_ids: Optional[str] = Query(None, description="comma-separated species ids, for example 1,2,3 (several species)"),
         mode: Literal["all", "any"] = Query("all", description="with species_ids: 'all' = lowest W, suitable only if every selected species is; 'any' = highest W"),
         d=Depends(D)):
    """Compact column arrays for every legal grid point: point_id, lon, lat, W, best_species_id, n_eligible_species, barangay."""
    if species_ids is not None:
        if species_id is not None:
            raise HTTPException(422, "Use either species_id (one species) or species_ids (several), not both")
        return _cached_json(grid_body_multi(d, purpose, parse_species_ids(d, species_ids), mode), d, live=True)
    if species_id is not None and species_id not in d.species_idx:
        raise HTTPException(404, f"species_id {species_id} not found (valid ids: {int(d.ctx.species.species_id.min())}-{int(d.ctx.species.species_id.max())})")
    return _cached_json(grid_body(d, purpose, species_id), d, live=True)


@app.get("/geo/zones")
def geo_zones(d=Depends(D)):
    """GeoJSON of the legal land-use zones (the zones that contain grid points), each with its name, bbox and label point."""
    return _cached_json(d.zones_body, d)


@app.get("/areas/rank")
def areas_rank(purpose: Purpose, species_ids: str = Query(..., description="comma-separated species ids, for example 1,2,3"),
               mode: Literal["all", "any"] = Query("all"), by: Literal["barangay", "zone"] = Query("barangay"), d=Depends(D)):
    """Barangays (or zones) ranked for the selected species: mean W over the legal points, share of points suitable, number of suitable points."""
    return _cached_json(areas_rank_body(d, purpose, parse_species_ids(d, species_ids), mode, by), d, live=True)


class AreaRankRequest(BaseModel):
    purpose: Purpose
    polygon: Optional[dict] = Field(None, description="GeoJSON Polygon / MultiPolygon (or a Feature holding one), lon/lat")
    barangay: Optional[str] = Field(None, description="barangay name (as written, or the display name, e.g. 'Santa Ana')")
    zone: Optional[str] = Field(None, description="zone_desc, e.g. 'Forest Zone'")
    limit: int = Field(10, ge=1, le=45)
    n_saplings: int = Field(API_CFG["area_mix_saplings"], ge=1, le=API_CFG["plan_max_saplings"], description="saplings the suggested mix is worked out for")


@app.post("/rank/area")
def rank_area(req: AreaRankRequest, d=Depends(D)):
    """Species ranked for a whole area (a barangay, a zone or a drawn polygon) plus the suggested mix with shares from the palette code."""
    ctx, cfg = d.ctx, d.cfg
    miss = cfg["missing_marker"]
    mask, info = resolve_area(d, req)
    excluded_here = int((mask & d.ex_mask).sum())
    mask = mask & ~d.ex_mask                                           # points marked not plantable are not candidate land
    idx = np.where(mask)[0]
    if len(idx) == 0 and excluded_here:
        raise HTTPException(400, f"All {excluded_here} planting points of '{info['display_name']}' are marked not plantable in the field, so there is nothing to rank.")
    if len(idx) == 0:
        raise HTTPException(400, f"The area '{info['display_name']}' contains no legal-zone grid points.")
    if field_active(d):
        info = {**info, "not_plantable_points": excluded_here}
    S_area, P = ctx.S[idx], ctx.P[req.purpose]
    st = pal.species_stats(S_area, P, mt.CFG["s_min"])
    st.insert(0, "species_id", ctx.species.species_id.to_numpy())
    suitable = st[st.n_eligible > 0].sort_values(["score", "mean_w", "species_id"], ascending=[False, False, True])
    if suitable.empty:
        raise HTTPException(400, f"No species has eligible points (S >= 0.50) in '{info['display_name']}', so there is nothing to rank. "
                                 "Try another area or another purpose.")
    conf = area_mean_confidence(d, ctx.sites.point_id.to_numpy()[idx])
    rows, ids = [], set()
    for rnk, r in enumerate(suitable.head(req.limit).itertuples(index=False), 1):
        sid = int(r.species_id)
        k = d.species_idx[sid]
        s_ids = species_field_ids(d, sid, [f for fs in ss.TERM_FIELDS.values() for f in fs])
        p_ids = purpose_source_ids(d, sid, req.purpose)
        ids |= set(s_ids) | set(p_ids)
        mc = conf.get(sid)
        flags = list(ctx.species_flags.get(sid, []))
        if mc is not None and mc < rp.CFG["low_confidence_below"]:
            flags.append("low_confidence")
        rows.append({"rank": rnk, "species_id": sid, "common_name": ctx.species.common_name.iloc[k], "species_score": round(float(r.score), 4),
                     "mean_W_where_suitable": round(float(r.mean_w), 4), "suitable_points": int(r.n_eligible),
                     "share_of_area_suitable": round(float(r.eligible_share), 4), "P": round(float(P[k]), 4),
                     "p_confidence": py(d.ps_by_key[(sid, req.purpose)].confidence) if py(d.ps_by_key[(sid, req.purpose)].confidence) is not None else miss,
                     "mean_site_confidence": round(float(mc), 4) if mc is not None else miss, "flags": flags,
                     "source_ids": {"site_score": s_ids, "purpose_score": p_ids}})
    pal_res = pal.build_palette(ctx.species, S_area, P, req.n_saplings)
    mix = [{"species_id": sid, "common_name": nm, "share": round(sh, 4), "quota": q, "species_score": round(sc, 4), "needs_both_sexes": nb,
            "genus": str(ctx.species.genus.iloc[d.species_idx[sid]])}
           for sid, nm, sh, q, sc, nb in zip(pal_res["species_id"], pal_res["common_name"], pal_res["share"], pal_res["quota"], pal_res["score"],
                                             pal_res["needs_both_sexes"])]
    any_suitable = int((S_area >= mt.CFG["s_min"]).any(axis=1).sum())
    return {"purpose": req.purpose, "area": {**info, "legal_points": int(len(idx)), "points_with_a_suitable_species": any_suitable},
            "species_total": int(len(ctx.species)), "species_with_suitable_points": int(len(suitable)), "returned": len(rows), "ranking": rows,
            "mix": {"n_saplings": req.n_saplings, "species": mix, "common_planting_months": pal_res["common_months"], "warnings": pal_res["warnings"],
                    "dioecious_left_out": pal_res["dioecious_rejected"],
                    "caps": {"max_species_share": pal.CFG["max_species_share"], "max_genus_share": pal.CFG["max_genus_share"],
                             "palette_min": pal.CFG["palette_min"], "palette_max": pal.CFG["palette_max"], "status": "provisional"}},
            "score_definition": "species_score = mean W where the species is suitable (S >= 0.50) x the share of the area's grid points where it is suitable",
            "missing": {"marker": miss, "columns": {"mean_site_confidence": f"{miss} = no confidence value available", "p_confidence": f"{miss} = no confidence value available"},
                        "note": "No value is null. In sources, a missing rank is the marker and a missing text is an empty string."},
            "sources": {k: {f: ((miss if f == "rank" else "") if v is None else v) for f, v in src.items()} for k, src in sources_map(d, ids).items()},
            "limits": LIMITS}


# ---------------------------------------------------------------------------------------------------------------------
# saved field checks (what a researcher saw at a spot). Append-only events in data/field/field_checks.db, see pipeline/field_verify.py
# ---------------------------------------------------------------------------------------------------------------------
class FieldCheckIn(BaseModel):
    point_id: int
    status: Literal["verified_plantable", "not_plantable", "needs_recheck"]
    reason: Optional[Literal["paved", "building", "rock_or_ledge", "creek_or_waterlogged", "too_steep", "existing_tree", "owner_refused", "other"]] = Field(
        None, description="required when status is not_plantable")
    note: Optional[str] = Field(None, description=f"up to {fv.CFG['note_max_chars']} characters; required to clear a not_plantable point")
    observer: str = Field(description="who made the check (a name only: there is no login yet)")
    observed_at: Optional[str] = Field(None, description="ISO date/time of the visit (default: now)")
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    gps_accuracy_m: Optional[float] = None
    moved_lat: Optional[float] = Field(None, description="where the stake was actually placed")
    moved_lon: Optional[float] = None
    plan_id: Optional[str] = None


def inside_municipality(d):
    from shapely.geometry import Point, shape
    geom = d.muni_geom
    return lambda lat, lon: geom.contains(Point(lon, lat))


def point_lonlat_of(d):
    def f(pid):
        i = d.point_index.get(int(pid))
        return None if i is None else (float(d.ctx.sites.lon.iloc[i]), float(d.ctx.sites.lat.iloc[i]))
    return f


@app.post("/field-checks", status_code=201)
def field_check_add(req: FieldCheckIn, d=Depends(D)):
    """Save one field check as a new event. Nothing is ever updated or deleted; the latest event of a point is its current status."""
    prev = d.field_current.get(req.point_id)
    try:
        ev = fv.validate_event(req.model_dump(), point_lonlat=point_lonlat_of(d)(req.point_id), inside=inside_municipality(d),
                               previous_status=prev["status"] if prev else None)
        check_id = fv.add_event(d.field_db, ev, source="dashboard")
    except fv.FieldCheckError as ex:
        raise HTTPException(422, str(ex))
    refresh_field(d)
    return {"check_id": check_id, "saved": {**ev, "source": "dashboard", "check_id": check_id}, "current": field_view(d, req.point_id),
            "effect": ("The point is now left out of rankings and plans." if req.point_id in d.field_ex_ids else
                       "Saved. This does not change any score." if req.status == "verified_plantable" else "Saved."),
            "limits": FIELD_LIMITS[:1]}


@app.get("/field-checks/summary")
def field_check_summary(d=Depends(D)):
    s = fv.summary(d.field_current, lambda pid: barangay_display_of(d, pid))
    return {**s, "events": d.field_n_events, "exclude_not_plantable": bool(d.cfg["field_exclude_not_plantable"]), "left_out_of_rankings": len(d.field_ex_ids),
            "statuses": list(fv.STATUSES), "reasons": list(fv.REASONS), "note": "Counts use the CURRENT status of each point (its latest event)."}


@app.get("/field-checks/export.csv")
def field_check_export(scope: Literal["events", "current"] = Query("events", description="events = every saved event; current = the latest event of each point"),
                       d=Depends(D)):
    text = fv.events_csv(d.field_db, lambda pid: barangay_display_of(d, pid), current_only=(scope == "current"))
    return Response(content=text, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="field_checks.csv"'})


@app.post("/field-checks/import")
async def field_check_import(request: Request, observer: str = Query(..., description="who is importing the file"),
                             plan_id: Optional[str] = Query(None, description="only needed if the file has no plan_id column"),
                             observed_at: Optional[str] = Query(None, description="date of the field work (default: now)"), d=Depends(D)):
    """Import a field kit's point-list.csv (the CSV text is the request body). Bad rows are rejected with a reason; a repeated import adds nothing."""
    raw = await request.body()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "The file is not UTF-8 text: save the point list as CSV (UTF-8) and try again.")
    try:
        report = fv.import_kit_csv(d.field_db, text, observer=observer, species=d.ctx.species, plans_dir=plans_dir(d), point_lonlat_of=point_lonlat_of(d),
                                   inside=inside_municipality(d), plan_id=plan_id, observed_at=observed_at)
    except fv.FieldCheckError as ex:
        raise HTTPException(400, str(ex))
    if report["accepted"]:
        refresh_field(d)
    return report


@app.get("/field-checks")
def field_check_list(status: Optional[Literal["verified_plantable", "not_plantable", "needs_recheck"]] = None, barangay: Optional[str] = None,
                     point_id: Optional[int] = None, limit: int = Query(API_CFG["field_list_default_limit"], ge=1, le=API_CFG["field_list_max_limit"]),
                     d=Depends(D)):
    """The CURRENT status of every checked point (latest event each), newest first. Filters: status, barangay, point_id."""
    b = None
    if barangay is not None:
        b = find_barangay(d, barangay)
        if b is None:
            raise HTTPException(400, f"Unknown barangay '{barangay}'. Barangays: {', '.join(d.barangay_display)}")
    rows = []
    for pid, c in d.field_current.items():
        if (status and c["status"] != status) or (point_id is not None and pid != point_id):
            continue
        i = d.point_index.get(pid)
        if b is not None and (i is None or d.point_barangay[i] != b):
            continue
        rows.append(field_view(d, pid))
    rows.sort(key=lambda r: (r["observed_at"], r["check_id"]), reverse=True)
    return {"count": min(len(rows), limit), "total_matching": len(rows), "points": rows[:limit]}


@app.get("/field-checks/{point_id}")
def field_check_history(point_id: int, d=Depends(D)):
    """The full history of one point (oldest first) and its current status."""
    if point_id not in d.point_index:
        raise HTTPException(404, f"point_id {point_id} is not a point of the planting grid")
    return {"point_id": point_id, "current": field_view(d, point_id), "history": fv.history(d.field_db, point_id), "left_out_of_rankings": point_id in d.field_ex_ids,
            "exclude_not_plantable": bool(d.cfg["field_exclude_not_plantable"])}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_v2:app", host="127.0.0.1", port=API_CFG["port"])
