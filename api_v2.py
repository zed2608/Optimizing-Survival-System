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
import dataclasses, hashlib, json, math, os, re, sqlite3, sys, threading, time, unicodedata, urllib.parse, urllib.request, zipfile
from collections import OrderedDict
from datetime import date, datetime, timedelta
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, Optional

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "pipeline"))
import advisory as adv  # noqa: E402
import field_verify as fv  # noqa: E402
import field_kit as fk  # noqa: E402
import landcover as lcv  # noqa: E402
import matching as mt  # noqa: E402
import palettes as pal  # noqa: E402
from names import fix_barangay_column  # noqa: E402
import site_rules as sr  # noqa: E402
import run_plan as rp  # noqa: E402
import score_sites as ss  # noqa: E402

# =====================================================================================================================
# CONFIG - every tunable number lives here. PROVISIONAL unless stated.
# =====================================================================================================================
API_CFG = {
    "data_dir": os.environ.get("OS_DATA_DIR") or "data/processed",   # OS_DATA_DIR: run on another (temporary) copy of the processed data
    "include_unzoned": True,                        # INCLUDE_UNZONED: default of ?include_unzoned= (squares outside the zoning map are scored and flagged zoning_unconfirmed); false = confirmed legal zones only
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
    "layout_mode": rp.CFG["layout_mode"],           # LAYOUT_MODE: "blocks" (new default: n_saplings = total trees planted in blocks at the species spacing) or "points" (one tree per square, the plan of before)
    "campaign_name_max": 80,                        # same limit as CampaignIn.name; a top-up name "<campaign> (top-up N)" is cut to fit
    "advisory_area_margin_deg": 0.1,                # /advisory/seasonal: the coordinate must be this close (degrees) to the mapped grid
    "boundary_simplify_deg": 0.00005,               # /geo/boundaries: first simplification tolerance (degrees, ~5 m)
    "boundary_simplify_max_deg": 0.002,             # ... never simplify beyond this (~200 m)
    "boundary_max_bytes": 300_000,                  # /geo/boundaries: the tolerance grows until the response is under this size
    "coord_decimals": 5,                            # coordinates in /geo/boundaries and /grid (5 decimals ~ 1 m)
    "grid_w_decimals": 3,                           # W in /grid
    "grid_max_bytes": 330_000,                      # /grid should stay under this size (checked by the tests; 8,010 squares with include_unzoned=true ~ 305 KB, false (6,731 squares) stays under 280 KB)
    "missing_marker": -1,                           # /grid: the explicit "no value" marker (never null)
    "grid_cache_seconds": 300,                      # Cache-Control max-age of /geo/boundaries and /grid
    "landuse_shp": "data/LandUses.shp",             # /geo/zones
    "zone_max_bytes": 300_000,                      # /geo/zones: the tolerance grows until the response is under this size
    "multi_cache_max": 48,                          # /grid with species_ids: how many different selections stay cached in memory
    "areas_cache_max": 64,                          # /areas/rank: how many different requests stay cached in memory
    "area_mix_saplings": 100,                       # POST /rank/area: saplings the suggested mix is worked out for (shares barely depend on it)
    "field_db": os.environ.get("OS_FIELD_DB") or "data/field/field_checks.db",   # saved field checks (append-only events, git-ignored); OS_FIELD_DB = another file (tests, browser checks)
    "field_exclude_not_plantable": True,            # THE SWITCH: points whose latest field check is not_plantable are left out of rankings and plans
    "field_list_default_limit": 100,                # GET /field-checks
    "field_list_max_limit": 1000,
    # ---- GET /grid/context: the map squares that are not planting zones ----
    "context_zone_reasons": {                       # zone name (as in the land-use layer) -> reason code; a square with no zone is "outside_zoning"
        "Special Reserved Zone": "special_reserved", "Medium Industrial Zone": "industrial", "Light Industrial Zone": "industrial",
        "Minor Commercial - Mixed Use Zone": "commercial", "Quarry Sub-Zone": "quarry", "Sanitary Landfill": "landfill",
        "Cemetery Zone": "cemetery",
    },
    "context_max_bytes": 120_000,                   # the context body must stay below this size
    # ---- planting window (season) ----
    "season_max_days": 366,                         # start/end dates: the longest window accepted
    # ---- search ----
    "search_group_limit": 5,                        # GET /search/all: results per group (the caller may ask for up to 20)
    "search_recent_plans": 20,                      # GET /search/all looks for planting points in this many most recent saved plans
    # ---- optional place search for streets and landmarks (Nominatim / OpenStreetMap): OFF by default ----
    "geocoder_enabled": False,                      # GEOCODER_ENABLED. Off: GET /search/geocode answers 503 and nothing leaves this computer
    "geocoder_contact": "",                         # GEOCODER_CONTACT: an email address or web address; REQUIRED when enabled (goes in the User-Agent)
    "geocoder_app_name": "OptimizingSurvival-SanMateo",
    "geocoder_url": "https://nominatim.openstreetmap.org/search",
    "geocoder_countrycodes": "ph",                  # only the Philippines
    "geocoder_bbox_margin_deg": 0.02,               # search box = the municipality's bbox plus this margin (~2 km); results are restricted to it
    "geocoder_limit": 8,                            # results per search
    "geocoder_min_interval_s": 1.0,                 # at most one request per second (the public service's rule)
    "geocoder_cache_days": 30,                      # every answer is kept on disk this long
    "geocoder_cache_dir": "cache/geocode",          # under the work folder (data/processed), git-ignored
    "geocoder_timeout_s": 8,
    "geocoder_attribution": "Search data (c) OpenStreetMap contributors",     # the page must show this next to place results
}
LIMITS = [
    "Soil pH is not scored (there is no real pH layer); rainfall, temperature, canopy and exposure are not scored either.",
    "Slope comes from ~100 m grid cells (finite differences); about 22% of cells have a one-axis slope that may under-estimate it.",
    "{SOIL_LIMIT}",
    "All weights, caps, thresholds and purpose scores are PROVISIONAL until the agriculturist signs off.",
    "{DATASET_LIMIT}",
    "Suitability S comes from rules written from the species dataset, not from field survival data.",
    "Each point is a ~100 m grid cell, so a plan places at most one tree per cell.",
    "Species data marked species_data_unverified cites a source file that was not provided.",
    "Scores are not valid outside the mapped municipality of San Mateo, Rizal.",
    "{PLANTING} planting squares + {OTHER} other squares = {TOTAL} map squares.",
    "{UNZONED_LIMIT}",
    "Field checks (verified plantable / not plantable / needs recheck) carry a name only: there is no login yet, and anyone with access to the dashboard can add one.",
    "While the field-check switch is on, points whose latest check is 'not plantable' are left out of rankings and plans; 'verified plantable' only adds a badge and never changes a score.",
]
FIELD_LIMITS = LIMITS[-2:]


UNZONED_NOTE = "Land outside our zoning map; the CLUP 2021-2031 shows it as Forest Reserve (Watershed): coordinate with MENRO and DENR before planting"


def soil_facts(pt):
    """The soil facts of a grid square for /rank and the point search: the LGU series, its texture, the source and the purity (None when the square is outside the soil map or the data has no
    LGU columns), and the legacy texture. Nothing is invented: a missing value stays None."""
    if "soil_texture_lgu" not in pt.index:
        return {}
    ser = py(pt.soil_series_lgu)
    return {"soil": {"series": ser, "texture": py(pt.soil_texture_lgu), "source": py(pt.soil_source) if ser else None, "purity": py(pt.soil_purity),
                     "status": "provisional" if ser else "Data Unavailable",
                     "note": ("Soil from the LGU soil map, digitized by us: provisional" if ser else "This square lies outside the LGU soil map: no soil texture, so the soil term is not scored."),
                     "legacy_texture": py(pt.soil_texture_legacy)}}


def limits_of(d):
    """The known limits with the numbers of THIS data and THIS view filled in (no hard-coded counts): planting squares, other squares, and what the zoning-map gap means."""
    ap = d.all_points
    n_plant, n_total = len(d.ctx.sites), len(ap)
    n_un = int((d.ctx.sites.zoning_status == "unconfirmed").sum()) if "zoning_status" in d.ctx.sites else 0
    n_named = int((d.ctx.sites.zoning_status.eq("unconfirmed") & d.ctx.sites.zone_desc.notna()).sum()) if n_un else 0
    if n_named:                                                        # ZONE_RULES moved a named zone to unconfirmed
        un = (f"{n_un:,} of the planting squares are not confirmed ({n_un - n_named:,} outside our zoning map, {n_named:,} in a named zone the LGU has not cleared). "
              f"The {n_un - n_named:,} outside our zoning map are shown in the CLUP 2021-2031 as Forest Reserve (Watershed). They are scored like the others but flagged zoning_unconfirmed: "
              "coordinate with MENRO and DENR before planting.")
    elif n_un:
        un = (f"{n_un:,} of the planting squares lie outside our zoning map. The CLUP 2021-2031 shows this land as Forest Reserve (Watershed), part of the Upper Marikina River Basin, "
              "which the Sangguniang Bayan resolved to co-manage with DENR. They are scored like the others but flagged zoning_unconfirmed: coordinate with MENRO and DENR before planting.")
    else:
        un = "Land that is not covered by our zoning map (the CLUP 2021-2031 shows it as Forest Reserve, Watershed) is left out until MENRO and DENR confirm it is plantable."
    if "soil_texture_lgu" in d.ctx.sites:
        n_nosoil = int(d.ctx.sites.soil_texture_lgu.isna().sum())
        soil = ("Soil comes from the LGU soil map (Bureau of Soils and Water Management), digitized by us from a scanned figure: approximate, and not yet verified by the agriculturist. "
                f"{n_nosoil:,} of the planting squares lie outside that map (the upper watershed area), have no soil texture, and are scored without the soil term. A texture mismatch only lowers the score "
                "and is flagged soil_unverified_mismatch; scores that use the LGU soil carry the flag soil_provisional. The old soil layer (four world-soil-database codes, legacy) is kept in the data and is also unverified.")
    else:
        soil = "The soil texture mapping is a legacy mapping and is UNVERIFIED; by default a texture mismatch only lowers the score and is flagged soil_unverified_mismatch."
    ds, ic = getattr(d, "dataset", {}) or {}, getattr(d, "ingest_counts", {}) or {}
    if ds.get("tag"):
        left = [f"{ic[k]} cells cite a file that was not provided" if k == "file_source_not_provided" else f"{ic[k]} cite sources outside the supplied list" if k == "off_list_source" else
                f"{ic[k]} citations are non-standard" if k == "nonstandard_citation" else f"{ic[k]} species have no Type I climate preference" if k == "no_type_I_preference" else
                f"{ic[k]} species soil text is unmapped" for k in ("file_source_not_provided", "off_list_source", "nonstandard_citation", "no_type_I_preference", "soil_text_unmapped") if ic.get(k)]
        dset = (f"Species data release {ds['tag']} (hash {ds.get('combined_hash12') or str(ds.get('file_hash'))[:12]}): {ds.get('note') or 'not signed off'}. "
                + (f"Known issues left for the agriculturist: {'; '.join(left)}." if left else ""))
    else:
        dset = "The species data release is not named."
    fill = {"{DATASET_LIMIT}": dset, "{PLANTING}": f"{n_plant:,}", "{OTHER}": f"{n_total - n_plant:,}", "{TOTAL}": f"{n_total:,}", "{UNZONED_LIMIT}": un, "{SOIL_LIMIT}": soil}
    out = []
    for t in LIMITS:
        for k, v in fill.items():
            t = t.replace(k, v)
        out.append(t)
    return out
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
    if d.unconf_idx:                                                   # squares outside the zoning map: positions in the column arrays (absent when there are none)
        doc["zoning"] = {"unconfirmed_index": d.unconf_idx, "n_unconfirmed": len(d.unconf_idx),
                         "note": "These positions are squares outside our zoning map (the CLUP 2021-2031 shows this land as Forest Reserve, Watershed): scored like the others but not confirmed as planting zones. Coordinate with MENRO and DENR before planting."}
    return json.dumps(doc, separators=(",", ":")).encode("utf-8")


def grid_body(d, purpose, species_id=None, drop=()):
    """JSON bytes of /grid for a purpose (best species at each legal point) or a purpose + ONE species (that species only). Cached in memory.
    drop = species ids removed by the season filter: their W is 0 (they are never the best species)."""
    key = (purpose, species_id)
    if not drop and key in d.grid_cache:
        return d.grid_cache[key]
    if drop:
        hit = lru_get(d.multi_cache, ("g",) + key + (drop,))
        if hit is not None:
            return hit
    ctx, cfg = d.ctx, d.cfg
    miss = cfg["missing_marker"]
    W, feas = mt.weights(ctx.S, ctx.P[purpose])
    if drop:
        gone = np.isin(ctx.species.species_id.to_numpy(dtype=int), list(drop))
        W, feas = np.where(gone[None, :], 0.0, W), feas & ~gone[None, :]
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
    if drop:
        lru_put(d.multi_cache, ("g",) + key + (drop,), body, d.cfg["multi_cache_max"])
    else:
        d.grid_cache[key] = body
    return body


CONTEXT_REASONS = {                                   # reason code -> plain words (an unnamed zone that is not in the table above is "other")
    "outside_zoning": "Outside the zoning map",
    "special_reserved": "Special Reserved Zone: not a planting zone",
    "industrial": "Industrial zone: not a planting zone",
    "commercial": "Commercial zone: not a planting zone",
    "quarry": "Quarry zone: not a planting zone",
    "landfill": "Sanitary landfill: not a planting zone",
    "cemetery": "Cemetery zone: not open to tree planting (MPDC, 7 Oct 2026)",
    "other": "A zone that is not a planting zone",
}


