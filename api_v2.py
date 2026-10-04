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
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, Optional

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "pipeline"))
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
]
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
def load_data(cfg=None):
    cfg = API_CFG if cfg is None else cfg
    root = ROOT / cfg["data_dir"]
    ctx = mt.load_context(root)
    sources = pd.read_csv(root / "species_sources.csv")
    refs = pd.read_csv(root / "species_references.csv")
    ps = pd.read_csv(root / "purpose_scores.csv")
    all_points = pd.read_csv(root / "site_points_clean.csv")
    d = SimpleNamespace(cfg=cfg, root=root, ctx=ctx, sources=sources, refs=refs, purpose_scores=ps, all_points=all_points)
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
            "purposes": list(mt.PURPOSES), "limits": LIMITS}


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
            "limits": LIMITS, "w_definition": "W = S x P if S >= 0.50 else 0"}


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
    viable = feas.any(axis=1)

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
    try:
        plan, summary = rp.make_plan(sub, req.purpose, req.n_saplings, zone=req.zone, seed=seed)
    except ValueError as ex:
        raise HTTPException(400, f"{ex}" + (" (the zone has no legal points inside the polygon)" if req.zone and req.polygon is not None else ""))
    if not summary["palette"]:
        raise HTTPException(400, "No species has eligible points (S >= 0.50) in this area, so no plan can be made. "
                                 f"{' '.join(summary['palette_warnings'])}".strip())
    ids = set()
    items = []
    for r in plan.itertuples(index=False):
        s_ids = [int(x) for x in str(r.site_scores_src_ids).split(";") if x] if isinstance(r.site_scores_src_ids, str) else []
        ids |= set(s_ids)
        items.append({"point_id": int(r.point_id), "lon": py(r.lon), "lat": py(r.lat), "utm_e": py(r.utm_e), "utm_n": py(r.utm_n), "zone": py(r.zone_desc),
                      "species_id": int(r.species_id), "species": r.species, "S": py(r.S), "P": py(r.P), "W": py(r.W), "confidence": py(r.confidence),
                      "flags": [f for f in str(r.flags).split(";") if f] if isinstance(r.flags, str) else [], "site_scores_source_ids": s_ids})
    palette = []
    for p in summary["palette"]:
        p_ids = purpose_source_ids(d, p["species_id"], req.purpose)
        ids |= set(p_ids)
        palette.append({**p, "purpose_score_source_ids": p_ids})
    pal_by_name = {p["species"]: p for p in summary["palette"]}
    rest = {k: v for k, v in summary.items() if k not in ("palette", "limits")}
    return {"purpose": req.purpose, "n_saplings_requested": req.n_saplings, "seed": seed, "palette": palette, "plan": items,
            "summary": rest,
            "unmatched": {"saplings_unmatched": summary["saplings_unmatched"], "saplings_unallocated_by_caps": summary["saplings_unallocated"],
                          "unused_candidate_points": summary["unused_candidate_points"],
                          "unmatched_by_species": {n: p["unmatched"] for n, p in pal_by_name.items() if p["unmatched"]}},
            "sources": sources_map(d, ids), "limits": list(dict.fromkeys(summary["limits"] + LIMITS))}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_v2:app", host="127.0.0.1", port=API_CFG["port"])