def build_context_body(d):
    """JSON bytes of GET /grid/context: the grid squares that are NOT planting zones, as compact arrays. Built once at startup. No nulls: -1 = no zone / no barangay."""
    cfg = d.cfg
    miss = cfg["missing_marker"]
    ap = d.all_points
    rows = np.where(~ap.point_id.isin(d.ctx.sites.point_id).to_numpy())[0]          # every square that is not a scored planting square in this view
    sub = ap.iloc[rows]
    zone_names = sorted(str(z) for z in sub.zone_desc.dropna().unique())
    zone_idx = {z: i for i, z in enumerate(zone_names)}
    reasons = list(CONTEXT_REASONS)
    code, zcol = [], []
    for z in sub.zone_desc:
        if pd.isna(z):
            code.append(reasons.index("outside_zoning"))
            zcol.append(miss)
        else:
            code.append(reasons.index(cfg["context_zone_reasons"].get(str(z), "other")))
            zcol.append(zone_idx[str(z)])
    nd = cfg["coord_decimals"]
    counts = {r: int(code.count(i)) for i, r in enumerate(reasons)}
    doc = {"n": int(len(rows)), "legal_points": int(len(ap) - len(rows)), "total_points": int(len(ap)),
           "columns": {"point_id": sub.point_id.astype(int).tolist(), "lon": np.round(sub.lon.to_numpy(), nd).tolist(), "lat": np.round(sub.lat.to_numpy(), nd).tolist(),
                       "reason": code, "zone": zcol, "barangay": d.allpt_barangay[rows].tolist()},
           "reasons": reasons, "reason_labels": CONTEXT_REASONS, "reason_counts": counts, "zones": zone_names,
           "barangays": d.barangay_names, "barangays_display": d.barangay_display,
           "missing": {"marker": miss, "columns": {"zone": f"{miss} = the square lies outside every zoning polygon", "barangay": f"{miss} = the square lies outside every barangay polygon"},
                       "note": "No column contains null. reason is an index into reasons; zone an index into zones; barangay an index into barangays. These squares are NOT scored."}}
    if d.zoning_on:                                                    # squares outside the zoning map are planting squares in this view: say what the table's "no zone" marker means
        doc["zoning"] = {"unconfirmed_squares_are_planting_squares": True,
                         "zone_table": [{"index": miss, "name": None, "label": "Outside our zoning map (CLUP: Forest Reserve, Watershed): the zoning file has no polygon here. Such squares are scored and flagged zoning_unconfirmed, so none of them is listed in this layer."}]
                                       + [{"index": i, "name": z, "label": CONTEXT_REASONS[cfg["context_zone_reasons"].get(z, "other")]} for i, z in enumerate(zone_names)],
                         "note": "With include_unzoned=true this layer holds only the squares in a named non-planting zone. With include_unzoned=false it also holds the squares outside the zoning map."}
    body = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    if len(body) > cfg["context_max_bytes"]:
        raise RuntimeError(f"/grid/context is {len(body)} bytes (limit {cfg['context_max_bytes']})")
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
    if not ids:                                                        # every selected species was removed by the season filter: nothing is suitable
        n = len(ctx.sites)
        return np.zeros(n), np.full(n, d.cfg["missing_marker"]), np.zeros(n, dtype=int)
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
    Done for every view of the data (include_unzoned true and false).
    """
    for v in {id(x): x for x in (d, *getattr(d, "views", {}).values())}.values():
        _refresh_one(v)


def _refresh_one(d):
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
            extra.append({"verified_plantable": "field_verified", "planted": "field_verified", "needs_recheck": "field_needs_recheck", "not_plantable": "field_not_plantable"}[c["status"]])
            if c["disputed"]:
                extra.append("field_disputed")
        out.append(";".join(x for x in (fl.split(";") if fl else []) + extra if x))
    plan["flags"] = out
    return plan


GROUND_SHARE_KEYS = {"share_tree": "tree", "share_shrub": "shrub", "share_grass": "grass", "share_crop": "crop", "share_built": "built", "share_bare": "bare",
                     "share_water": "water", "share_wetland": "wetland", "share_mangrove": "mangrove", "share_other": "other"}
GROUND_CODES = [10, 20, 30, 40, 50, 60, 80, 90, 95, 100]                     # the classes of /grid/landcover (index = position in this list)
GROUND_GROUPS = {10: "tree", 20: "shrub_grass", 30: "shrub_grass", 40: "crop", 50: "built", 60: "bare", 80: "water", 90: "water", 95: "water", 100: "other"}
GROUND_BITS = {"ground_bare": 1, "ground_built_up": 2, "ground_water": 4}


def ground_cover_block(d, pid):
    """Satellite land cover of one grid square (ESA WorldCover 2021): shares, the one-line text, the flags with their plain notes, and the accuracy note. None without data."""
    if d.landcover is None or int(pid) not in d.landcover.index:
        return None
    r = d.landcover.loc[int(pid)]
    src = lcv.SOURCE
    base = {"year": src["year"], "source": src["name"], "doi": src["doi"], "license": src["license"], "attribution": src["attribution"],
            "accuracy_note": f"Satellite land cover from 2021, about {src['accuracy'].split('%')[0].split()[-1]}% accurate worldwide (overall accuracy stated in the Product Validation Report V2.0). Check on the ground.",
            "provisional_thresholds": {"bare": lcv.LC_CFG["flag_bare_share"], "built_up": lcv.LC_CFG["flag_built_share"], "water": lcv.LC_CFG["flag_water_share"]}}
    if pd.isna(r["share_tree"]):
        return {**base, "available": False, "line": None, "shares": {}, "flags": [], "flag_notes": {}, "note": "Data Unavailable: the satellite raster does not cover this square well enough."}
    shares = {GROUND_SHARE_KEYS[c]: round(float(r[c]), 3) for c in GROUND_SHARE_KEYS}
    flags = [f for f in str(r["ground_flags"]).split(";") if f] if isinstance(r["ground_flags"], str) else []
    code = int(r["dominant_code"])
    return {**base, "available": True, "line": lcv.describe(r), "shares": shares, "dominant_code": code, "dominant": lcv.CODE_NAME.get(code), "flags": flags,
            "flag_notes": {f: lcv.FLAG_NOTES[f] for f in flags}, "coverage": py(r["lc_coverage"]) if "lc_coverage" in r else None,
            "info": (f"Mostly tree cover ({round(100 * shares['tree'])}%)" if shares["tree"] >= lcv.LC_CFG["info_tree_share"] else None)}


def build_landcover_body(d):
    """GET /grid/landcover: the dominant class of every grid square and its ground flags, compact (point_id, class index, flag bits), cached at startup."""
    ap = d.all_points
    lc = d.landcover.reindex(ap.point_id.to_numpy())
    idx = {c: i for i, c in enumerate(GROUND_CODES)}
    codes = [(-1 if pd.isna(v) else idx[int(v)]) for v in lc.dominant_code]
    bits = [sum(GROUND_BITS[f] for f in str(v).split(";") if f in GROUND_BITS) if isinstance(v, str) else 0 for v in lc.ground_flags]
    doc = {"n": int(len(ap)), "year": lcv.SOURCE["year"], "source": lcv.SOURCE["name"], "attribution": lcv.SOURCE["attribution"], "accuracy": lcv.SOURCE["accuracy"],
           "classes": [{"index": i, "code": c, "name": lcv.CODE_NAME[c], "group": GROUND_GROUPS[c]} for i, c in enumerate(GROUND_CODES)],
           "flag_bits": GROUND_BITS, "missing": {"marker": -1, "note": "-1 = the satellite raster has no usable data for the square (never zero)"},
           "columns": {"point_id": ap.point_id.astype(int).tolist(), "class": codes, "flags": bits},
           "note": "Information only. The same squares as site_points_clean.csv; no score or ranking depends on it."}
    return json.dumps(doc, separators=(",", ":")).encode("utf-8")


def limiting_factors(d, pt, items, n_suit, requested):
    """Why few (or no) species suit a square: for each hard gate how many species it excludes, the square's value and the lowest and highest species limit. Built from the
    gate_failed lists of the saved site breakdown (nothing is recomputed); `items` = (eligible, W, S, k, species_id, confidence, breakdown) of ALL species."""
    sp = d.ctx.species
    n = len(items)
    gates = {"zone": 0, "elevation": 0, "slope": 0, "soil": 0}
    soil_mis = 0
    no_gate_low = 0
    for el, _w, _s, _k, _sid, _c, bd in items:
        failed = bd.get("gate_failed", [])
        for g_ in failed:
            key = "zone" if g_ == "legal_zone" else g_
            if key in gates:
                gates[key] += 1
        if "soil_unverified_mismatch" in bd.get("flags", []):
            soil_mis += 1
        if not el and not failed:
            no_gate_low += 1
    elev, slope = py(pt.elev_m), py(pt.slope_pct)
    emin, emax = py(sp.elev_min_m.min()), py(sp.elev_max_m.max())
    smin, smax = py(sp.max_slope_pct.min()), py(sp.max_slope_pct.max())
    f_ = []
    msgs = []
    lgu = "soil_texture_lgu" in pt.index
    tex = py(pt.soil_texture_lgu) if lgu else py(pt.soil_texture_legacy)
    tex_src = "from the LGU soil map, digitized by us and unverified" if lgu else "from a legacy and unverified soil map"
    f_.append({"gate": "zone", "label": "Zone", "species_excluded": gates["zone"], "n_species": n, "square_value": py(pt.zoning_status) if "zoning_status" in pt else None, "unit": None,
               "species_limit_min": None, "species_limit_max": None, "message": None})
    ex = gates["elevation"]
    m = None
    if ex and elev is not None:
        if ex == n:
            m = (f"Elevation {elev:.0f} m is higher than the limit of every species (highest allowed: {emax:.0f} m)." if elev > emax else
                 f"Elevation {elev:.0f} m is lower than the limit of every species (lowest allowed: {emin:.0f} m)." if elev < emin else
                 f"Elevation {elev:.0f} m is outside the range of every species (the ranges run from {emin:.0f} m to {emax:.0f} m).")
        else:
            m = f"Elevation {elev:.0f} m is outside the range of {ex} of {n} species (the limits run from {emin:.0f} m to {emax:.0f} m)."
    f_.append({"gate": "elevation", "label": "Elevation", "species_excluded": ex, "n_species": n, "square_value": elev, "unit": "m", "species_limit_min": emin, "species_limit_max": emax, "message": m})
    ex = gates["slope"]
    m = None
    if ex and slope is not None:
        m = (f"Slope {slope:.0f}% is steeper than the limit of every species (highest allowed: {smax:.0f}%)." if ex == n else
             f"Slope {slope:.0f}% is steeper than the limit of {ex} of {n} species (the limits run from {smin:.0f}% to {smax:.0f}%).")
    f_.append({"gate": "slope", "label": "Slope", "species_excluded": ex, "n_species": n, "square_value": slope, "unit": "%", "species_limit_min": smin, "species_limit_max": smax, "message": m})
    ex = gates["soil"]
    m = None
    if ex:
        m = f"The soil texture ({tex}) rules out {ex} of {n} species."
    elif soil_mis:
        m = (f"The soil texture ({tex}, {tex_src}) does not match {soil_mis} of {n} species. This only lowers their score; it does not rule them out.")
    f_.append({"gate": "soil", "label": "Soil", "species_excluded": ex, "n_species": n, "square_value": tex, "unit": None, "species_limit_min": None, "species_limit_max": None,
               "species_with_mismatch": soil_mis, "message": m})
    msgs = [x["message"] for x in f_ if x["message"]]
    if no_gate_low:
        msgs.append(f"{no_gate_low} of {n} species stay below the suitability limit of 0.50 even though no hard limit rules them out (several soft factors together).")
    return {"applies": True, "shown_because": "requested" if requested and n_suit >= 3 else "fewer_than_3_species_suit", "n_species": n, "n_suitable": int(n_suit), "factors": f_,
            "messages": msgs, "low_score_without_gate": int(no_gate_low),
            "source": "the site_scores breakdown (gate_failed) and the species table limits; nothing is recomputed"}


def mean_confidence(d, ctx):
    """{species_id: mean site confidence} over the scored squares of a context (from the scores database; {} for a csv)."""
    if not d.is_db:
        return {}
    con = sqlite3.connect(ctx.scores_path)
    ids = ",".join(str(int(i)) for i in ctx.sites.point_id)
    mc = pd.read_sql_query(f"SELECT species_id, AVG(confidence) AS c FROM site_scores WHERE point_id IN ({ids}) GROUP BY species_id", con)
    con.close()
    return dict(zip(mc.species_id.astype(int), mc.c))


def municipal_tables(ctx):
    out = {}
    for purpose in mt.PURPOSES:
        st = pal.species_stats(ctx.S, ctx.P[purpose], mt.CFG["s_min"])
        st.insert(0, "species_id", ctx.species.species_id.to_numpy())
        out[purpose] = st.sort_values(["score", "species_id"], ascending=[False, True]).reset_index(drop=True)
    return out


class HabView:
    """The data seen for a planting window that touches Jul-Sep (round 15a, MAO 7 Oct 2026, provisional): the site match S of the squares of the Habagat barangays is multiplied by 0.8, so every
    ranking, map colour and plan made through this object uses the lowered values (and S >= 0.50 is tested on them). Everything else is read from the base data object."""
    def __init__(self, base):
        object.__setattr__(self, "_base", base)

    def __getattr__(self, name):
        return getattr(self._base, name)


def habagat_data(d, season):
    """d itself unless the planting window touches a Habagat month; then a HabView of d with the lowered S (built once per data object, cached with its own response caches)."""
    if season is None:
        return d
    months = season_object(None, season)["window_months"]
    if not sr.habagat_months_hit(months):
        return d
    store = vars(d).get("_hab_store")
    if store is None:
        names = [d.barangay_names[b] if b >= 0 else "" for b in d.point_barangay]
        mask = sr.habagat_square_mask(names)
        S = d.ctx.S.copy()
        S[mask] = S[mask] * float(sr.HABAGAT_CFG["multiplier"])
        store = {"mask": mask, "ctx": dataclasses.replace(d.ctx, S=S), "grid": {}, "multi": OrderedDict(), "areas": OrderedDict()}
        d._hab_store = store
    v = HabView(d)
    v.base_ctx, v.ctx, v.hab_mask, v.hab = d.ctx, store["ctx"], store["mask"], sr.habagat_info(months)
    v.grid_cache, v.multi_cache, v.areas_cache = store["grid"], store["multi"], store["areas"]
    return v


def habagat_flags_for_plan(d, plan):
    """Add habagat_washout to the flags of the planned points that lie in a Habagat barangay (when the window touches Jul-Sep)."""
    hab = getattr(d, "hab", None)
    if not hab or plan.empty:
        return plan, 0
    names = []
    for pid in plan.point_id.astype(int):
        j = d.allpt_index.get(pid)
        b = int(d.allpt_barangay[j]) if j is not None else -1
        names.append(d.barangay_names[b] if b >= 0 else "")
    m = sr.habagat_square_mask(names)
    plan = plan.copy()
    plan["flags"] = [";".join(x for x in (str(fl).split(";") if isinstance(fl, str) and fl else []) + ([sr.HABAGAT_FLAG] if hit else []) if x) for fl, hit in zip(plan["flags"], m)]
    n = int(plan.loc[m, "trees_planned"].sum()) if "trees_planned" in plan else int(m.sum())
    return plan, n


class View:
    """The data seen with include_unzoned=false: squares outside the zoning map are not planting squares, exactly as before zoning_status existed.
    Whatever depends on the set of scored squares is held here; everything else (species, sources, outlines, field database ...) is read from the base data object."""
    def __init__(self, base):
        object.__setattr__(self, "_base", base)

    def __getattr__(self, name):
        return getattr(self._base, name)


def confirmed_view(base):
    cfg = base.cfg
    v = View(base)
    keep = (base.ctx.sites.zoning_status == "confirmed").to_numpy()
    v.include_unzoned, v.zoning_on, v.unconf_idx = False, False, []
    v.ctx = rp.confirmed_only(base.ctx)
    v.tree_legal = cKDTree(v.ctx.sites[["utm_e", "utm_n"]].to_numpy(dtype=float))
    v.legal_index = {int(p): i for i, p in enumerate(v.ctx.sites.point_id)}
    v.point_index = v.legal_index
    v.point_barangay, v.point_zone = base.point_barangay[keep], base.point_zone[keep]
    v.mean_conf = mean_confidence(base, v.ctx)
    v.municipal = municipal_tables(v.ctx)
    v.boundaries_body, v.boundaries_info = build_boundaries(base.gs, base.barangay_names, base.barangay_display, v.point_barangay, cfg)
    v.zones_body, v.zone_bbox = base.zones_body, base.zone_bbox        # zones hold confirmed squares only: identical in both views
    v.grid_cache, v.multi_cache, v.areas_cache = {}, OrderedDict(), OrderedDict()
    v.context_body = build_context_body(v)
    _refresh_one(v)
    return v


def load_data(cfg=None):
    cfg = API_CFG if cfg is None else cfg
    root = ROOT / cfg["data_dir"]
    ctx = rp.load_context(root, include_unzoned=True)                  # confirmed + unconfirmed squares; the confirmed-only view is derived below
    sources = pd.read_csv(root / "species_sources.csv")
    refs = pd.read_csv(root / "species_references.csv")
    ps = pd.read_csv(root / "purpose_scores.csv")
    all_points = pd.read_csv(root / "site_points_clean.csv")
    if "zoning_status" not in all_points:                              # data made before zoning_status existed: derive it (confirmed = legal zone; no unconfirmed squares were scored)
        all_points["zoning_status"] = np.where(all_points.is_legal_zone.astype(bool), "confirmed", "excluded")
    d = SimpleNamespace(cfg=cfg, root=root, work=root, ctx=ctx, sources=sources, refs=refs, purpose_scores=ps, all_points=all_points)
    d.include_unzoned = True
    d.zoning_on = bool((ctx.sites.zoning_status == "unconfirmed").any())          # False on older data: the switch then has nothing to do
    d.unconf_idx = np.where((ctx.sites.zoning_status == "unconfirmed").to_numpy())[0].tolist()
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
    ir = root / "ingest_report.csv"                                    # what the ingest found in the species data (counts shown in Known limits)
    d.ingest_counts = pd.read_csv(ir).groupby("issue").size().to_dict() if ir.is_file() else {}
    d.is_db = ctx.scores_path.suffix == ".db"
    d.mean_conf = mean_confidence(d, ctx)
    # municipal ranking per purpose (cheap, computed once)
    d.municipal = municipal_tables(ctx)
    # barangays
    import geopandas as gpd
    g = fix_barangay_column(gpd.read_file(ROOT / cfg["barangay_shp"]))          # round 15a: "Pintong Bukawe" (the shapefile spells it Pintung)
    proj = g.to_crs(cfg["site_crs"])
    cen = proj.centroid.to_crs("EPSG:4326")
    d.places = [{"name": str(r.BRGY_NAME), "display_name": display_name(r.BRGY_NAME, cfg["place_aliases"]), "key": norm_place(r.BRGY_NAME, cfg["place_aliases"]),
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
    pts_all = gpd.GeoDataFrame({"i": np.arange(len(all_points))}, geometry=gpd.points_from_xy(all_points.lon, all_points.lat), crs=gs.crs)
    j_all = gpd.sjoin(pts_all, gs[["geometry"]].reset_index().rename(columns={"index": "b"}), how="left", predicate="intersects")
    d.allpt_barangay = j_all.drop_duplicates("i", keep="first").set_index("i").b.reindex(range(len(all_points))).fillna(cfg["missing_marker"]).astype(int).to_numpy()
    d.allpt_index = {int(p): i for i, p in enumerate(all_points.point_id)}
    lcf = root / "site_landcover.csv"                                  # ground cover from satellite land cover (information only)
    d.food_ids = sr.food_bearing_ids(ctx.species)                       # food-bearing species (type text): the rehabilitation-site warning applies to them
    # round 15a: tables beside the species table (interviews of 7 Oct 2026; provisional): purpose tags (filters only), the LGU nursery list, interview notes
    def _table(name):
        f = root / name
        return pd.read_csv(f, keep_default_na=False) if f.is_file() else None
    tt, nt, it = _table("species_purpose_tags.csv"), _table("nursery_stock.csv"), _table("interview_notes.csv")
    d.purpose_tags = {int(k): g[["tag", "basis"]].to_dict("records") for k, g in tt.groupby("species_id")} if tt is not None else {}
    d.nursery_rows = {int(k): g.to_dict("records") for k, g in nt[nt.matched_species_id.astype(str) != ""].assign(matched_species_id=lambda x: x.matched_species_id.astype(int)).groupby("matched_species_id")} if nt is not None else {}
    d.nursery_table_present = nt is not None
    d.interview_notes = {int(k): g[["note", "source", "provisional"]].to_dict("records") for k, g in it.groupby("species_id")} if it is not None else {}
    pf = root / "species_partners.csv"                                  # "Works well with": starting rules from pipeline/partners.py (provisional)
    d.partners = pd.read_csv(pf) if pf.is_file() else None
    d.landcover = pd.read_csv(lcf).set_index("point_id") if lcf.is_file() else None
    d.landcover_body = build_landcover_body(d) if d.landcover is not None else None
    d.places_sorted = sorted(d.places, key=lambda p: p["name"])           # same order as barangay_names (sorted by name)
    d.geo = SimpleNamespace(lock=threading.Lock(), last=None, clock=time.monotonic, sleep=time.sleep)
    d.plan_index_cache = OrderedDict()
    d.species_months = [pal.parse_months(v) for v in ctx.species.planting_months]      # {5, 6, 7} or None (never guessed)
    d.gs = gs
    d.boundaries_body, d.boundaries_info = build_boundaries(gs, d.barangay_names, d.barangay_display, d.point_barangay, cfg)
    d.barangay_keys = [norm_place(n, cfg["place_aliases"]) for n in d.barangay_names]
    d.barangay_bbox = [f["properties"]["bbox"] for f in json.loads(d.boundaries_body)["features"][1:]]
    d.zone_names = sorted(str(z) for z in ctx.sites.zone_desc.dropna().unique())
    d.point_zone = pd.Categorical(ctx.sites.zone_desc, categories=d.zone_names).codes.astype(int)
    d.zones_body, d.zone_bbox = build_zones(d, cfg)
    d.grid_cache = {}
    d.multi_cache = OrderedDict()
    d.areas_cache = OrderedDict()
    d.context_body = build_context_body(d)
    from shapely.geometry import shape as _shape
    d.muni_geom = _shape(json.loads(d.boundaries_body)["features"][0]["geometry"]).buffer(fv.CFG["municipality_buffer_deg"])
    d.point_index = d.legal_index
    d.field_db = ROOT / cfg["field_db"]
    fv.connect(d.field_db).close()                                    # creates data/field/ and the table on the first start
    refresh_field(d)
    d.views = {True: d, False: d}
    if d.zoning_on:
        d.views[False] = confirmed_view(d)
    for v in {id(x): x for x in d.views.values()}.values():
        for purpose in mt.PURPOSES:
            grid_body(v, purpose, None)
    return d.views[bool(cfg["include_unzoned"])]                        # app.state.data is the DEFAULT view; the other one is reached through ?include_unzoned=


@asynccontextmanager
async def lifespan(app):
    app.state.data = load_data()
    yield


app = FastAPI(title="San Mateo Optimizing Survival API (v2)", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=API_CFG["cors_origins"], allow_credentials=False,
                   allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])


def D(request: Request, include_unzoned: Optional[bool] = Query(None, description="true: squares outside the zoning map are planting squares too (scored, flagged zoning_unconfirmed); "
                                                                                 "false: confirmed legal zones only, exactly as before. Default: API_CFG include_unzoned")):
    d = request.app.state.data
    views = getattr(d, "views", None)
    if not views:
        return d
    return views[bool(d.cfg["include_unzoned"] if include_unzoned is None else include_unzoned)]


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


# ---------------------------------------------------------------------------------------------------------------------
# planting window (season): optional start / end dates. Species planting months decide which species can be planted in the window.
# The scores S, P and W NEVER depend on the dates. season_filter=mark only labels species; season_filter=only also removes the out-of-season ones.
# Month granularity: a month counts if any day of it lies inside the window. A species with no planting months is "unknown" (never guessed, never removed).
# ---------------------------------------------------------------------------------------------------------------------
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_date(text, name):
    if not isinstance(text, str) or not DATE_RE.fullmatch(text.strip()):
        raise HTTPException(422, f"{name} must be a date written YYYY-MM-DD, for example 2026-10-06 (got '{text}').")
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise HTTPException(422, f"{name} '{text}' is not a real calendar date.")


def window_month_list(start, end):
    """Month numbers touched by the window in calendar order from the start; a window may cross the year end (10 Nov to 20 Feb -> [11, 12, 1, 2])."""
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(m)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return list(dict.fromkeys(out))


def parse_season(cfg, start, end, season_filter="mark"):
    """None when no dates were sent (behaviour exactly as before); otherwise the planting window. Bad dates are a 422 with a plain message."""
    if start is None and end is None:
        return None
    if start is None or end is None:
        raise HTTPException(422, "Send both start and end (YYYY-MM-DD), or neither.")
    s, e = parse_date(start, "start"), parse_date(end, "end")
    if e < s:
        raise HTTPException(422, f"The end date ({e.isoformat()}) is before the start date ({s.isoformat()}). The window must end on or after its start.")
    days = (e - s).days + 1
    if days > cfg["season_max_days"]:
        raise HTTPException(422, f"The planting window is {days} days long; the longest allowed is {cfg['season_max_days']} days.")
    if season_filter not in ("only", "mark"):
        raise HTTPException(422, "season_filter must be 'only' or 'mark'.")
    return SimpleNamespace(start=s, end=e, days=days, months=window_month_list(s, e), filter=season_filter)


def season_q(start: Optional[str] = Query(None, description="planting window start, YYYY-MM-DD (send together with end)"),
             end: Optional[str] = Query(None, description="planting window end, YYYY-MM-DD"),
             season_filter: Literal["only", "mark"] = Query("mark", description="'mark' = label species with their season status; 'only' = also remove the out-of-season ones"),
             d=Depends(D)):
    return parse_season(d.cfg, start, end, season_filter)


def HD(season=Depends(season_q), d=Depends(D)):
    """Like D, but with the Habagat adjustment when the planting window touches Jul-Sep (see habagat_data)."""
    return habagat_data(d, season)


def season_object(species_months, season):
    """status: in_season (every month of the window is a planting month) | partly (some) | out_of_season (none) | unknown (no planting months recorded)."""
    win = season.months
    if species_months is None:
        return {"status": "unknown", "window_months": win, "species_months": [], "months_in_window": []}
    inn = [m for m in win if m in species_months]
    status = "in_season" if len(inn) == len(win) else ("partly" if inn else "out_of_season")
    return {"status": status, "window_months": win, "species_months": sorted(species_months), "months_in_window": inn}


def season_drop_ids(d, season):
    """Species ids removed by season_filter=only (the out-of-season ones). Unknown ones stay, marked."""
    if season is None or season.filter != "only":
        return ()
    ids = d.ctx.species.species_id.astype(int).tolist()
    return tuple(sid for sid, m in zip(ids, d.species_months) if season_object(m, season)["status"] == "out_of_season")


def day_text(x):
    return f"{x.day} {x.strftime('%b')}"


def season_block(d, season, selected_ids=None):
    objs = [season_object(m, season)["status"] for m in d.species_months]
    n = len(objs)
    drop = season_drop_ids(d, season)
    block = {"start": season.start.isoformat(), "end": season.end.isoformat(), "days": season.days, "window_months": season.months, "filter": season.filter,
             "species_total": n, "in_season": objs.count("in_season"), "partly": objs.count("partly"), "out_of_season": objs.count("out_of_season"),
             "unknown": objs.count("unknown"), "removed": len(drop), "removed_species_ids": list(drop), "kept": n - len(drop),
             "removed_reason": "out_of_season: none of the months of the window is a planting month of the species" if drop else "",
             "message": (f"Only {n - len(drop)} of {n} species can be planted between {day_text(season.start)} and {day_text(season.end)}." if season.filter == "only"
                         else f"{objs.count('in_season')} of {n} species are fully in season and {objs.count('partly')} partly between {day_text(season.start)} and {day_text(season.end)}."),
             "note": "Month granularity: a month counts if any day of it is inside the window. Scores S, P and W do not depend on the dates. "
                     "A species with no planting months is 'unknown' and is never removed."}
    if selected_ids is not None:
        block["selected_removed_ids"] = [int(i) for i in selected_ids if int(i) in drop]
    return block


def season_extra(d, season, selected_ids=None):
    return {} if season is None else {"season": season_block(d, season, selected_ids)}


def with_season(body, block):
    """Add a "season" member to cached JSON bytes (the cached grid / area bodies do not depend on the dates themselves)."""
    return body[:-1] + b',"season":' + json.dumps(block, separators=(",", ":")).encode("utf-8") + b"}"


def clip_months(species, season):
    """A copy of the species table whose planting_months are cut to the window (used so that a palette's shared months lie inside the window)."""
    sp = species.copy()
    win = set(season.months)
    out = []
    for v in sp.planting_months:
        m = pal.parse_months(v)
        out.append(";".join(str(x) for x in sorted(m & win)) if m else v)
    sp["planting_months"] = out
    return sp


def season_ctx(ctx, season, drop):
    """A matching.Context without the removed species and with planting months cut to the window."""
    keep = ~ctx.species.species_id.astype(int).isin(drop).to_numpy()
    sp = clip_months(ctx.species[keep].reset_index(drop=True), season)
    return dataclasses.replace(ctx, species=sp, S=ctx.S[:, keep], P={k: v[keep] for k, v in ctx.P.items()})


def plan_season(d, season, summary):
    """The season block of a plan summary, with the months the palette shares inside the window."""
    block = season_block(d, season)
    common = summary.get("palette_common_planting_months") or []
    inside = [m for m in season.months if m in common]
    block["palette_common_months"] = list(common)
    block["palette_common_months_in_window"] = inside
    if summary["palette"] and not inside:
        summary["palette_warnings"] = list(summary.get("palette_warnings", [])) + [
            "season: the species of this palette do not share a planting month inside the window (season_filter=mark does not change the palette)"]
    return block


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
            "dataset_hash": d.dataset.get("combined_hash12"), "dataset_species_file_sha256": d.dataset.get("file_hash"), "dataset_sources_file_sha256": d.dataset.get("sources_file_hash"),
            "dataset_note": d.dataset.get("note"),
            "dataset": d.dataset, "scores_file": str(ctx.scores_path.relative_to(ROOT)) if ctx.scores_path.is_relative_to(ROOT) else str(ctx.scores_path),
            "counts": {"species": len(ctx.species), "grid_points": len(d.all_points), "legal_points": len(ctx.sites),
                       "species_point_scores": int(ctx.S.size), "sources": len(d.sources), "barangays": len(d.places)},
            "purposes": list(mt.PURPOSES), "limits": limits_of(d),
            "ground_cover": {"available": d.landcover is not None, "source": lcv.SOURCE["name"], "attribution": lcv.SOURCE["attribution"], "accuracy": lcv.SOURCE["accuracy"],
                             "squares": int(d.landcover.share_tree.notna().sum()) if d.landcover is not None else 0},
            "field_checks": {"events": d.field_n_events, "points_checked": len(d.field_current), "left_out_of_rankings": len(d.field_ex_ids),
                             "exclude_not_plantable": bool(d.cfg["field_exclude_not_plantable"])}}


KEY_FIELDS = {"common_name": "common_name", "scientific_name": "scientific_name", "elev_min_m": "elev_min_m", "elev_max_m": "elev_max_m",
              "max_slope_pct": "max_slope_pct", "origin": "category", "planting_months": "months_raw"}


@app.get("/species")
def species_list(season=Depends(season_q), d=Depends(D)):
    """All species. With start/end each species gets a season object; with season_filter=only the out-of-season ones are removed."""
    sp, items, ids = d.ctx.species, [], set()
    drop = set(season_drop_ids(d, season))
    for k, r in enumerate(sp.itertuples(index=False)):
        sid = int(r.species_id)
        if sid in drop:
            continue
        fid = {f: d.src_by_sf[(sid, s)] for f, s in KEY_FIELDS.items() if (sid, s) in d.src_by_sf}
        ids |= set(fid.values())
        items.append({"species_id": sid, "common_name": r.common_name, "scientific_name": r.scientific_name, "genus": py(r.genus),
                      "origin": py(r.origin), "elev_min_m": py(r.elev_min_m), "elev_max_m": py(r.elev_max_m),
                      "max_slope_pct": py(r.max_slope_pct), "planting_months": py(r.planting_months), "is_dioecious": py(r.is_dioecious),
                      "confidence": {"share_of_cells_with_rank1_or_2_source": py(r.confidence_r12), "cells_cited": py(r.n_cells_cited),
                                     "cells_rank1_or_2": py(r.n_cells_rank12)},
                      "purpose_scores": {p: {"p_score": py(d.ps_by_key[(sid, p)].p_score), "confidence": py(d.ps_by_key[(sid, p)].confidence)}
                                         for p in mt.PURPOSES},
                      "flags": d.ctx.species_flags.get(sid, []), "source_ids": fid, **species_extras(d, sid),
                      **({"season": season_object(d.species_months[k], season)} if season is not None else {})})
    return {"count": len(items), "species": items, "sources": sources_map(d, ids),
            "note": "GET /species/{species_id} lists every field with its source URL and rank", **season_extra(d, season)}


@app.get("/species/{species_id}")
def species_detail(species_id: int, season=Depends(season_q), d=Depends(D)):
    i = d.species_idx.get(species_id)
    if i is None:
        raise HTTPException(404, f"species_id {species_id} not found (valid ids: {int(d.ctx.species.species_id.min())}-{int(d.ctx.species.species_id.max())})")
    row = d.ctx.species.iloc[i]
    rows = d.sources[d.sources.species_id == species_id]
    sx = {"season": season_object(d.species_months[i], season), "season_window": season_block(d, season)} if season is not None else {}
    fields = [{"field_name": r.field_name, "value_as_written": py(r.value_text), "source_id": int(r.source_id), "source_url": py(r.source_url),
               "source_rank": py(r.source_rank), "rank_basis": py(r.rank_basis), "off_list": py(r.off_list), "flags": py(r.flags)}
              for r in rows.itertuples(index=False)]
    return {**sx, "species_id": species_id, "common_name": row.common_name, "scientific_name": row.scientific_name,
            "confidence": {"share_of_cells_with_rank1_or_2_source": py(row.confidence_r12), "cells_cited": py(row.n_cells_cited),
                           "cells_rank1_or_2": py(row.n_cells_rank12)},
            "flags": d.ctx.species_flags.get(species_id, []),
            "fields": fields, "clean_values": {k: py(v) for k, v in row.items()},
            "provisional_note": "root_urban_safety_prov and root_soil_binding_prov are provisional scores from tag_maps_root.csv, not sourced facts; "
                                "is_high_value_crop is a team decision",
            "reference_urls": d.refs[d.refs.species_id == species_id].reference_url.tolist(),
            **species_extras(d, species_id),
            "purpose_tag_details": d.purpose_tags.get(species_id, []),
            "tags_note": "Purpose tags are filters only (they do not change the urban, planting or watershed scores); provisional, to be confirmed by the agriculturist.",
            "nursery": ([{"listed_name": r["listed_name"], "in_system": r["in_system"], "match_note": r["match_note"], "source": "LGU nursery list (handwritten); quantities unknown"}
                         for r in d.nursery_rows.get(species_id, [])] if d.nursery_table_present else None),
            "interview_notes": d.interview_notes.get(species_id, []),
            "purpose_scores": {p: purpose_breakdown(d, species_id, p) for p in mt.PURPOSES}}


def species_extras(d, sid):
    """purpose_tags, in_nursery and the nursery match for one species (round 15a; provisional, from the tables beside the species table)."""
    tags = d.purpose_tags.get(sid, [])
    rows = d.nursery_rows.get(sid, [])
    return {"purpose_tags": [t["tag"] for t in tags], "in_nursery": bool(rows) if d.nursery_table_present else None,
            "nursery_match": ("partial" if rows and all(r["in_system"] == "partial" for r in rows) else "yes") if rows else None}


PARTNER_NONE = "No good partner found in our data"
PARTNER_NOTE = "These are starting rules from the species data. The agriculturist will check them."


def partners_of(d, species_id):
    """Rows of species_partners.csv for one main species, best first (empty when the table is not built or the species has no listed partner)."""
    if d.partners is None:
        return d.partners
    t = d.partners[d.partners.species_id == species_id]
    if "status" in t:                                                   # pairs that fit first, then the ones named in the sources whose conditions differ (round 15a)
        t = t.assign(_o=(t.status != "fits").astype(int))
        return t.sort_values(["_o", "score", "partner_id"], ascending=[True, False, True]).drop(columns="_o")
    return t.sort_values(["score", "partner_id"], ascending=[False, True])


def partner_pairs_in(d, species_ids):
    """Listed pairs (either direction) among the given species: [(main_id, partner_id)]. Used for the one-line note of a plan with two or more species."""
    ids = {int(i) for i in species_ids}
    if d.partners is None or len(ids) < 2:
        return []
    t = d.partners[d.partners.species_id.isin(ids) & d.partners.partner_id.isin(ids)]
    if "status" in t:
        t = t[t.status == "fits"]                                      # only pairs that fit count as "these species suit each other"
    seen, out = set(), []
    for r in t.sort_values("score", ascending=False).itertuples(index=False):
        k = tuple(sorted((int(r.species_id), int(r.partner_id))))
        if k not in seen:
            seen.add(k)
            out.append((int(r.species_id), int(r.partner_id)))
    return out


def partner_note(d, species_ids):
    """One sentence for a mix of two or more species: do the starting partner rules link any two of them?"""
    ids = list(dict.fromkeys(int(i) for i in species_ids))
    if len(ids) < 2 or d.partners is None:
        return None
    pairs = partner_pairs_in(d, ids)
    names = dict(zip(d.ctx.species.species_id.astype(int), d.ctx.species.common_name))
    if not pairs:
        return {"text": "No partner rule applies", "pairs": [], "provisional": True, "note": PARTNER_NOTE}
    return {"text": "These species suit each other" if len(pairs) >= len(ids) - 1 else "Some of these species suit each other",
            "pairs": [{"species_id": a, "partner_id": b, "species": names.get(a), "partner": names.get(b)} for a, b in pairs[:6]], "provisional": True, "note": PARTNER_NOTE}


@app.get("/species/{species_id}/partners")
def species_partners(species_id: int, purpose: Optional[Purpose] = None, barangay: Optional[str] = Query(None, description="barangay name: adds the squares of that barangay where both species suit"),
                     season=Depends(season_q), d=Depends(D)):
    """Up to 5 partner species ("Works well with") with plain reasons; provisional starting rules (pipeline/partners.py). An explicit empty list when none is found."""
    i = d.species_idx.get(species_id)
    if i is None:
        raise HTTPException(404, f"species_id {species_id} not found (valid ids: {int(d.ctx.species.species_id.min())}-{int(d.ctx.species.species_id.max())})")
    if d.partners is None:
        raise HTTPException(503, "The partner table is not built yet: run python pipeline/partners.py.")
    sp = d.ctx.species
    main = sp.iloc[i]
    mask, area = None, None
    if barangay is not None:
        b = find_barangay(d, barangay)
        if b is None:
            raise HTTPException(400, f"Unknown barangay '{barangay}'. Barangays: {', '.join(d.barangay_display)}")
        mask = d.point_barangay == b
        area = {"name": d.barangay_names[b], "display_name": d.barangay_display[b], "squares": int(mask.sum())}
    text = py(main.plant_partners)
    base = {"species_id": species_id, "common_name": main.common_name, "purpose": purpose, "area": area, "provisional": True, "note": PARTNER_NOTE,
            "sources_say": text, "source_ids": species_field_ids(d, species_id, ["plant_partners"]), "max_partners": 5}
    if season is not None:
        base["season_window"] = season_block(d, season)
    t_all = partners_of(d, species_id)
    t = pd.concat([t_all[t_all.status == "fits"].head(5), t_all[t_all.status != "fits"].head(3)]) if "status" in t_all else t_all.head(5)       # up to 5 that fit, plus the ones named in the sources whose conditions differ
    if len(t) == 0:
        return {**base, "partners": [], "message": PARTNER_NONE}
    out = []
    smin = mt.CFG["s_min"]
    for r in t.itertuples(index=False):
        j = d.species_idx[int(r.partner_id)]
        pr = sp.iloc[j]
        item = {"species_id": int(r.partner_id), "common_name": pr.common_name, "scientific_name": py(pr.scientific_name), "score": py(r.score),
                "reasons": [x for x in str(r.reasons).split(" | ") if x], "source_named": bool(r.source_named), "overlap_share": py(r.overlap_share),
                "status": getattr(r, "status", "fits"), "cautions": [x for x in str(getattr(r, "cautions", "") or "").split(";") if x]}
        if item["status"] != "fits":
            item["label"] = "named in the sources, conditions differ"
        if mask is not None:
            a_, b_ = d.ctx.S[mask][:, i] >= smin, d.ctx.S[mask][:, j] >= smin
            small = min(int(a_.sum()), int(b_.sum()))
            item["overlap_in_area"] = {"squares_both": int((a_ & b_).sum()), "squares_main": int(a_.sum()), "squares_partner": int(b_.sum()),
                                       "share_of_smaller": round(float((a_ & b_).sum() / small), 4) if small else None}
        if season is not None:
            item["season"] = season_object(d.species_months[j], season)
        if purpose is not None:
            item["purpose_fit"] = round(float(d.ctx.P[purpose][j]), 4)
        out.append(item)
    return {**base, "partners": out, "message": ""}


@app.get("/rank")
def rank(purpose: Purpose, lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180),
         limit: int = Query(API_CFG["rank_default_limit"], ge=1, le=100), season=Depends(season_q),
         include_left_out: bool = Query(False, description="true: a point marked not plantable in the field is still ranked (for display only, greyed out) instead of answering 404"),
         explain: bool = Query(False, description="true: always add limiting_factors (otherwise only when fewer than 3 species suit the square)"),
         d=Depends(HD)):
    e, n = d.to_utm.transform(lon, lat)
    dist, i = d.tree_all.query([e, n])
    if dist > d.cfg["nearest_point_max_m"]:
        raise HTTPException(404, f"The nearest grid point is {dist:.0f} m away (limit {d.cfg['nearest_point_max_m']:.0f} m): "
                                 "the coordinate is outside the mapped area of San Mateo.")
    pt = d.all_points.iloc[int(i)]
    if int(pt.point_id) not in d.legal_index:
        zone = py(pt.zone_desc) or "outside the zoning map"
        raise HTTPException(404, f"The nearest grid point (id {int(pt.point_id)}, {dist:.0f} m away) is not in a legal planting zone ({zone}); no ranking is given.")
    j = d.legal_index[int(pt.point_id)]
    if d.ex_mask[j] and not include_left_out:
        c = d.field_current[int(pt.point_id)]
        raise HTTPException(404, f"This point (id {int(pt.point_id)}) was marked not plantable in the field ({c['reason']}) by {c['observer']} on {c['observed_at'][:10]}"
                                 f"{': ' + c['note'] if c['note'] else ''}. It is left out of the ranking. Its history: GET /field-checks/{int(pt.point_id)}.")
    S_row, P = d.ctx.S[j], d.ctx.P[purpose]
    unconf = bool(d.zoning_on and pt.zoning_status == "unconfirmed")
    W, feas = mt.weights(S_row[None, :], P)
    pairs = pair_rows(d, pt.point_id)
    items = []
    for k, sid in enumerate(d.ctx.species.species_id.astype(int)):
        conf, bd = pairs.get(sid, (None, {}))
        items.append((bool(feas[0, k]), float(W[0, k]), float(S_row[k]), k, sid, conf, bd))
    items.sort(key=lambda t: (not t[0], -t[1], -t[2], t[4]))
    n_all = len(items)
    n_suit = sum(t[0] for t in items)
    lf = limiting_factors(d, pt, items, n_suit, explain) if (n_suit < 3 or explain) else None
    gc = ground_cover_block(d, pt.point_id)
    gflags = gc["flags"] if gc else []
    hab_on = bool(getattr(d, "hab", None) and d.hab_mask[j])           # Habagat: this square lies in a Habagat barangay and the window touches Jul-Sep
    drop = set(season_drop_ids(d, season))
    if drop:                                                          # season_filter=only: out-of-season species are not ranked
        items = [t for t in items if t[4] not in drop]
    out, ids = [], set()
    for rnk, (el, w, s, k, sid, conf, bd) in enumerate(items[:limit], 1):
        terms = {t: {"value": v["value"], "weight": v["weight"], "sources": [source(d, x) for x in v["src"]]} for t, v in bd.get("terms", {}).items()}
        out.append({"rank": rnk, "species_id": sid, "common_name": d.ctx.species.common_name.iloc[k], "S": round(s, 4), "P": round(float(P[k]), 4),
                    "W": round(w, 4), "eligible": el, "confidence": py(conf), "flags": flags_for(d, sid, bd, conf) + (["zoning_unconfirmed"] if unconf else []) + gflags + sr.rehab_flags(pt.zone_desc, sid, d.food_ids) + ([sr.HABAGAT_FLAG] if hab_on else []),
                    "site_breakdown": {"gate_failed": bd.get("gate_failed", []), "terms": terms},
                    "purpose_breakdown": purpose_breakdown(d, sid, purpose),
                    **({"habagat": {"multiplier": d.hab["multiplier"], "S_before": round(float(d.base_ctx.S[j, k]), 4), "W_before": round(float(mt.weights(d.base_ctx.S[j][None, :], P)[0][0, k]), 4), "months_hit": d.hab["months_hit"],
                                 "warning": sr.HABAGAT_WARNING, "source": d.hab["source"], "provisional": True}} if hab_on else {}),
                    **({"season": season_object(d.species_months[k], season)} if season is not None else {})})
    return {"purpose": purpose, "query": {"lat": lat, "lon": lon},
            "point": {"point_id": int(pt.point_id), "lon": py(pt.lon), "lat": py(pt.lat), "utm_e": py(pt.utm_e), "utm_n": py(pt.utm_n),
                      "distance_m": round(float(dist), 1), "zone": py(pt.zone_desc), "elev_m": py(pt.elev_m), "slope_pct": py(pt.slope_pct),
                      "slope_method": py(pt.slope_method), "soil_texture_legacy": py(pt.soil_texture_legacy),
                      "soil_mapping_status": py(pt.soil_mapping_status),
                      **({"zoning_status": py(pt.zoning_status),
                          "zoning_note": ((f"{pt.zone_desc}: confirm with the LGU before planting" if isinstance(pt.zone_desc, str) else UNZONED_NOTE)
                                          if unconf else "Inside a legal planting zone")} if d.zoning_on else {}),
                      **soil_facts(pt),
                      **({"zone_condition": py(pt.zone_condition)} if "zone_condition" in d.all_points and isinstance(pt.zone_condition, str) and pt.zone_condition else {}),
                      **({"rehab_site": {"zone": py(pt.zone_desc), "warning": sr.REHAB_WARNING, "applies_to": "food-bearing species", "source": sr.REHAB_SOURCE}} if sr.rehab_zone(py(pt.zone_desc)) else {}),
                      **({"habagat": d.hab} if hab_on else {}),
                      "site_inputs_source": "backend/Working_Points.csv (elevation); slope by finite differences on elevation; soil texture = " + (
                          "the LGU soil map (BSWM), digitized by us, provisional" if "soil_texture_lgu" in d.all_points else "legacy mapping (unverified)"),
                      **({"ground_cover": gc} if gc is not None else {})},
            "species_eligible": int(sum(t[0] for t in items)), "species_total": n_all, "returned": len(out), "ranking": out,
            "limits": limits_of(d), "w_definition": "W = S x P if S >= 0.50 else 0", **field_extra(d, int(pt.point_id)), **season_extra(d, season),
            **({"left_out_by_field_check": True} if d.ex_mask[j] else {}), **({"limiting_factors": lf} if lf else {})}


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
            "ranking": items, "sources": sources_map(d, ids), "limits": limits_of(d)}


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
    out = [{"type": "barangay", "name": p["name"], "display_name": p["display_name"], "centroid": p["centroid"], "bounds": p["bounds"],
            "bounds_order": "minlon,minlat,maxlon,maxlat", "source": "data/BRGY_BOUNDARY.shp (BRGY_NAME)"}
           for p in d.places if key in p["key"]]
    return {"query": q, "normalised_query": key, "count": len(out), "results": out[:d.cfg["search_max_results"]],
            "note": "Sta -> Santa, Sto -> Santo; accents and punctuation are ignored"}


@app.get("/nearest-viable")
def nearest_viable(purpose: Purpose, lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180), season=Depends(season_q), d=Depends(HD)):
    ctx, cfg = d.ctx, d.cfg
    e, n = d.to_utm.transform(lon, lat)
    W, feas = mt.weights(ctx.S, ctx.P[purpose])
    drop = season_drop_ids(d, season)
    if drop:                                                          # season_filter=only: only species that can be planted in the window count
        gone = np.isin(ctx.species.species_id.to_numpy(dtype=int), list(drop))
        if gone.all():
            raise HTTPException(404, f"No species can be planted between {day_text(season.start)} and {day_text(season.end)}, so no suitable spot can be offered. "
                                     "Change the dates or show all species.")
        W, feas = np.where(gone[None, :], 0.0, W), feas & ~gone[None, :]
    viable = feas.any(axis=1) & ~d.ex_mask                          # a point marked not plantable is never offered

    def best(j):
        k = int(np.argmax(np.where(feas[j], W[j], -1.0)))
        sid = int(ctx.species.species_id.iloc[k])
        return {"species_id": sid, "common_name": ctx.species.common_name.iloc[k], "S": round(float(ctx.S[j, k]), 4),
                "P": round(float(ctx.P[purpose][k]), 4), "W": round(float(W[j, k]), 4),
                **({"season": season_object(d.species_months[k], season)} if season is not None else {}),
                "source_ids": {"site_score": species_field_ids(d, sid, [f for fs in ss.TERM_FIELDS.values() for f in fs]),
                               "purpose_score": purpose_source_ids(d, sid, purpose)}}

    def point(j, dist, ring, already):
        r = ctx.sites.iloc[j]
        b = best(j)
        ids = set(b["source_ids"]["site_score"]) | set(b["source_ids"]["purpose_score"])
        return {"purpose": purpose, "query": {"lat": lat, "lon": lon}, "already_viable": already, "search_ring": ring,
                "ring_step_m": cfg["ring_step_m"], "distance_m": round(float(dist), 1),
                "direction": None if already else compass(r.utm_e - e, r.utm_n - n),
                "point": {"point_id": int(r.point_id), "lon": py(r.lon), "lat": py(r.lat), "utm_e": py(r.utm_e), "utm_n": py(r.utm_n), "zone": py(r.zone_desc),
                          **({"zoning_status": py(r.zoning_status)} if d.zoning_on else {})},
                "best_species": b, "sources": sources_map(d, ids), "limits": limits_of(d), **season_extra(d, season)}

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


CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=80, description="campaign name, 1 to 80 characters")
    unit: Optional[str] = Field(None, max_length=80, description="assigned unit (free text, up to 80 characters)")

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("the campaign name cannot be empty")
        if CONTROL_CHARS.search(v):
            raise ValueError("the campaign name cannot contain control characters")
        return v

    @field_validator("unit")
    @classmethod
    def _unit(cls, v):
        v = (v or "").strip()
        if CONTROL_CHARS.search(v):
            raise ValueError("the assigned unit cannot contain control characters")
        return v


class PlanRequest(BaseModel):
    purpose: Purpose
    n_saplings: Optional[int] = Field(None, ge=API_CFG["plan_min_saplings"], le=API_CFG["plan_max_saplings"], description="total trees (the automatic mix), or leave it out and send species_counts")
    species_counts: Optional[dict[int, int]] = Field(None, description="trees per species, {species_id: trees}: exactly these counts are placed (the 20% / 30% caps do not apply); "
                                                                       "each at least 1, total 1 to 2000 (in points mode every tree has its own square)")
    polygon: Optional[dict] = Field(None, description="GeoJSON Polygon / MultiPolygon (or a Feature holding one), lon/lat")
    zone: Optional[str] = Field(None, description="zone_desc, e.g. 'Forest Zone'")
    barangay: Optional[str] = Field(None, description="barangay name (as written, or the display name, e.g. 'Santa Ana')")
    seed: Optional[int] = None
    campaign: Optional[CampaignIn] = Field(None, description="campaign name and assigned unit, saved with the plan")
    species_ids: Optional[list[int]] = Field(None, min_length=1, max_length=60, description="plan with only these species (caps are relaxed to the minimum needed)")
    layout_mode: Optional[Literal["blocks", "points"]] = Field(None, description="blocks (default): n_saplings = total TREES, planted in blocks (one 100 m square per block, species spacing); "
                                                                                 "points: one tree per square, exactly the plan of before")

    @model_validator(mode="after")
    def _ways_to_ask(self):
        """n_saplings (automatic mix) or species_counts (counts by hand), never a mix of the two ways."""
        lo, hi = API_CFG["plan_min_saplings"], API_CFG["plan_max_saplings"]
        if self.species_counts:
            c = self.species_counts
            if len(c) > 60:
                raise ValueError("species_counts can name at most 60 species")
            if any(v < 1 for v in c.values()):
                raise ValueError("Every species in species_counts needs at least 1 tree")
            tot = sum(c.values())
            if not lo <= tot <= hi:
                raise ValueError(f"The total of species_counts must be {lo} to {hi} trees (it is {tot})")
            if self.n_saplings is not None and int(self.n_saplings) != tot:
                raise ValueError(f"n_saplings ({self.n_saplings}) is not the total of species_counts ({tot}): send only one of them")
            if self.species_ids and set(self.species_ids) != set(c):
                raise ValueError("species_ids and species_counts name different species: send only species_counts")
            self.n_saplings = tot
            self.species_ids = list(c)
        elif self.n_saplings is None:
            raise ValueError("Send n_saplings (the automatic mix) or species_counts (trees per species)")
        return self


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


def campaign_info(s):
    """The campaign of a saved plan. A plan made before campaigns existed has no name/unit: they come back as null and are listed in `missing` (never an error)."""
    c, se = s.get("campaign"), s.get("season") or {}
    start = (c or {}).get("start") or se.get("start")
    end = (c or {}).get("end") or se.get("end")
    out = {"status": "saved" if c else "missing", "name": c["name"] if c else None, "unit": c.get("unit", "") if c else None, "start": start, "end": end}
    out["missing"] = [k for k in ("name", "unit", "start", "end") if out[k] is None]
    return out


def block_geometry_fields(r):
    """The planted rectangle of a block from the ONE shared function (pipeline/palettes.block_geometry): side and margin in metres, tree 1 from the square's south-west corner."""
    g = pal.block_geometry(float(r.spacing_m), int(r.trees_per_row), int(r.rows), int(r.trees_planned))
    return {"rect_side_m": round(g["rect_side_m"], 3), "margin_m": round(g["margin_m"], 3), "first_tree_m": [round(g["first_tree"][0], 3), round(g["first_tree"][1], 3)]}


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
    refs = {pid: ref for ref, pid in fv.plan_point_refs(plan, d.ctx.species).items()}
    blocks = "trees_planned" in plan.columns
    if blocks:
        for it, r in zip(items, plan.itertuples(index=False)):
            it.update({"trees_planned": int(r.trees_planned), "spacing_m": py(r.spacing_m), "rows": int(r.rows), "trees_per_row": int(r.trees_per_row), "capacity": int(r.capacity),
                       "usable_side_m": py(r.usable_side_m), "row_direction": r.row_direction, "start_corner": r.start_corner,
                       "layout_note": r.layout_note if isinstance(r.layout_note, str) else "", **block_geometry_fields(r)})
    for it in items:
        ref = refs[it["point_id"]]
        if blocks:
            it["block_ref"] = ref
        j = d.allpt_index.get(it["point_id"])                          # all grid squares (a saved plan may hold squares the current view does not score)
        b = int(d.allpt_barangay[j]) if j is not None else -1
        it.update({"point_ref": ref, "species_code": ref.split("-")[0], "barangay": d.barangay_names[b] if b >= 0 else "",
                   "barangay_display": d.barangay_display[b] if b >= 0 else ""})
        if j is not None and "zone_condition" in d.all_points:                         # round 15a: the MPDC condition of the zone, when there is one
            zc = d.all_points.zone_condition.iloc[j]
            if isinstance(zc, str) and zc:
                it["zone_condition"] = zc
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
           "sources": sources_map(d, ids), "limits": list(dict.fromkeys(summary.get("limits", []) + limits_of(d))),
           "campaign": campaign_info(summary), "n_species": len(summary["palette"]), "n_placed": summary["saplings_placed"],
           "layout_mode": "blocks" if blocks else "points", "parent_plan_id": summary.get("parent_plan_id")}
    pn = partner_note(d, [p["species_id"] for p in summary["palette"]])
    if pn is not None:
        out["partners"] = pn
    if blocks:
        out["blocks"] = {"trees": int(summary.get("saplings_placed", 0)), "blocks": int(len(items)), "hectares": (summary.get("layout") or {}).get("hectares_used")}
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


def plan_scope(d, req, season, strict=True, extra_exclude_ids=None):
    """The planting squares and species a plan request can use: the area (barangay / zone / polygon), the season rules, the field-check exclusions and the chosen species.
    strict=True raises the plain-words 4xx errors of POST /plan-event; strict=False (the preview) reports an empty season in `empty` instead."""
    ctx = d.ctx
    if req.zone:
        zones = {z.strip().lower() for z in ctx.sites.zone_desc.dropna()}
        if req.zone.strip().lower() not in zones:
            raise HTTPException(400, f"Unknown zone '{req.zone}'. Legal zones: {sorted(ctx.sites.zone_desc.dropna().unique())}")
    sub = ctx
    mask = np.ones(len(ctx.sites), dtype=bool)
    area = {"type": "zone" if req.zone else "municipality", "name": req.zone or "San Mateo", "display_name": req.zone or "The whole municipality"}
    if req.barangay is not None:
        b_ = find_barangay(d, req.barangay)
        if b_ is None:
            raise HTTPException(400, f"Unknown barangay '{req.barangay}'. Barangays: {', '.join(d.barangay_display)}")
        mask &= d.point_barangay == b_
        area = {"type": "barangay", "name": d.barangay_names[b_], "display_name": d.barangay_display[b_] + (f", {req.zone}" if req.zone else "")}
    if req.polygon is not None:
        m = polygon_mask(ctx.sites, req.polygon, d.cfg["polygon_max_vertices"])
        if not m.any():
            raise HTTPException(400, "The polygon contains no legal-zone grid points (it may lie outside San Mateo or only cover non-planting zones).")
        mask &= m
        area = {"type": "polygon", "name": "Drawn area", "display_name": "Drawn area" + (f", {req.zone}" if req.zone else "")}
    if not mask.any():
        raise HTTPException(400, "The area contains no planting-zone grid points.")
    if req.barangay is not None or req.polygon is not None:
        sub = dataclasses.replace(ctx, sites=ctx.sites[mask].reset_index(drop=True), S=ctx.S[mask])
    family_dropped = 0
    if extra_exclude_ids:                                             # a top-up never reuses a square of its plan family
        gone = sub.sites.point_id.isin(extra_exclude_ids).to_numpy()
        family_dropped = int(gone.sum())
        if gone.any():
            sub = dataclasses.replace(sub, sites=sub.sites[~gone].reset_index(drop=True), S=sub.S[~gone])
        if len(sub.sites) == 0:
            raise HTTPException(400, "Every planting square of this area is already used by the parent plan (or its top-ups), so no top-up can be made here.")
    excluded_in_area = 0
    if d.field_ex_ids:                                                # points marked not plantable in the field are never planned
        gone = sub.sites.point_id.isin(d.field_ex_ids).to_numpy()
        in_zone = (sub.sites.zone_desc.fillna("").str.strip().str.lower() == req.zone.strip().lower()).to_numpy() if req.zone else np.ones(len(sub.sites), dtype=bool)
        excluded_in_area = int((gone & in_zone).sum())
        if gone.any():
            sub = dataclasses.replace(sub, sites=sub.sites[~gone].reset_index(drop=True), S=sub.S[~gone])
        if len(sub.sites) == 0:
            raise HTTPException(400, "Every planting point of this area is marked not plantable in the field, so no plan can be made.")
    ids_req = list(dict.fromkeys(req.species_ids)) if req.species_ids else None
    if ids_req:
        unknown = [i for i in ids_req if i not in d.species_idx]
        if unknown:
            raise HTTPException(404, f"species_id {unknown} not found (valid ids: {int(ctx.species.species_id.min())}-{int(ctx.species.species_id.max())}). Choose species from the species list.")
    drop = season_drop_ids(d, season)
    ids_kept, removed, empty, message = ids_req, [], None, ""
    if ids_req and drop:
        removed = [i for i in ids_req if i in drop]
        ids_kept = [i for i in ids_req if i not in drop]
    if drop:                                                          # season_filter=only: species out of season are left out, planting months cut to the window
        sub = season_ctx(sub, season, drop)
        if len(sub.species) == 0:
            empty = "no_species_in_season"
            message = (f"Every species is out of season between {day_text(season.start)} and {day_text(season.end)}, so no plan can be made. "
                       "Change the dates, or send season_filter=mark to plan anyway and see the season labels.")
        elif ids_req and not ids_kept:
            empty = "chosen_species_outside_best_months"
            message = (f"None of your chosen species can be planted between {day_text(season.start)} and {day_text(season.end)} (all are outside their best months). "
                       "Change the dates, choose other species, or send season_filter=mark.")
    if empty and strict:
        raise HTTPException(400, message)
    return SimpleNamespace(sub=sub, season=season, drop=drop, excluded_in_area=excluded_in_area, ids_req=ids_req, ids_kept=ids_kept, removed=removed, area=area,
                           empty=empty, message=message, family_dropped=family_dropped)


@app.post("/plan-event/preview")
def plan_preview(req: PlanRequest, q_season=Depends(season_q), d=Depends(HD)):
    """What a plan request could use, WITHOUT creating or saving anything: suitable squares in the area, species available, field-check exclusions and whether a plan can be made."""
    sc = plan_scope(d, req, q_season, strict=False)
    sub, n = sc.sub, int(req.n_saplings)
    smin = mt.CFG["s_min"]
    cols = [k for k, sid in enumerate(sub.species.species_id.astype(int)) if sc.ids_kept is None or sid in set(sc.ids_kept)]
    suitable = int((sub.S[:, cols] >= smin).any(axis=1).sum()) if cols else 0
    species_available = int((sub.S[:, cols] >= smin).any(axis=0).sum()) if cols else 0
    layout = req.layout_mode or d.cfg["layout_mode"]
    can, reason, message = True, "", ""
    est = None
    if layout == "blocks" and cols and suitable:
        avail = (sub.S[:, cols] >= smin).any(axis=0)
        bt = pal.block_table(sub.species.iloc[cols].reset_index(drop=True))
        caps = bt.capacity.to_numpy(dtype=float)[avail & np.isfinite(bt.capacity.to_numpy(dtype=float))]
        if len(caps):
            typ = int(np.median(caps))
            bc = pal.BLOCK_CFG
            about = int(math.ceil(n / typ))
            est = {"trees": n, "typical_trees_per_block": typ, "min_trees_per_block": int(caps.min()), "max_trees_per_block": int(caps.max()),
                   "blocks_about": about, "blocks_low": int(math.ceil(n / caps.max())), "blocks_high": int(math.ceil(n / caps.min())),
                   "hectares_about": round(about * bc["block_side_m"] ** 2 / bc["hectare_m2"], 2),
                   "basis": "typical = the median trees per full block of the species that have a suitable square in this area; the real count depends on the species mix the plan chooses"}
    if getattr(req, "species_counts", None) and layout == "blocks":
        bt_all = pal.block_table(d.ctx.species).set_index("species_id")
        names_ = dict(zip(d.ctx.species.species_id.astype(int), d.ctx.species.common_name))
        per_ = []
        for sid_, cnt_ in req.species_counts.items():
            cap_ = bt_all.capacity.get(int(sid_)) if int(sid_) in bt_all.index else None
            ok_ = cap_ is not None and cap_ == cap_
            per_.append({"species_id": int(sid_), "species": names_.get(int(sid_), str(sid_)), "trees": int(cnt_), "capacity": int(cap_) if ok_ else None,
                         "blocks": int(math.ceil(cnt_ / cap_)) if ok_ else None})
        nb_ = sum(x["blocks"] or 0 for x in per_)
        bc_ = pal.BLOCK_CFG
        est = {"trees": n, "typical_trees_per_block": max(1, round(n / nb_)) if nb_ else 1, "min_trees_per_block": 1, "max_trees_per_block": n, "blocks_about": nb_, "blocks_low": nb_, "blocks_high": nb_, "hectares_about": round(nb_ * bc_["block_side_m"] ** 2 / bc_["hectare_m2"], 2),
               "per_species": per_, "basis": "exact: blocks of a species = trees of the species divided by its trees per full block, rounded up"}
    if sc.empty:
        can, reason, message = False, sc.empty, sc.message
    elif suitable == 0:
        can, reason, message = False, "no_suitable_squares", "No square of this area is suitable (S >= 0.50) for the species available, so no plan can be made."
    elif layout == "blocks" and est is None:
        can, reason, message = False, "no_species_with_spacing", "None of the species available has a planting distance, so no plan in blocks can be made."
    if layout == "blocks" and est is not None:
        cap = {"n_saplings": n, "unit": "trees", "max_placeable": suitable * est["typical_trees_per_block"], "max_placeable_blocks": suitable,
               "short": est["blocks_about"] > suitable,
               "message": (f"Only {suitable} suitable squares: at most {suitable} blocks (about {suitable * est['typical_trees_per_block']} trees) can be placed"
                           if est["blocks_about"] > suitable else "")}
    else:
        cap = {"n_saplings": n, "unit": "squares", "max_placeable": suitable, "short": n > suitable,
               "message": (f"Only {suitable} suitable squares: at most {suitable} trees can be placed" if 0 < suitable < n else "")}
    return {"can_create": can, "reason": reason, "message": message, "layout_mode": layout, "blocks_estimate": est,
            "area": {**sc.area, "candidate_squares": int(len(sub.sites)), "suitable_squares": suitable},
            "capacity": cap,
            "species": {"mode": "chosen" if sc.ids_req else "auto", "requested": sc.ids_req, "removed_by_season": sc.removed, "available": species_available,
                        "total": int(len(d.ctx.species))},
            "excluded_by_field_checks": sc.excluded_in_area,
            **season_extra(d, q_season, sc.ids_req)}


def request_snapshot(d, req, season, layout, seed):
    """The settings of a blocks plan, saved in its summary so that a top-up can repeat them (same area, species, dates, campaign and views)."""
    return {"purpose": req.purpose, "n_saplings": int(req.n_saplings), "layout_mode": layout, "zone": req.zone, "barangay": req.barangay, "polygon": req.polygon, "seed": seed,
            "species_ids": list(req.species_ids) if req.species_ids else None,
            "species_counts": {str(k): int(v) for k, v in req.species_counts.items()} if getattr(req, "species_counts", None) else None,
            "campaign": {"name": req.campaign.name, "unit": req.campaign.unit or ""} if req.campaign is not None else None,
            "start": season.start.isoformat() if season else None, "end": season.end.isoformat() if season else None,
            "season_filter": season.filter if season else None, "include_unzoned": bool(d.zoning_on)}


def create_plan(d, req, season, sc, seed, layout, species_trees=None, topup=None):
    """Make, complete and save one plan (POST /plan-event and POST /plans/{id}/top-up). topup = {parent_plan_id, ...} marks a top-up plan."""
    sub = sc.sub
    counts = getattr(req, "species_counts", None) or None
    if counts:
        names = dict(zip(d.ctx.species.species_id.astype(int), d.ctx.species.common_name))
        if sc.removed:
            who = ", ".join(names.get(i, str(i)) for i in sc.removed)
            raise HTTPException(400, f"{who} {'is' if len(sc.removed) == 1 else 'are'} outside the best months for these dates, so the tree counts cannot be placed. "
                                     "Change the dates, take the species out, or turn off 'Only species for my dates'.")
    try:
        plan, summary = rp.make_plan(sub, req.purpose, req.n_saplings, zone=req.zone, seed=seed, species_ids=sc.ids_kept, layout_mode=layout, species_trees=species_trees,
                                     species_counts=counts)
    except ValueError as ex:
        raise HTTPException(400, f"{ex}" + (" (the zone has no legal points inside the polygon)" if req.zone and req.polygon is not None else ""))
    if not summary["palette"]:
        if sc.ids_req:
            raise HTTPException(400, "None of your chosen species can be planted in this area (no planting square has a suitability of 0.50 or more for them, or they share no "
                                     "planting month). Choose other species or another area. " + " ".join(summary["palette_warnings"]).strip())
        raise HTTPException(400, "No species has eligible points (S >= 0.50) in this area, so no plan can be made. "
                                 f"{' '.join(summary['palette_warnings'])}".strip())
    summary["area_choice"] = sc.area
    if season is not None:
        summary["season"] = plan_season(d, season, summary)
        for p_ in summary["palette"]:
            p_["season"] = season_object(d.species_months[d.species_idx[p_["species_id"]]], season)
    if req.campaign is not None:
        summary["campaign"] = {"name": req.campaign.name, "unit": req.campaign.unit or "", "start": season.start.isoformat() if season else None,
                               "end": season.end.isoformat() if season else None}
    if sc.ids_req and not topup:
        summary.setdefault("species_selection", {})["species_ids_removed_by_season"] = sc.removed
    summary["field_checks"] = {"exclude_not_plantable": bool(d.cfg["field_exclude_not_plantable"]), "excluded_points": sc.excluded_in_area,
                               "note": "Points whose latest field check is not_plantable were left out of this plan." if d.cfg["field_exclude_not_plantable"]
                               else "The field-check switch is off: not_plantable points were NOT left out."}
    if d.zoning_on:                                                   # how many placed trees stand on land outside the zoning map
        summary["zoning"] = rp.zoning_block(True, plan)
    if layout == "blocks":
        summary["request"] = request_snapshot(d, req, season, layout, seed)
    if topup:
        summary["parent_plan_id"] = topup["parent_plan_id"]
        summary["topup"] = {k: v for k, v in topup.items() if k != "parent_plan_id"}
        summary["palette_warnings"] = []                               # the species mix of a top-up is fixed by what was lost, so the usual diversity notes do not apply
        summary.pop("species_selection", None)
    plan = field_flags_for_plan(d, plan)
    if getattr(d, "hab", None):                                        # planting window touches Jul-Sep: the Habagat multiplier was applied to the squares of the Habagat barangays
        plan, n_hab = habagat_flags_for_plan(d, plan)
        summary["habagat"] = {**d.hab, "affected_trees": n_hab}
        if n_hab:
            summary["palette_warnings"] = list(summary.get("palette_warnings", [])) + [sr.HABAGAT_WARNING]
    plan_id, f, sj = save_plan(d, req.purpose, plan, summary)
    return render_plan(d, plan, summary, plan_id,
                       {"saved": {"plan_csv": f.name, "summary_json": sj.name, "folder": f"{d.cfg['data_dir']}/{rp.CFG['plans_dir']}"},
                        "next": {"plan": f"/plans/{plan_id}", "build_field_kit": f"POST /plans/{plan_id}/field-kit"},
                        **({"season": summary["season"]} if "season" in summary else {})})


@app.post("/plan-event")
def plan_event(req: PlanRequest, q_season=Depends(season_q), d=Depends(HD)):
    seed = d.cfg["default_seed"] if req.seed is None else req.seed
    layout = req.layout_mode or d.cfg["layout_mode"]
    sc = plan_scope(d, req, q_season, strict=True)
    return create_plan(d, req, q_season, sc, seed, layout)


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
                      "campaign": campaign_info(s), "n_species": len(s.get("palette") or []),
                      "field_kit_built": kit_zip_path(d, plan_id).is_file(), "layout_mode": s.get("layout_mode", "points"), "parent_plan_id": s.get("parent_plan_id"),
                      "blocks": (s.get("layout") or {}).get("blocks")})
    items.sort(key=lambda x: (x["date"], x["plan_id"]), reverse=True)
    return {"count": len(items[:limit]), "total_saved": len(items), "plans": items[:limit]}


@app.get("/plans/{plan_id}")
def plan_get(plan_id: str, d=Depends(D)):
    csv, js = plan_files(d, plan_id)
    plan = pd.read_csv(csv)
    summary = json.loads(js.read_text(encoding="utf-8"))
    return render_plan(d, plan, summary, plan_id,
                       {"saved": {"plan_csv": csv.name, "summary_json": js.name}, "field_kit_built": kit_zip_path(d, plan_id).is_file(), "child_plan_ids": plan_children(d, plan_id),
                        "next": {"build_field_kit": f"POST /plans/{plan_id}/field-kit", "download": f"/kits/{plan_id}.zip"}})


# ---------------------------------------------------------------------------------------------------------------------
# progress of a plan in blocks, top-up plans and the block model
# ---------------------------------------------------------------------------------------------------------------------
PROGRESS_STATES = ("done", "partly", "problem", "to_do")


def plan_parents(d):
    """{plan_id: parent_plan_id or None} of every saved plan."""
    root = plans_dir(d)
    out = {}
    for sj in (root.glob("plan_*_summary.json") if root.is_dir() else []):
        pid = sj.name[:-len("_summary.json")]
        if not valid_plan_id(pid) or not (root / f"{pid}.csv").is_file():
            continue
        try:
            out[pid] = json.loads(sj.read_text(encoding="utf-8")).get("parent_plan_id")
        except (ValueError, OSError):
            continue
    return out


def plan_children(d, plan_id):
    return sorted(pid for pid, par in plan_parents(d).items() if par == plan_id)


def plan_family(d, plan_id):
    """(root plan id, set of every plan id of the family: the root, its top-ups and their top-ups)."""
    parents = plan_parents(d)
    r, seen = plan_id, set()
    while parents.get(r) and r not in seen:
        seen.add(r)
        r = parents[r]
    fam, grew = {r}, True
    while grew:
        grew = False
        for pid, par in parents.items():
            if par in fam and pid not in fam:
                fam.add(pid)
                grew = True
    return r, fam


def load_plan(d, plan_id):
    csv, js = plan_files(d, plan_id)
    return pd.read_csv(csv), json.loads(js.read_text(encoding="utf-8"))


def block_progress(d, plan_id, plan):
    """The progress of a plan in blocks from the append-only field checks. Per block the latest relevant event wins: planted only counts for THIS plan, not_plantable / needs_recheck /
    verified_plantable are facts about the square. States: done (all trees planted), partly (some), problem (not plantable), to_do (nothing planted yet)."""
    refs = {pid: ref for ref, pid in fv.plan_point_refs(plan, d.ctx.species).items()}
    latest = fv.latest_for_plan(d.field_db, plan_id, plan.point_id.astype(int).tolist())
    blocks = []
    for r in plan.itertuples(index=False):
        pid, planned = int(r.point_id), int(r.trees_planned)
        ev = latest.get(pid)
        st = ev["status"] if ev else None
        planted = int(ev["trees_planted"] or 0) if st == "planted" else 0
        if st == "not_plantable":
            state = "problem"
        elif st == "planted" and planted >= planned:
            state = "done"
        elif st == "planted" and planted > 0:
            state = "partly"
        else:
            state = "to_do"
        blocks.append({"point_id": pid, "block_ref": refs[pid], "species_id": int(r.species_id), "species": r.species, "trees_planned": planned, "trees_planted": planted,
                       "state": state, "field_status": st, "reason": ev["reason"] if ev else None, "observer": ev["observer"] if ev else None,
                       "observed_at": ev["observed_at"] if ev else None, "note": ev["note"] if ev else None,
                       "needs_recheck": st == "needs_recheck"})
    return blocks


def progress_report(d, plan_id, plan, summary):
    if not fv.is_blocks_plan(plan):
        raise HTTPException(400, "This plan was made in points mode (one tree per square). Progress and top-up only exist for plans in blocks.")
    blocks = block_progress(d, plan_id, plan)
    n_state = {k: sum(1 for b in blocks if b["state"] == k) for k in PROGRESS_STATES}
    planned = sum(b["trees_planned"] for b in blocks)
    planted = sum(b["trees_planted"] for b in blocks)
    problem_trees = sum(b["trees_planned"] for b in blocks if b["state"] == "problem")
    remaining = planned - planted - problem_trees
    per = {}
    for b in blocks:
        e = per.setdefault(b["species_id"], {"species_id": b["species_id"], "species": b["species"], "planned": 0, "planted": 0, "problem_trees": 0, "remaining": 0, "blocks": 0,
                                             "blocks_done": 0, "blocks_partly": 0, "blocks_problem": 0, "blocks_to_do": 0})
        e["planned"] += b["trees_planned"]
        e["planted"] += b["trees_planted"]
        e["blocks"] += 1
        e["blocks_" + b["state"]] += 1
        if b["state"] == "problem":
            e["problem_trees"] += b["trees_planned"]
        else:
            e["remaining"] += b["trees_planned"] - b["trees_planted"]
    return {"plan_id": plan_id, "layout_mode": "blocks", "campaign": campaign_info(summary), "parent_plan_id": summary.get("parent_plan_id"), "child_plan_ids": plan_children(d, plan_id),
            "trees": {"planned": planned, "planted": planted, "remaining": remaining, "problem": problem_trees,
                      "percent_planted": round(100.0 * planted / planned, 1) if planned else 0.0},
            "blocks": {"total": len(blocks), "done": n_state["done"], "partly": n_state["partly"], "problem": n_state["problem"], "to_do": n_state["to_do"]},
            "shortfall": {"trees": problem_trees, "blocks": n_state["problem"],
                          "note": "The shortfall is the trees of the blocks marked not plantable. Trees that are not planted yet are 'remaining', not shortfall."},
            "per_species": sorted(per.values(), key=lambda e: e["species_id"]), "blocks_list": blocks,
            "definitions": {"done": "every tree of the block is planted", "partly": "some trees are planted", "problem": "the block cannot be planted (latest check: not plantable)",
                            "to_do": "nothing planted yet", "remaining": "planned - planted - problem trees"}}


@app.get("/plans/{plan_id}/progress")
def plan_progress(plan_id: str, d=Depends(D)):
    """How far a plan in blocks is planted, from the saved field checks (latest relevant event of each block)."""
    plan, summary = load_plan(d, plan_id)
    return progress_report(d, plan_id, plan, summary)


class TopUpIn(BaseModel):
    include_remaining: bool = Field(False, description="also plan the trees that are not planted yet (not only the trees of the problem blocks)")
    seed: Optional[int] = None


@app.post("/plans/{plan_id}/top-up")
def plan_top_up(plan_id: str, request: Request, body: Optional[TopUpIn] = None, d=Depends(D)):
    """A new plan for the trees a plan lost (blocks marked not plantable) and, optionally, the trees still to plant. Same campaign, dates and settings; the name is
    '<campaign> (top-up N)'; squares of the parent plan (and of its other top-ups) and squares marked not plantable are never used; parent_plan_id is saved with the new plan."""
    body = body or TopUpIn()
    plan, summary = load_plan(d, plan_id)
    snap = summary.get("request")
    if not fv.is_blocks_plan(plan) or not snap:
        raise HTTPException(400, "Only plans made in blocks can be topped up (this plan is in points mode or was saved without its settings).")
    base = request.app.state.data
    if getattr(base, "views", None):                                   # the view the parent plan was made in (squares outside the zoning map or not)
        d = base.views[bool(snap.get("include_unzoned", d.zoning_on))]
    prog = progress_report(d, plan_id, plan, summary)
    want = {}
    for e in prog["per_species"]:
        n = e["problem_trees"] + (e["remaining"] if body.include_remaining else 0)
        if n > 0:
            want[e["species_id"]] = n
    _, fam = plan_family(d, plan_id)
    covered = {}
    for child in plan_children(d, plan_id):                            # trees an earlier top-up of this plan already planned: never plan them twice
        cp, _ = load_plan(d, child)
        if "trees_planned" in cp.columns:
            for sid, n in cp.groupby("species_id").trees_planned.sum().items():
                covered[int(sid)] = covered.get(int(sid), 0) + int(n)
    short = {sid: n - covered.get(sid, 0) for sid, n in want.items() if n - covered.get(sid, 0) > 0}
    if not short:
        raise HTTPException(400, ("Nothing to top up: no block of this plan is marked not plantable." if not body.include_remaining and not covered else
                                  "Nothing to top up: the trees that were lost are already covered by an earlier top-up of this plan." if covered else
                                  "Nothing to top up: every tree of this plan is planted."))
    used = set()
    for fid in fam:
        fp = pd.read_csv(plan_files(d, fid)[0], usecols=["point_id"])
        used |= set(fp.point_id.astype(int))
    season = None
    if snap.get("start") and snap.get("end"):
        season = parse_season(d.cfg, snap["start"], snap["end"], snap.get("season_filter") or "mark")
    d = habagat_data(d, season)                                        # the same Habagat adjustment the parent plan was made with
    camp = snap.get("campaign")
    root_id, _ = plan_family(d, plan_id)
    root_summary = load_plan(d, root_id)[1] if root_id != plan_id else summary
    root_camp = (root_summary.get("request") or {}).get("campaign") or camp
    n_top = len(fam)                                                   # the root plan counts as 1, so the first top-up is 1
    label = f" (top-up {n_top})"
    cname = None
    if root_camp:
        cname = root_camp["name"][:max(1, d.cfg["campaign_name_max"] - len(label))] + label
    req = SimpleNamespace(purpose=snap["purpose"], n_saplings=int(sum(short.values())), polygon=snap.get("polygon"), zone=snap.get("zone"), barangay=snap.get("barangay"),
                          seed=body.seed if body.seed is not None else snap.get("seed"), species_ids=list(short),
                          campaign=SimpleNamespace(name=cname, unit=(root_camp or {}).get("unit", "")) if cname else None, layout_mode="blocks")
    sc = plan_scope(d, req, season, strict=True, extra_exclude_ids=used)
    seed = d.cfg["default_seed"] if req.seed is None else req.seed
    trees = {sid: n for sid, n in short.items() if sid in set(sc.ids_kept or [])}
    gone = sorted(set(short) - set(trees))
    if not trees:
        raise HTTPException(400, "None of the species that lost trees can be planted again in this area and window. Change the dates or plan a new campaign.")
    req.species_ids = list(trees)
    req.n_saplings = int(sum(trees.values()))
    req.campaign = SimpleNamespace(name=cname, unit=(root_camp or {}).get("unit", "")) if cname else None
    out = create_plan(d, req, season, sc, seed, "blocks", species_trees=trees,
                      topup={"parent_plan_id": plan_id, "number": n_top, "trees_requested": req.n_saplings, "include_remaining": bool(body.include_remaining),
                             "trees_by_species": {str(k): v for k, v in trees.items()}, "species_not_available": gone, "squares_excluded_of_family": sc.family_dropped,
                             "shortfall_trees_of_parent": prog["shortfall"]["trees"]})
    out["parent_plan_id"] = plan_id
    out["topup"] = {"number": n_top, "trees_requested": req.n_saplings, "include_remaining": bool(body.include_remaining), "species_not_available": gone,
                    "squares_excluded_of_family": sc.family_dropped, "parent_shortfall_trees": prog["shortfall"]["trees"]}
    return out


@app.get("/block-model")
def block_model(d=Depends(D)):
    """The block model (provisional) and, for every species, the spacing, rows, trees per row and capacity of a full block; a species without planting distance says why it cannot be planned."""
    bc = pal.BLOCK_CFG
    bt = pal.block_table(d.ctx.species)
    rows = [{"species_id": int(r.species_id), "common_name": r.common_name, "spacing_m": py(r.spacing_m), "rows": py(r.rows), "trees_per_row": py(r.trees_per_row),
             "capacity": py(r.capacity), "reason": r.reason} for r in bt.itertuples(index=False)]
    return {"config": {**bc, "usable_side_m": round(bc["block_side_m"] * bc["usable_share"] ** 0.5, 2), "status": "provisional until the agriculturist signs it off"},
            "species": rows, "without_spacing": [r["species_id"] for r in rows if r["capacity"] is None]}


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


@app.get("/plans/{plan_id}/field-kit")
def field_kit_info(plan_id: str, d=Depends(D)):
    """Does this plan have a field kit? When it does: when it was built, its size, its check code and whether the PDF map is inside (read from the zip, nothing is rebuilt)."""
    plan_files(d, plan_id)                                             # strict plan id, 404 if the plan does not exist
    path = kit_zip_path(d, plan_id)
    if not path.is_file():
        return {"plan_id": plan_id, "built": False, "download_url": None, "note": f"No field kit has been built for this plan yet (POST /plans/{plan_id}/field-kit)."}
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            man = next((n for n in names if n.endswith("manifest.json")), None)
            manifest = json.loads(z.read(man).decode("utf-8")) if man else {}
    except (zipfile.BadZipFile, ValueError, OSError):
        raise HTTPException(500, "The saved field kit could not be read. Build it again.")
    pdf = any(n.endswith("field-map.pdf") for n in names)
    return {"plan_id": plan_id, "built": True, "built_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"), "built_on": manifest.get("built_on"),
            "zip_size_bytes": path.stat().st_size, "check_code": manifest.get("check_code"), "pdf_included": pdf,
            "pdf_note": None if pdf else "field-map.pdf is not in this kit (it was skipped when the kit was built, for example because matplotlib is missing)",
            "files": sorted(n.rsplit("/", 1)[-1] for n in names if not n.endswith("/")), "download_url": f"/kits/{plan_id}.zip"}


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


def span_text(a, b):
    """'1 May - 29 Jun 2027' (both years when the span crosses a year end)."""
    if a.year != b.year:
        return f"{day_text(a)} {a.year} - {day_text(b)} {b.year}"
    return f"{day_text(a)} - {day_text(b)} {b.year}"


def window_vs_forecast(win, rows):
    """How the plan's planting dates relate to the forecast days. Returns (covered, overlap or None, plain message). covered = the dates and the forecast share at least one day."""
    n = adv.CFG["forecast_days"]
    if win is None:
        return None, None, f"This plan has no planting dates saved, so the advice cannot be compared with them. It is for the next {n} days only."
    if not rows:
        return False, None, f"The forecast has no days, so your planting dates ({span_text(*win)}) cannot be compared with it."
    fs, fe = date.fromisoformat(rows[0]["date"]), date.fromisoformat(rows[-1]["date"])
    ws, we = win
    label = span_text(ws, we)
    if ws > fe:
        return False, None, f"Your planting dates ({label}) are beyond the {n}-day forecast. The advice below is for the next {n} days only."
    if we < fs:
        return False, None, f"Your planting dates ({label}) have already passed. The advice below is for the next {n} days only."
    lo, hi = max(ws, fs), min(we, fe)
    if ws >= fs and we <= fe:
        return True, {"start": lo.isoformat(), "end": hi.isoformat()}, f"The {n}-day forecast covers all of your planting dates ({label})."
    return True, {"start": lo.isoformat(), "end": hi.isoformat()}, (f"The {n}-day forecast covers {span_text(lo, hi)} of your planting dates ({label}). "
                                                                      "The rest is outside the forecast, so the advice below is for the next "
                                                                      f"{n} days only.")


@app.get("/plans/{plan_id}/advisory")
def plan_advisory(plan_id: str, d=Depends(D)):
    """Weather advice for a saved plan: ONE forecast for the centre of the planned trees, compared with the plan's planting dates, and the warnings of every species of the plan."""
    csv, js = plan_files(d, plan_id)
    plan = pd.read_csv(csv)
    summary = json.loads(js.read_text(encoding="utf-8"))
    lat, lon = round(float(plan.lat.mean()), 6), round(float(plan.lon.mean()), 6)
    try:
        fc = adv.fetch_forecast(lat, lon, d.work / d.cfg["cache_dir"])
    except adv.ForecastUnavailable as ex:
        raise HTTPException(503, str(ex))
    today = adv.today_local()
    rows = adv.forecast_table(fc["daily"], today)
    camp = campaign_info(summary)
    win = None
    if camp["start"] and camp["end"]:
        try:
            win = (date.fromisoformat(camp["start"]), date.fromisoformat(camp["end"]))
        except ValueError:
            win = None
    covered, overlap, wmsg = window_vs_forecast(win, rows)
    window = {"months": window_month_list(*win), "label": span_text(*win)} if win else None
    codes = {}
    for it in plan_index(d, plan_id):
        codes.setdefault(it["species_id"], it["species_code"])
    sp_out, n_warn = [], 0
    for p_ in summary["palette"]:
        if p_.get("placed", 0) <= 0:
            continue
        i = d.species_idx[p_["species_id"]]
        row = d.ctx.species.iloc[i]
        a = adv.build_advisory({"species_id": p_["species_id"], "common_name": row.common_name, "planting_months": py(row.planting_months), "drought_tol": py(row.drought_tol)},
                               fc, today, window=window)
        n_warn += len(a["warnings"])
        sp_out.append({"species_id": p_["species_id"], "common_name": row.common_name, "code": codes.get(p_["species_id"]), "planted": p_["placed"],
                       "warnings": a["warnings"], "not_assessed": a["not_assessed"]})
    k = adv.CFG["dry_spell_days"]
    first = rows[:k]
    rain7 = round(sum(r["rain_mm"] for r in first), 1) if len(first) == k and all(r["rain_mm"] is not None for r in first) else None
    known = [r for r in rows if r["rain_mm"] is not None]
    wettest = max(known, key=lambda r: r["rain_mm"]) if known else None
    tmax = [r["tmax_c"] for r in rows if r["tmax_c"] is not None]
    tmin = [r["tmin_c"] for r in rows if r["tmin_c"] is not None]
    enso = {"status": adv.CFG["enso_status"], "source": adv.CFG["enso_source"], "note": "Set by hand in the configuration; the weather forecast cannot tell us this.",
            "is_default": adv.CFG["enso_status"] == "none" and str(adv.CFG["enso_source"]).startswith("not set")}
    return {"plan_id": plan_id, "location": {"lat": lat, "lon": lon, "note": "the centre of the planned trees"},
            "window": ({"start": win[0].isoformat(), "end": win[1].isoformat(), "label": span_text(*win)} if win else None),
            "window_covered_by_forecast": covered, "window_overlap": overlap, "window_message": wmsg,
            "forecast": {"first_day": rows[0]["date"] if rows else None, "last_day": rows[-1]["date"] if rows else None, "days": len(rows),
                         "rain_next_days": k, "rain_next_days_mm": rain7, "max_daily_rain_mm": wettest["rain_mm"] if wettest else None,
                         "max_daily_rain_date": wettest["date"] if wettest else None, "tmax_c_max": max(tmax) if tmax else None, "tmin_c_min": min(tmin) if tmin else None,
                         "missing_note": ("Some forecast values are missing and were not used." if len(known) < len(rows) or len(tmax) < len(rows) or len(tmin) < len(rows) else "")},
            "species": sp_out, "n_warnings": n_warn, "enso": enso, "thresholds": {"dry_spell_mm": adv.CFG["dry_spell_mm"], "dry_spell_days": k, "heavy_rain_mm": adv.CFG["heavy_rain_mm"]},
            "cached": fc["cached"], "cache_age_minutes": fc["cache_age_minutes"], "cache_stale": fc["stale"], "forecast_fetched_at": fc["fetched_at"], "network_error": fc["network_error"],
            "forecast_source": adv.SOURCE, "disclaimer": adv.DISCLAIMER}


# ---------------------------------------------------------------------------------------------------------------------
# GET /weather/week: the next 7 days at one place, a plain verdict for planting that week, and the species to plant (or hold back) for a purpose
# ---------------------------------------------------------------------------------------------------------------------
WEEK_VERDICTS = {"good_to_plant": "Good to plant", "plant_with_care": "Plant with care", "avoid_this_week": "Avoid this week", "unknown": "Cannot judge this week"}


def week_forecast(fc, today, n):
    """The forecast restricted to the first n days from today (same shape as fetch_forecast gives, so adv.build_advisory judges THIS week only)."""
    t = fc["daily"]["time"]
    idx = []
    for i, ds in enumerate(t):
        try:
            if date.fromisoformat(ds) >= today:
                idx.append(i)
        except ValueError:
            continue
    idx = idx[:n]
    daily = {k: ([v[i] if i < len(v) else None for i in idx] if isinstance(v, list) else v) for k, v in fc["daily"].items()}
    return {**fc, "daily": daily}


def months_text(months):
    """[5, 6, 7] -> 'May to July'; [5, 7] -> 'May, July'."""
    names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    ms = sorted(months)
    if len(ms) >= 3 and ms[-1] - ms[0] == len(ms) - 1:
        return f"{names[ms[0] - 1]} to {names[ms[-1] - 1]}"
    return ", ".join(names[m - 1] for m in ms)


def week_verdict(days, c):
    """good_to_plant | plant_with_care | avoid_this_week | unknown, from the existing thresholds (heavy rain in one day, dry spell over the week), with the numbers behind it."""
    n, heavy_mm, dry_mm = c["dry_spell_days"], c["heavy_rain_mm"], c["dry_spell_mm"]
    known = [r for r in days if r["rain_mm"] is not None]
    thresholds = {"heavy_rain_mm": heavy_mm, "dry_spell_mm": dry_mm, "dry_spell_days": n}
    total = round(sum(r["rain_mm"] for r in known), 1) if len(days) == n and len(known) == n else None
    heavy = [r for r in known if r["rain_mm"] > heavy_mm]
    if heavy:
        worst = max(heavy, key=lambda r: r["rain_mm"])
        code = "avoid_this_week"
        reasons = [{"code": "heavy_rain", "message": f"Heavy rain is forecast: up to {worst['rain_mm']:g} mm on {day_text(date.fromisoformat(worst['date']))} (threshold {heavy_mm:g} mm in one day).",
                    "numbers": {"max_daily_rain_mm": worst["rain_mm"], "date": worst["date"], "threshold_mm": heavy_mm,
                                "days_above_threshold": [{"date": r["date"], "rain_mm": r["rain_mm"]} for r in heavy]}}]
    elif not known:
        code, reasons = "unknown", [{"code": "no_rain_values", "message": "The forecast has no rain values for this week, so it cannot be judged.", "numbers": {}}]
    elif total is None:
        code = "unknown"
        reasons = [{"code": "rain_values_missing", "message": f"The forecast has rain values for only {len(known)} of the {n} days, so the week cannot be judged "
                                                            "(no day is above the heavy-rain threshold, but the dry-spell check needs every day).",
                    "numbers": {"days_with_rain_value": len(known), "days_needed": n, "heavy_rain_mm": heavy_mm}}]
    elif total < dry_mm:
        code = "plant_with_care"
        reasons = [{"code": "dry_spell", "message": f"Only {total:g} mm of rain is forecast for the next {n} days (threshold {dry_mm:g} mm): new trees will need watering.",
                    "numbers": {"forecast_rain_mm": total, "days": n, "threshold_mm": dry_mm}}]
    else:
        code = "good_to_plant"
        reasons = [{"code": "no_warning", "message": f"{total:g} mm of rain is forecast for the next {n} days and no day is above {heavy_mm:g} mm: no dry spell and no heavy rain.",
                    "numbers": {"forecast_rain_mm": total, "days": n, "dry_spell_mm": dry_mm, "heavy_rain_mm": heavy_mm,
                                "max_daily_rain_mm": max(r["rain_mm"] for r in known)}}]
    return {"code": code, "label": WEEK_VERDICTS[code], "reasons": reasons, "thresholds": thresholds}, total


@app.get("/weather/week")
def weather_week(purpose: Purpose, lat: Optional[float] = Query(None, ge=-90, le=90, description="default: the centre of San Mateo"),
                 lon: Optional[float] = Query(None, ge=-180, le=180, description="default: the centre of San Mateo"), d=Depends(D)):
    """The next 7 days at one place (ONE forecast request, cached 3 h, saved copy when the network fails), a plain verdict for planting this week with the numbers behind it,
    and two species lists for the purpose: (a) in their best months this week and not hit by a weather warning, (b) outside their best months but with High drought tolerance
    ('Only if you can water'). Species with a warning are listed apart as held_back. Ranked by the municipal species score. A planning aid, not a guarantee."""
    a_ = d.all_points
    if (lat is None) != (lon is None):
        raise HTTPException(422, "Send both lat and lon, or neither (then the centre of San Mateo is used).")
    if lat is None:
        bb = d.boundaries_info["bbox"]
        lon, lat = round((bb[0] + bb[2]) / 2, 5), round((bb[1] + bb[3]) / 2, 5)
        centre = True
    else:
        centre = False
        m = d.cfg["advisory_area_margin_deg"]
        if not (a_.lat.min() - m <= lat <= a_.lat.max() + m and a_.lon.min() - m <= lon <= a_.lon.max() + m):
            raise HTTPException(422, "The coordinate is outside the San Mateo area; the weather advice is only offered for the mapped municipality.")
    try:
        fc = adv.fetch_forecast(lat, lon, d.work / d.cfg["cache_dir"])
    except adv.ForecastUnavailable as ex:
        raise HTTPException(503, str(ex))
    c = adv.CFG
    n = c["dry_spell_days"]
    today = adv.today_local()
    fc7 = week_forecast(fc, today, n)
    days = adv.forecast_table(fc7["daily"])
    verdict, total = week_verdict(days, c)
    known = [r for r in days if r["rain_mm"] is not None]
    wettest = max(known, key=lambda r: r["rain_mm"]) if known else None
    hot = [r for r in days if r["tmax_c"] is not None]
    hottest = max(hot, key=lambda r: r["tmax_c"]) if hot else None
    tmin = [r["tmin_c"] for r in days if r["tmin_c"] is not None]
    missing = len(known) < len(days) or len(hot) < len(days) or len(tmin) < len(days)
    week = {"first_day": days[0]["date"] if days else None, "last_day": days[-1]["date"] if days else None, "n_days": len(days), "days": days,
            "rain_total_mm": total, "wettest_day": {"date": wettest["date"], "rain_mm": wettest["rain_mm"]} if wettest else None,
            "hottest_day": {"date": hottest["date"], "tmax_c": hottest["tmax_c"]} if hottest else None,
            "tmax_c_max": hottest["tmax_c"] if hottest else None, "tmin_c_min": min(tmin) if tmin else None,
            "missing_note": ("Some forecast values are missing and were not used." if missing else ""),
            "short_note": (f"The forecast has only {len(days)} of the next {n} days." if len(days) < n else "")}
    # ---- species for the week
    end = today + timedelta(days=max(n - 1, 0))
    season = SimpleNamespace(start=today, end=end, months=window_month_list(today, end), days=n, filter="mark")
    window = {"months": season.months, "label": span_text(today, end)}
    mn = c["month_names"]
    rank_of = {int(r.species_id): (k, float(r.score)) for k, r in enumerate(d.municipal[purpose].itertuples(index=False), 1)}
    sp = d.ctx.species
    items = {"best": [], "water": [], "held_back": []}
    n_known_months = 0
    month_counts = {}
    ids = set()
    for k, r in enumerate(sp.itertuples(index=False)):
        sid = int(r.species_id)
        months = d.species_months[k]
        if months is None:
            continue
        n_known_months += 1
        for mth in months:
            month_counts[mth] = month_counts.get(mth, 0) + 1
        so = season_object(months, season)
        tol = py(r.drought_tol)
        a = adv.build_advisory({"species_id": sid, "common_name": r.common_name, "planting_months": py(r.planting_months), "drought_tol": tol}, fc7, today, window=window)
        warn = [w for w in a["warnings"] if w["code"] != "not_in_planting_window"]
        best = so["status"] in ("in_season", "partly")
        water = (not best) and tol == "High"
        if not (best or water):
            continue
        names = ", ".join(mn[m - 1] for m in sorted(months))
        if best:
            why = (f"In its best months ({names})." if so["status"] == "in_season" else f"Only part of this week is in its best months ({names}).") + (f" Drought tolerance: {tol}." if tol else "")
        else:
            why = f"Outside its best months ({names}) but with High drought tolerance: only if you can water."
        rk, sc = rank_of[sid]
        fid = species_field_ids(d, sid, ["months_raw", "drought_tol"])
        ids |= set(fid)
        item = {"species_id": sid, "common_name": r.common_name, "rank": rk, "species_score": round(sc, 4), "list": "best_months" if best else "only_if_you_can_water",
                "label": None if best else "Only if you can water", "reason": why, "season": so, "planting_months_names": [mn[m - 1] for m in sorted(months)], "drought_tol": tol,
                "warnings": warn, "not_assessed": [x for x in a["not_assessed"] if x["code"] != "not_in_planting_window"],
                "flags": d.ctx.species_flags.get(sid, []), "source_ids": {f: d.src_by_sf[(sid, f)] for f in ("months_raw", "drought_tol") if (sid, f) in d.src_by_sf}}
        items["held_back" if warn else ("best" if best else "water")].append(item)
    for lst in items.values():
        lst.sort(key=lambda x: (x["rank"], x["species_id"]))
    half = [m for m, cnt in month_counts.items() if n_known_months and cnt * 2 >= n_known_months]
    most = {"months": sorted(half), "names": [mn[m - 1] for m in sorted(half)], "text": f"Most are best planted {months_text(half)}." if half else ""}
    best_total = len(items["best"]) + sum(1 for x in items["held_back"] if x["list"] == "best_months")
    if items["best"]:
        e_best = None
    elif best_total == 0:
        e_best = {"code": "none_in_best_months", "message": f"No species are in their best months this week. {most['text']}".strip()}
    else:
        e_best = {"code": "all_held_back_by_warnings", "message": "Every species in its best months has a weather warning this week. They are listed below under 'Held back'."}
    water_total = len(items["water"]) + sum(1 for x in items["held_back"] if x["list"] == "only_if_you_can_water")
    e_water = None if items["water"] else ({"code": "no_drought_tolerant_species_out_of_season", "message": "No species with High drought tolerance is outside its best months this week."}
                                          if water_total == 0 else {"code": "all_held_back_by_warnings", "message": "Every drought-tolerant species outside its best months has a weather warning this week."})
    enso = {"status": adv.CFG["enso_status"], "source": adv.CFG["enso_source"], "note": "Set by hand in the configuration; the weather forecast cannot tell us this.",
            "is_default": adv.CFG["enso_status"] == "none" and str(adv.CFG["enso_source"]).startswith("not set")}
    return {"purpose": purpose, "include_unzoned": bool(d.include_unzoned), "today": today.isoformat(),
            "location": {"lat": lat, "lon": lon, "forecast_for_lat": round(lat, c["cache_coord_decimals"]), "forecast_for_lon": round(lon, c["cache_coord_decimals"]),
                         "note": "the centre of San Mateo" if centre else "the place you chose"},
            "week": week, "verdict": verdict,
            "species": {"best_months": {"label": "In their best months this week", "items": items["best"], "count": len(items["best"]), "empty_reason": e_best},
                        "only_if_you_can_water": {"label": "Only if you can water", "items": items["water"], "count": len(items["water"]), "empty_reason": e_water},
                        "held_back": items["held_back"], "n_species_total": int(len(sp)), "species_with_planting_months": n_known_months, "most_species_months": most,
                        "ranking": "Ranked by the municipal species score for this purpose (GET /rank/municipal).",
                        "week_months": [mn[m - 1] for m in season.months]},
            "enso": enso, "thresholds": {"dry_spell_mm": c["dry_spell_mm"], "dry_spell_days": n, "heavy_rain_mm": c["heavy_rain_mm"]},
            "cached": fc["cached"], "cache_age_minutes": fc["cache_age_minutes"], "cache_stale": fc["stale"], "forecast_fetched_at": fc["fetched_at"], "network_error": fc["network_error"],
            "forecast_source": adv.SOURCE, "disclaimer": adv.DISCLAIMER, "sources": sources_map(d, ids)}


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
         season=Depends(season_q), d=Depends(HD)):
    """Compact column arrays for every legal grid point: point_id, lon, lat, W, best_species_id, n_eligible_species, barangay."""
    drop = season_drop_ids(d, season)
    if species_ids is not None:
        if species_id is not None:
            raise HTTPException(422, "Use either species_id (one species) or species_ids (several), not both")
        ids = parse_species_ids(d, species_ids)
        body = grid_body_multi(d, purpose, [i for i in ids if i not in drop], mode)
        sel = ids
    else:
        if species_id is not None and species_id not in d.species_idx:
            raise HTTPException(404, f"species_id {species_id} not found (valid ids: {int(d.ctx.species.species_id.min())}-{int(d.ctx.species.species_id.max())})")
        body = grid_body(d, purpose, species_id, drop)
        sel = None if species_id is None else [species_id]
    if season is not None:
        body = with_season(body, season_block(d, season, sel))
    return _cached_json(body, d, live=True)


@app.get("/grid/landcover")
def grid_landcover(d=Depends(D)):
    """The dominant satellite land-cover class (ESA WorldCover 2021) of every grid square and its ground flags, compact. Information only; the same for both views."""
    if d.landcover_body is None:
        raise HTTPException(404, "Data Unavailable: data/processed/site_landcover.csv does not exist yet (run python pipeline/landcover.py compute).")
    return _cached_json(d.landcover_body, d)


@app.get("/grid/context")
def grid_context(d=Depends(D)):
    """The 1,837 grid squares that are not planting zones (outside the zoning map, special reserved, industrial, commercial, quarry, landfill), for a faint map layer. Not scored."""
    return _cached_json(d.context_body, d)


@app.get("/geo/zones")
def geo_zones(d=Depends(D)):
    """GeoJSON of the legal land-use zones (the zones that contain grid points), each with its name, bbox and label point."""
    return _cached_json(d.zones_body, d)


@app.get("/areas/rank")
def areas_rank(purpose: Purpose, species_ids: str = Query(..., description="comma-separated species ids, for example 1,2,3"),
               mode: Literal["all", "any"] = Query("all"), by: Literal["barangay", "zone"] = Query("barangay"), season=Depends(season_q), d=Depends(HD)):
    """Barangays (or zones) ranked for the selected species: mean W over the legal points, share of points suitable, number of suitable points."""
    ids = parse_species_ids(d, species_ids)
    drop = season_drop_ids(d, season)
    body = areas_rank_body(d, purpose, [i for i in ids if i not in drop], mode, by)
    if season is not None:
        body = with_season(body, season_block(d, season, ids))
    return _cached_json(body, d, live=True)


class AreaRankRequest(BaseModel):
    purpose: Purpose
    polygon: Optional[dict] = Field(None, description="GeoJSON Polygon / MultiPolygon (or a Feature holding one), lon/lat")
    barangay: Optional[str] = Field(None, description="barangay name (as written, or the display name, e.g. 'Santa Ana')")
    zone: Optional[str] = Field(None, description="zone_desc, e.g. 'Forest Zone'")
    limit: int = Field(10, ge=1, le=45)
    n_saplings: int = Field(API_CFG["area_mix_saplings"], ge=1, le=API_CFG["plan_max_saplings"], description="saplings the suggested mix is worked out for")


@app.post("/rank/area")
def rank_area(req: AreaRankRequest, q_season=Depends(season_q), d=Depends(HD)):
    """Species ranked for a whole area (a barangay, a zone or a drawn polygon) plus the suggested mix with shares from the palette code."""
    ctx, cfg = d.ctx, d.cfg
    season = q_season
    drop = season_drop_ids(d, season)
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
    if drop:                                                           # season_filter=only: out-of-season species are not ranked (the scores are untouched)
        suitable = suitable[~suitable.species_id.isin(drop)]
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
    keep_k = [k for k, sid_ in enumerate(ctx.species.species_id.astype(int)) if sid_ not in drop]
    if not keep_k or suitable.empty:
        pal_res = {"species_id": [], "common_name": [], "share": [], "quota": [], "score": [], "needs_both_sexes": [], "common_months": [], "dioecious_rejected": [],
                   "warnings": ["No species is left after the planting-window filter, so no mix can be suggested. Change the dates or show all species."]}
    else:
        sp_view = ctx.species.iloc[keep_k].reset_index(drop=True)
        if season is not None and season.filter == "only":
            sp_view = clip_months(sp_view, season)                    # the mix's shared planting months must lie inside the window
        pal_res = pal.build_palette(sp_view, S_area[:, keep_k], P[keep_k], req.n_saplings)
    mix = [{"species_id": sid, "common_name": nm, "share": round(sh, 4), "quota": q, "species_score": round(sc, 4), "needs_both_sexes": nb,
            "genus": str(ctx.species.genus.iloc[d.species_idx[sid]])}
           for sid, nm, sh, q, sc, nb in zip(pal_res["species_id"], pal_res["common_name"], pal_res["share"], pal_res["quota"], pal_res["score"],
                                             pal_res["needs_both_sexes"])]
    any_suitable = int((S_area >= mt.CFG["s_min"]).any(axis=1).sum())
    if season is not None:
        for r_ in rows + mix:
            r_["season"] = season_object(d.species_months[d.species_idx[r_["species_id"]]], season)
        if mix and not [m for m in season.months if m in pal_res["common_months"]]:
            pal_res["warnings"] = list(pal_res["warnings"]) + ["season: the species of this mix do not share a planting month inside the window"]
    out = {"purpose": req.purpose, "area": {**info, "legal_points": int(len(idx)), "points_with_a_suitable_species": any_suitable},
            "species_total": int(len(ctx.species)), "species_with_suitable_points": int(len(suitable)), "returned": len(rows), "ranking": rows,
            "mix": {"n_saplings": req.n_saplings, "species": mix, "common_planting_months": pal_res["common_months"], "warnings": pal_res["warnings"],
                    "dioecious_left_out": pal_res["dioecious_rejected"],
                    "caps": {"max_species_share": pal.CFG["max_species_share"], "max_genus_share": pal.CFG["max_genus_share"],
                             "palette_min": pal.CFG["palette_min"], "palette_max": pal.CFG["palette_max"], "status": "provisional"}},
            "score_definition": "species_score = mean W where the species is suitable (S >= 0.50) x the share of the area's grid points where it is suitable",
            "missing": {"marker": miss, "columns": {"mean_site_confidence": f"{miss} = no confidence value available", "p_confidence": f"{miss} = no confidence value available"},
                        "note": "No value is null. In sources, a missing rank is the marker and a missing text is an empty string."},
            "sources": {k: {f: ((miss if f == "rank" else "") if v is None else v) for f, v in src.items()} for k, src in sources_map(d, ids).items()},
            "limits": limits_of(d), **season_extra(d, season)}
    if season is not None:
        out["mix"]["common_months_in_window"] = [m for m in season.months if m in pal_res["common_months"]]
    return out


# ---------------------------------------------------------------------------------------------------------------------
# saved field checks (what a researcher saw at a spot). Append-only events in data/field/field_checks.db, see pipeline/field_verify.py
# ---------------------------------------------------------------------------------------------------------------------
class FieldCheckIn(BaseModel):
    point_id: int
    status: Literal["verified_plantable", "not_plantable", "needs_recheck", "planted"]
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
    plan_id: Optional[str] = Field(None, description="required when the status is planted: the plan whose block was planted")
    trees_planted: Optional[int] = Field(None, ge=0, description="required when the status is planted: trees really planted in the block (0 up to the trees of the block)")


def check_planted(d, req):
    """planted only makes sense for a block of a plan in blocks: the plan must exist, hold the point, and trees_planted must not exceed the trees of the block."""
    if not req.plan_id:
        raise HTTPException(422, "plan_id is required when the status is planted (say which plan's block was planted).")
    plan, _ = load_plan(d, req.plan_id)
    if not fv.is_blocks_plan(plan):
        raise HTTPException(422, "This plan was made in points mode: use verified_plantable. The status planted (with a tree count) belongs to blocks plans.")
    row = plan[plan.point_id.astype(int) == int(req.point_id)]
    if row.empty:
        raise HTTPException(422, f"point_id {req.point_id} is not a block of plan {req.plan_id}.")
    planned = int(row.trees_planned.iloc[0])
    if req.trees_planted is None or req.trees_planted > planned:
        raise HTTPException(422, f"trees_planted must be a whole number from 0 to {planned} (the trees of this block).")


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
    if req.status == "planted":
        check_planted(d, req)
    elif req.trees_planted is not None:
        raise HTTPException(422, "trees_planted only applies to the status planted.")
    try:
        ev = fv.validate_event(req.model_dump(), point_lonlat=point_lonlat_of(d)(req.point_id), inside=inside_municipality(d),
                               previous_status=prev["status"] if prev else None)
        check_id = fv.add_event(d.field_db, ev, source="dashboard")
    except fv.FieldCheckError as ex:
        raise HTTPException(422, str(ex))
    refresh_field(d)
    return {"check_id": check_id, "saved": {**ev, "source": "dashboard", "check_id": check_id}, "current": field_view(d, req.point_id),
            "effect": ("The point is now left out of rankings and plans." if req.point_id in d.field_ex_ids else
                       "Saved. This does not change any score." if req.status == "verified_plantable" else
                       f"Saved: {req.trees_planted} trees planted in this block (plan {req.plan_id})." if req.status == "planted" else "Saved."),
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
def field_check_list(status: Optional[Literal["verified_plantable", "not_plantable", "needs_recheck", "planted"]] = None, barangay: Optional[str] = None,
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


# ---------------------------------------------------------------------------------------------------------------------
# search: barangays, species, grid points, planting points of saved plans, and (optional) streets and landmarks
# ---------------------------------------------------------------------------------------------------------------------
def point_card(d, pid):
    """A grid point as shown in search results (None if the id is not a grid point)."""
    i = d.allpt_index.get(int(pid))
    if i is None:
        return None
    r = d.all_points.iloc[i]
    b = int(d.allpt_barangay[i])
    legal = bool(r.is_legal_zone)
    card = {"type": "grid_point", "point_id": int(r.point_id), "lon": py(r.lon), "lat": py(r.lat), "utm_e": py(r.utm_e), "utm_n": py(r.utm_n),
            "legal_zone": legal, "zone": py(r.zone_desc) or "", "barangay": d.barangay_names[b] if b >= 0 else "",
            "barangay_display": d.barangay_display[b] if b >= 0 else "", "elev_m": py(r.elev_m), "slope_pct": py(r.slope_pct)}
    unconf = bool(d.zoning_on and r.zoning_status == "unconfirmed")
    if d.zoning_on:
        card["zoning_status"] = py(r.zoning_status)
    if unconf:
        card["note"] = ((f"This grid point is in the {r.zone_desc} (zoning not confirmed). It is ranked, but confirm with the LGU before planting." if isinstance(r.zone_desc, str) else
                         "This grid point is outside our zoning map (the CLUP 2021-2031 shows it as Forest Reserve, Watershed). It is ranked, but coordinate with MENRO and DENR before planting."))
    elif not legal:
        card["note"] = "This grid point is not in a legal planting zone, so it has no ranking."
    card.update(soil_facts(r))
    if (legal or unconf) and d.field_current.get(int(pid)) is not None:
        card["field_check"] = field_view(d, int(pid))
    gc = ground_cover_block(d, int(pid))
    if gc is not None:
        card["ground_cover"] = gc
    return card


def parse_point_query(q):
    """'832' -> 832. Digits only (spaces around are ignored); anything else is a 422 with an example."""
    t = str(q).strip()
    if not re.fullmatch(r"\d{1,9}", t):
        raise HTTPException(422, "A grid point id is digits only (for example 832).")
    return int(t)


def norm_ref(text):
    return re.sub(r"[\s_]+", "-", text.strip().lower())


def parse_ref_query(q):
    """'duh-012', 'DUH 12', 'duh12' -> ('duh', 12); 'duh' -> ('duh', None); anything else -> None."""
    m = re.fullmatch(r"([a-z][a-z0-9]{0,2}?)[-\s_]*0*(\d{1,4})", q.strip().lower())
    if m:
        return m.group(1), int(m.group(2))
    m = re.fullmatch(r"[a-z][a-z0-9]{0,2}", q.strip().lower())
    return (m.group(0), None) if m else None


def plan_index(d, plan_id):
    """The points of a saved plan with their kit references (point_ref, species_code), barangay and species name. Cached until the plan file changes."""
    csv_path = plans_dir(d) / f"{plan_id}.csv"
    key = (plan_id, csv_path.stat().st_mtime_ns)
    hit = lru_get(d.plan_index_cache, key)
    if hit is not None:
        return hit
    plan = pd.read_csv(csv_path)
    refs = fv.plan_point_refs(plan, d.ctx.species)                    # the same numbering as the field kit builder
    inv = {pid: ref for ref, pid in refs.items()}
    names = d.ctx.species.set_index("species_id").common_name
    items = []
    for r in plan.itertuples(index=False):
        pid = int(r.point_id)
        ref = inv[pid]
        j = d.legal_index.get(pid)
        b = int(d.point_barangay[j]) if j is not None else -1
        items.append({"type": "plan_point", "plan_id": plan_id, "point_ref": ref, "species_code": ref.split("-")[0], "species_id": int(r.species_id),
                      "species": str(names[int(r.species_id)]), "point_id": pid, "lon": py(r.lon), "lat": py(r.lat), "zone": py(r.zone_desc) or "",
                      "barangay": d.barangay_names[b] if b >= 0 else "", "barangay_display": d.barangay_display[b] if b >= 0 else "",
                      "S": py(r.S), "W": py(r.W)})
    lru_put(d.plan_index_cache, key, items, 64)
    return items


def match_plan_items(items, q):
    """Plan points matching a query: point_ref (DUH-012, duh 12), species code (duh), common name (duhat, weeping fig) or the grid point id; case-insensitive."""
    q = q.strip()
    ref = parse_ref_query(q)
    nq = norm_text(q)
    hits = []
    for it in items:
        code = it["species_code"].lower()
        score = None
        if ref and ref[1] is not None and code == ref[0] and int(it["point_ref"].split("-")[1]) == ref[1]:
            score = 0                                                    # the exact point reference
        elif q.isdigit() and int(q) == it["point_id"]:
            score = 1
        elif ref and ref[1] is None and (code == ref[0] or code.startswith(ref[0])):
            score = 2                                                    # a species code
        elif nq and nq in norm_text(it["species"]):
            score = 3                                                    # a common name
        elif norm_ref(q) in it["point_ref"].lower():
            score = 4
        if score is not None:
            hits.append((score, it["point_ref"], it))
    hits.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in hits]


def saved_plan_ids(d):
    """Plan ids that have both files, newest first (by the timestamp in the id, else the file time)."""
    root = plans_dir(d)
    out = []
    for sj in (root.glob("plan_*_summary.json") if root.is_dir() else []):
        pid = sj.name[:-len("_summary.json")]
        if not valid_plan_id(pid) or not (root / f"{pid}.csv").is_file():
            continue
        m = re.search(r"_(\d{8})_(\d{6})", pid)
        out.append((m.group(1) + m.group(2) if m else datetime.fromtimestamp(sj.stat().st_mtime).strftime("%Y%m%d%H%M%S"), pid))
    return [pid for _, pid in sorted(out, reverse=True)]


def barangay_hits(d, q):
    key = norm_place(q, d.cfg["place_aliases"])
    if not key:
        return []
    return [{"type": "barangay", "name": p["name"], "display_name": p["display_name"], "centroid": p["centroid"], "bounds": p["bounds"],
             "legal_points": int((d.point_barangay == i).sum())} for i, p in enumerate(d.places_sorted) if key in p["key"]]


def species_hits(d, q):
    needle = norm_text(q)
    out = []
    for r in d.ctx.species.itertuples(index=False):
        hit = [f for f, v in (("common_name", r.common_name), ("scientific_name", r.scientific_name)) if needle in norm_text(v)]
        if needle and hit:
            out.append({"type": "species", "species_id": int(r.species_id), "common_name": r.common_name, "scientific_name": r.scientific_name, "matched_on": hit})
    return out


@app.get("/search/point")
def search_point(q: str = Query(min_length=1, max_length=40), d=Depends(D)):
    """A grid point by its id (digits only). 404 when there is no such point."""
    pid = parse_point_query(q)
    card = point_card(d, pid)
    if card is None:
        raise HTTPException(404, f"There is no grid point with id {pid}. Grid point ids run from {int(d.all_points.point_id.min())} to {int(d.all_points.point_id.max())}.")
    return card


@app.get("/plans/{plan_id}/points")
def plan_points_search(plan_id: str, q: str = Query(min_length=1, max_length=60), limit: int = Query(20, ge=1, le=100), d=Depends(D)):
    """Points of a saved plan by point reference (DUH-012), species code (DUH), common name (Duhat) or grid point id. Case-insensitive."""
    plan_files(d, plan_id)                                             # strict plan id, 404 if the plan does not exist
    hits = match_plan_items(plan_index(d, plan_id), q)
    return {"plan_id": plan_id, "query": q, "count": min(len(hits), limit), "total_matching": len(hits), "points": hits[:limit]}


@app.get("/search/all")
def search_all(q: str = Query(min_length=2, max_length=60), limit: int = Query(API_CFG["search_group_limit"], ge=1, le=20), d=Depends(D)):
    """One call for the suggestions of the search box: barangays, species, a grid point (if q is a number) and the planting points of the most recent plans."""
    q = q.strip()
    bar, sp = barangay_hits(d, q), species_hits(d, q)
    pts = []
    if re.fullmatch(r"\d{1,9}", q):
        card = point_card(d, int(q))
        pts = [card] if card else []
    plan_hits = []
    for pid in saved_plan_ids(d)[:d.cfg["search_recent_plans"]]:
        plan_hits.extend(match_plan_items(plan_index(d, pid), q)[:limit])
        if len(plan_hits) >= limit:
            break
    return {"query": q, "normalised_query": norm_place(q, d.cfg["place_aliases"]), "limit": limit,
            "barangays": bar[:limit], "species": sp[:limit], "points": pts[:limit], "plan_points": plan_hits[:limit],
            "counts": {"barangays": len(bar), "species": len(sp), "points": len(pts), "plan_points": len(plan_hits)},
            "searched_plans": min(len(saved_plan_ids(d)), d.cfg["search_recent_plans"]), "geocoder_enabled": bool(d.cfg["geocoder_enabled"])}


# ---- streets and landmarks: the public Nominatim service, OFF by default ------------------------------------------------
def geocoder_http_get(url, headers, timeout):
    """GET a URL and return the parsed JSON (tests replace this function; they never use the internet)."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode_bbox(d):
    x0, y0, x1, y1 = d.boundaries_info["bbox"]
    m = d.cfg["geocoder_bbox_margin_deg"]
    return [x0 - m, y0 - m, x1 + m, y1 + m]                           # west, south, east, north


def geocode_cache_file(d, nq):
    key = hashlib.sha256(json.dumps([nq, d.cfg["geocoder_countrycodes"], geocode_bbox(d), d.cfg["geocoder_limit"]]).encode()).hexdigest()[:40]
    return d.work / d.cfg["geocoder_cache_dir"] / f"{key}.json"


@app.get("/search/geocode")
def search_geocode(q: str = Query(min_length=3, max_length=100), d=Depends(D)):
    """Streets and landmarks through Nominatim (OpenStreetMap). Disabled unless geocoder_enabled; one request per second; every answer cached 30 days."""
    cfg = d.cfg
    if not cfg["geocoder_enabled"]:
        raise HTTPException(503, "Place search for streets and landmarks is disabled (geocoder_enabled is off). Barangays, species, points and coordinates still work.")
    contact = (cfg["geocoder_contact"] or "").strip()
    if not contact:
        raise HTTPException(503, "Place search is enabled but geocoder_contact is empty. The public service requires an identifying contact (an email address or a web address) "
                                 "in every request, so no request was sent. Set geocoder_contact in API_CFG.")
    nq = re.sub(r"\s+", " ", q.strip().lower())
    path = geocode_cache_file(d, nq)
    cached = None
    if path.is_file():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            cached = None

    def answer(doc, from_cache, stale=False, error=None):
        age_days = (time.time() - doc["fetched_at"]) / 86400.0
        return {"query": q, "enabled": True, "cached": from_cache, "stale": stale, "cache_age_days": round(age_days, 2), "network_error": error,
                "results": doc["results"], "attribution": cfg["geocoder_attribution"], "source": "Nominatim (OpenStreetMap)"}

    if cached and (time.time() - cached["fetched_at"]) < cfg["geocoder_cache_days"] * 86400:
        return answer(cached, True)
    x0, y0, x1, y1 = geocode_bbox(d)
    params = {"q": q.strip(), "format": "jsonv2", "limit": cfg["geocoder_limit"], "countrycodes": cfg["geocoder_countrycodes"],
              "viewbox": f"{x0},{y1},{x1},{y0}", "bounded": 1, "addressdetails": 0}
    url = f"{cfg['geocoder_url']}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": f"{cfg['geocoder_app_name']}/1.0 ({contact})", "Accept": "application/json", "Accept-Language": "en"}
    err = None
    with d.geo.lock:                                                   # one request at a time, at most one per geocoder_min_interval_s
        if d.geo.last is not None:
            wait = cfg["geocoder_min_interval_s"] - (d.geo.clock() - d.geo.last)
            if wait > 0:
                d.geo.sleep(wait)
        d.geo.last = d.geo.clock()
        try:
            raw = geocoder_http_get(url, headers, cfg["geocoder_timeout_s"])
            if not isinstance(raw, list):
                raise ValueError("the service did not return a list of places")
        except Exception as ex:                                        # network down, timeout, blocked, bad answer
            err = f"{type(ex).__name__}: {ex}"
    if err is not None:
        if cached:
            return answer(cached, True, stale=True, error=err)
        raise HTTPException(503, f"The place search service could not be reached and there is no saved answer for this search ({err}). Try again later.")
    results = []
    for it in raw:
        try:
            lat, lon = float(it["lat"]), float(it["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        bb = it.get("boundingbox")
        results.append({"name": it.get("name") or str(it.get("display_name", "")).split(",")[0], "display_name": it.get("display_name", ""),
                        "category": it.get("category") or it.get("class", ""), "type": it.get("type", ""), "lat": lat, "lon": lon,
                        "bbox": [float(bb[2]), float(bb[0]), float(bb[3]), float(bb[1])] if isinstance(bb, list) and len(bb) == 4 else []})
    doc = {"fetched_at": time.time(), "query": nq, "results": results}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc), encoding="utf-8")
    tmp.replace(path)
    return answer(doc, False)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_v2:app", host="127.0.0.1", port=API_CFG["port"])
