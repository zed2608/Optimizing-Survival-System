#!/usr/bin/env python3
"""
score_sites.py - Day 2 task 1: rule-based site suitability S(point, species) in [0, 1].

    python pipeline/score_sites.py --out data/processed
    python pipeline/score_sites.py --out data/processed --water data/SMR_WATERBODIES_POLY.shp

Reads  <out>/species_clean.csv, <out>/species_sources.csv, <out>/site_points_clean.csv (Day 1 outputs; read-only here).
Writes <out>/scores/site_scores.csv and the table site_scores in <out>/scores/site_scores.db, a separate database file
(replaced on every run; <out>/scores/ is git-ignored). optimizing_survival.db is never touched.

Hard gates (S = 0 if violated): legal zone, elevation range, max slope; soil texture only when SOIL_GATE_MODE == "hard".
Slope (round 18): SLOPE_MODE "graded" (default) lets a square a little steeper than the species limit through with a lowered S (see SLOPE_MODE below);
SLOPE_MODE "hard" is the old gate and reproduces the earlier numbers exactly.
In "soft" mode (default, until the agriculturist verifies the soil mapping) a texture mismatch does not zero S: the soil
factor takes SOIL_MISMATCH_FACTOR, the pair is flagged soil_unverified_mismatch and its confidence is lowered.
A gate whose input is unknown (site texture unknown, species texture list empty, slope missing) does NOT exclude;
the term is left out of the score and the confidence drops.
Soft factors (0..1): elevation margin, slope margin, soil match, wetness. S = weighted mean of the factors that could be evaluated.
NOT scored: pH, rainfall, temperature, canopy, exposure (no real layers).
"""
import argparse, json, sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

# =====================================================================================================================
# CONFIG - every tunable number lives here. All are PROVISIONAL until the agriculturist signs off (CLAUDE.md rule 4).
# =====================================================================================================================
MARGIN_FRACTION = 0.10          # soft fall-off margin = this fraction of the species range (10%); the ONLY margin setting.
SOIL_GATE_MODE = "soft"         # "soft": texture mismatch -> low soil factor + flag, S not zeroed (legacy soil mapping is UNVERIFIED)
                                # "hard": texture mismatch -> S = 0. Switch to "hard" after the agriculturist verifies the mapping.
SLOPE_MODE = "graded"           # "graded" (default, round 18, PROVISIONAL: a team decision, the adviser confirms next week): above the species limit S is multiplied by a factor that falls
                                # linearly from 1 at the limit to 0 at limit + SLOPE_GRADED_MARGIN_FRACTION x limit; beyond that the pair is still rejected (hard stop).
                                # "hard": a square steeper than the limit has S = 0 (the rule before round 18; the printed sample sheet was scored with it).
SLOPE_GRADED_MARGIN_FRACTION = 0.25   # margin = 25% of the species limit, in percent slope (the unit of the data). A fixed 5 degrees would be a very different relative margin for each species.
STEEP_SQUARE_SLOPE_PCT = 57.7   # a "steep square" in the reports: slope above this PERCENT (57.7 percent is about 30 degrees). Used only to list the newly eligible pairs that the field team should look at first; it changes no score.
ELIGIBLE_S = 0.50               # a pair is eligible when S >= this (the same 0.50 as matching.CFG["s_min"])
SLOPE_GRADED_FLAG = "slope_graded"    # on a pair that is eligible only because of the graded slope rule
SLOPE_GRADED_NOTE = "Slope is steeper than this tree's usual limit. Plant on terraces or use contour planting, or choose another tree."
SOIL_MISMATCH_FACTOR = 0.25     # soil factor on a texture mismatch in "soft" mode (provisional, no source)
SOIL_SOURCE = "lgu"             # "lgu": the soil match uses soil_texture_lgu (the LGU soil map digitized by us, pipeline/lgu_soil.py); "legacy": soil_texture_legacy (the old four-code layer).
                                # Both are UNVERIFIED. A square with no texture never lowers a score (the soil term is simply not evaluated for it).
# SOIL_COMPAT: which species soil words fit a site texture (PROVISIONAL, for the agriculturist; explained in docs/DATA_SOURCES.md). A site texture matches a species when the species list
# holds ANY of the words on its row. Clay, Clay Loam and Loam keep today's rule (the same word); Silt Loam also counts as Loam; Sandy Loam also counts as the species' plain "Sandy".
SOIL_COMPAT = {
    "clay": {"clay"},
    "clay loam": {"clay loam"},
    "loam": {"loam"},
    "silt loam": {"silt loam", "loam"},
    "sandy loam": {"sandy loam", "sandy"},
}
SOIL_PROVISIONAL_FLAG = "soil_provisional"   # on a pair whose soil term was evaluated from the LGU soil map
SOIL_PROVISIONAL_NOTE = "Soil from the LGU soil map, digitized by us: provisional"
TERM_WEIGHTS = {                # weight of each soft factor in S (equal weights; provisional, not from any source)
    "elevation": 0.25, "slope": 0.25, "soil": 0.25, "wetness": 0.25,
}
WETNESS_RISK_DISTANCE_M = 50.0  # within this distance of a CREEK/RIVER, waterlogging risk applies (provisional, no source)
WATERLOG_TOL_LEVEL = {"Low": 0.0, "Medium": 0.5, "High": 1.0}   # ordinal levels as in FOUR_DAY_PLAN.md (Low/Medium/High = 0/0.5/1)
WATER_CLASSES = ("CREEK", "RIVER")
SITE_CRS = "EPSG:32651"         # UTM 51N, the CRS of utm_e / utm_n in site_points_clean.csv
# =====================================================================================================================

# species field -> field names in species_sources that justify each term
TERM_FIELDS = {
    "elevation": ["elev_min_m", "elev_max_m"],
    "slope": ["max_slope_pct"],
    "soil": ["soil_raw"],
    "wetness": ["waterlog_tol"],
}
# Site-side inputs (same for every row, so not repeated in breakdown_json): elev_m (backend/Working_Points.csv), slope_pct
# (finite differences on elev_m, ~100 m cells), soil_texture_legacy (legacy mapping, UNVERIFIED), distance to CREEK/RIVER
# polygons of data/SMR_WATERBODIES_POLY.shp.


def distance_to_water(sites, shp):
    """Distance (m) from each point to the nearest CREEK/RIVER polygon of the waterbodies layer; NaN if unavailable."""
    import geopandas as gpd
    from shapely import make_valid
    try:
        w = gpd.read_file(shp)
    except Exception:
        return pd.Series(np.nan, index=sites.index)
    w = w[w["CLASS"].isin(WATER_CLASSES) & w.geometry.notna()]
    if w.empty:
        return pd.Series(np.nan, index=sites.index)
    w = w.to_crs(SITE_CRS)
    w["geometry"] = w.geometry.map(make_valid)
    from shapely.strtree import STRtree
    pts = gpd.points_from_xy(sites.utm_e, sites.utm_n)
    idx, dist = STRtree(w.geometry.values).query_nearest(pts, return_distance=True, all_matches=False)
    out = np.full(len(pts), np.nan)
    out[idx[0]] = dist                                       # idx[0] = input point positions
    return pd.Series(out, index=sites.index)


def _edge_factor(dist_inside, margin):
    """1 when at least `margin` inside the limit, falling linearly to 0 at the limit itself."""
    with np.errstate(divide="ignore", invalid="ignore"):
        f = np.where(margin > 0, dist_inside / margin, 1.0)
    return np.clip(f, 0.0, 1.0)


def site_texture_column(sites, soil_source=None):
    """(column, source) of the site texture used: soil_texture_lgu when SOIL_SOURCE is 'lgu' and the column exists, else soil_texture_legacy."""
    src = SOIL_SOURCE if soil_source is None else soil_source
    if src not in ("lgu", "legacy"):
        raise ValueError(f"soil_source must be 'lgu' or 'legacy', got {src!r}")
    if src == "lgu" and "soil_texture_lgu" in sites:
        return "soil_texture_lgu", "lgu"
    return "soil_texture_legacy", "legacy"


def score_pairs(species, sites, margin_fraction=None, weights=None, wet_distance_m=None, soil_gate_mode=None,
                soil_mismatch_factor=None, soil_source=None, slope_mode=None, slope_margin_fraction=None):
    """
    Vectorised S for every (site, species) pair. Returns one row per pair with numeric terms (no JSON yet).

    species columns: species_id, elev_min_m, elev_max_m, max_slope_pct, soil_textures, soil_any_texture, waterlog_tol
    sites columns:   point_id, elev_m, slope_pct, soil_texture_legacy, is_legal_zone, water_dist_m (NaN = unknown)
    """
    mf = MARGIN_FRACTION if margin_fraction is None else margin_fraction
    w = dict(TERM_WEIGHTS if weights is None else weights)
    wet_r = WETNESS_RISK_DISTANCE_M if wet_distance_m is None else wet_distance_m
    mode = SOIL_GATE_MODE if soil_gate_mode is None else soil_gate_mode
    smode = SLOPE_MODE if slope_mode is None else slope_mode
    if smode not in ("graded", "hard"):
        raise ValueError(f"slope_mode must be 'graded' or 'hard', got {smode!r}")
    gm = SLOPE_GRADED_MARGIN_FRACTION if slope_margin_fraction is None else slope_margin_fraction
    if mode not in ("soft", "hard"):
        raise ValueError(f"soil_gate_mode must be 'soft' or 'hard', got {mode!r}")
    sp, si = species.reset_index(drop=True), sites.reset_index(drop=True)
    ns, np_ = len(sp), len(si)

    def sv(col):  # species column as (1, ns) array
        return sp[col].to_numpy(dtype=float)[None, :]
    def pv(col):  # site column as (np, 1) array
        return si[col].to_numpy(dtype=float)[:, None]

    elev, slope = pv("elev_m"), pv("slope_pct")
    water = pv("water_dist_m") if "water_dist_m" in si else np.full((np_, 1), np.nan)
    if "zoning_status" in si:                                # confirmed AND unconfirmed squares pass the zone gate; only named non-planting zones (excluded) fail
        legal = (si["zoning_status"] != "excluded").to_numpy()[:, None]
    else:
        legal = si["is_legal_zone"].astype(bool).to_numpy()[:, None]

    # ---- elevation: gate = inside [min, max]; factor = distance inside the nearest edge / margin
    emin, emax = sv("elev_min_m"), sv("elev_max_m")
    elev_known = ~np.isnan(elev) & ~np.isnan(emin) & ~np.isnan(emax)
    elev_gate_ok = ~elev_known | ((elev >= emin) & (elev <= emax))
    margin = mf * (emax - emin)
    f_hi = _edge_factor(emax - elev, margin)
    # a lower limit of 0 m is sea level, a floor of the data convention, not a tolerance edge: no fall-off there
    f_lo = np.where(emin <= 0, 1.0, _edge_factor(elev - emin, margin))
    f_elev = np.where(elev_known, np.minimum(f_hi, f_lo), np.nan)

    # ---- slope: gate = slope <= max_slope_pct; factor falls over the top `margin` of the 0..max range
    smax = sv("max_slope_pct")
    slope_known = ~np.isnan(slope) & ~np.isnan(smax)
    f_slope = np.where(slope_known, _edge_factor(smax - slope, mf * smax), np.nan)     # inside the limit: unchanged (0 at the limit itself)
    over = slope_known & (slope > smax)
    if smode == "hard":
        slope_gate_ok = ~slope_known | (slope <= smax)
        g_slope = np.ones_like(f_slope)
    else:                                                    # graded: factor 1 inside the limit, falling linearly to 0 at limit + gm x limit, then the hard stop
        slope_gate_ok = ~slope_known | (slope <= smax * (1.0 + gm))
        with np.errstate(divide="ignore", invalid="ignore"):
            g_slope = np.where(over, np.clip(1.0 - (slope - smax) / (gm * smax), 0.0, 1.0), 1.0)

    # ---- soil: gate = species texture list contains the site texture, or any texture is fine
    tex_lists = [set(t.strip().lower() for t in str(v).split(";") if t.strip()) if pd.notna(v) else set() for v in sp["soil_textures"]]
    any_tex = sp["soil_any_texture"].astype(bool).to_numpy()[None, :]
    tex_col, tex_src = site_texture_column(si, soil_source)
    site_tex = si[tex_col].fillna("").astype(str).str.strip().str.lower().to_numpy()
    has_list = np.array([bool(s) for s in tex_lists])[None, :]
    match = np.zeros((np_, ns), dtype=bool)
    for j, s in enumerate(tex_lists):
        if s:
            fits = [t for t in np.unique(site_tex) if t and (SOIL_COMPAT.get(t, {t}) & s)]     # site textures that fit this species
            match[:, j] = np.isin(site_tex, fits)
    site_known = (site_tex != "")[:, None]
    soil_known = any_tex | (site_known & has_list)           # gate can be evaluated
    soil_mismatch = soil_known & ~(any_tex | match)
    if mode == "hard":
        soil_gate_ok = ~soil_mismatch                        # mismatch zeroes S
        mismatch_factor = 0.0
    else:
        soil_gate_ok = np.ones((np_, ns), dtype=bool)        # mismatch only lowers the factor and the confidence
        mismatch_factor = SOIL_MISMATCH_FACTOR if soil_mismatch_factor is None else soil_mismatch_factor
    f_soil = np.where(soil_known, np.where(soil_mismatch, mismatch_factor, 1.0), np.nan)

    # ---- wetness: tolerance level, relaxed linearly to 1 at the risk distance from the water
    tol = sp["waterlog_tol"].map(WATERLOG_TOL_LEVEL).to_numpy(dtype=float)[None, :]
    wet_known = ~np.isnan(water) & ~np.isnan(tol)
    f_wet = np.where(wet_known, tol + (1.0 - tol) * np.clip(water / wet_r, 0.0, 1.0), np.nan)

    # ---- combine
    factors = {"elevation": f_elev, "slope": f_slope, "soil": f_soil, "wetness": f_wet}
    num = np.zeros((np_, ns)); den = np.zeros((np_, ns)); tot = sum(w[k] for k in factors)
    for k, f in factors.items():
        ok = ~np.isnan(f)
        num += np.where(ok, w[k] * np.nan_to_num(f), 0.0); den += np.where(ok, w[k], 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        s_soft = np.where(den > 0, num / den, 0.0)
    gate_ok = legal & elev_gate_ok & slope_gate_ok & soil_gate_ok
    s_rule = np.where(gate_ok, s_soft * g_slope, 0.0)
    slope_graded = over & slope_gate_ok & gate_ok & (s_rule >= ELIGIBLE_S) if smode == "graded" else np.zeros_like(over)   # eligible ONLY because of the graded rule (it would be S = 0 under "hard")
    # share of the weight that could actually be evaluated; a soil mismatch (unverified mapping) does not count as evaluated
    confidence = (den - np.where(soil_mismatch, w["soil"], 0.0)) / tot

    gate_fail = {
        "legal_zone": np.broadcast_to(~legal, (np_, ns)), "elevation": ~elev_gate_ok,
        "slope": ~slope_gate_ok, "soil": ~soil_gate_ok,
    }
    rows = {"point_id": np.repeat(si["point_id"].to_numpy(), ns), "species_id": np.tile(sp["species_id"].to_numpy(), np_),
            "s_rule": s_rule.ravel(), "confidence": confidence.ravel()}
    for k, f in factors.items():
        rows["f_" + k] = f.ravel()
    for k, g in gate_fail.items():
        rows["gate_fail_" + k] = np.ascontiguousarray(g).ravel()
    rows["slope_graded"] = np.ascontiguousarray(slope_graded).ravel()
    rows["slope_over_pct"] = np.where(over, slope - smax, 0.0).ravel()
    rows["soil_unverified_mismatch"] = (soil_mismatch & (mode == "soft")).ravel()
    rows["soil_lgu_used"] = ((soil_known & site_known & has_list & ~any_tex) if tex_src == "lgu" else np.zeros((np_, ns), dtype=bool)).ravel()   # the soil term was evaluated from the LGU map
    for k, ok in (("elevation", elev_known), ("slope", slope_known), ("soil", soil_known), ("wetness", wet_known)):
        rows["known_" + k] = np.broadcast_to(ok, (np_, ns)).ravel()
    rows["s_prob"] = np.full(np_ * ns, np.nan)
    return pd.DataFrame(rows)


def source_lookup(sources):
    """{(species_id, field_name): {'source_id', 'url', 'rank'}} from species_sources (one row per species-field)."""
    d = {}
    for r in sources.itertuples(index=False):
        d[(int(r.species_id), r.field_name)] = {"source_id": int(r.source_id),
                                                "url": None if pd.isna(r.source_url) else r.source_url,
                                                "rank": None if pd.isna(r.source_rank) else int(r.source_rank)}
    return d


def build_breakdown(scores, species, sites, src, weights=None):
    """
    breakdown_json per row: {"gate_failed": [...], "flags": [...], "terms": {term: {"value", "weight", "src": [source_id, ...]}}}.
    flags holds "soil_unverified_mismatch" when (soft mode) the soil texture does not match the species list.
    value is null when the term could not be evaluated (unknown input; left out of S). `src` holds the species_sources.source_id
    of the species fields behind the term (resolve URL + source_rank with: SELECT source_url, source_rank FROM species_sources
    WHERE source_id IN (...)). IDs instead of URLs keep the 281k-row table at tens of MB instead of hundreds.
    """
    w = TERM_WEIGHTS if weights is None else weights
    term_src = {(int(sid), term): sorted({src[(int(sid), f)]["source_id"] for f in fields if (int(sid), f) in src})
                for sid in species.species_id for term, fields in TERM_FIELDS.items()}
    out = []
    for r in scores.itertuples(index=False):
        sid = int(r.species_id)
        terms = {}
        for term in TERM_FIELDS:
            v = getattr(r, "f_" + term)
            terms[term] = {"value": None if (not getattr(r, "known_" + term) or v != v) else round(float(v), 3),
                           "weight": w[term], "src": term_src[(sid, term)]}
        gates = [g for g in ("legal_zone", "elevation", "slope", "soil") if getattr(r, "gate_fail_" + g)]
        flags = ["soil_unverified_mismatch"] if r.soil_unverified_mismatch else []
        if r.slope_graded:
            flags.append(SLOPE_GRADED_FLAG)
        if r.soil_lgu_used:
            flags.append(SOIL_PROVISIONAL_FLAG)
        out.append(json.dumps({"gate_failed": gates, "flags": flags, "terms": terms}, separators=(",", ":")))
    return out


def run(out_dir, water_shp, soil_gate_mode=None, soil_source=None, slope_mode=None):
    out = Path(out_dir)
    dest = out / "scores"
    dest.mkdir(parents=True, exist_ok=True)
    species = pd.read_csv(out / "species_clean.csv")
    sources = pd.read_csv(out / "species_sources.csv")
    sites = pd.read_csv(out / "site_points_clean.csv")
    n_all = len(sites)
    if "zoning_status" in sites:                                     # acceptance: all confirmed + unconfirmed points x species (excluded zones stay unscored)
        sites = sites[sites.zoning_status.isin(["confirmed", "unconfirmed"])].copy()
    else:
        sites = sites[sites.is_legal_zone.astype(bool)].copy()
    sites["water_dist_m"] = distance_to_water(sites, water_shp) if water_shp else np.nan
    scores = score_pairs(species, sites, soil_gate_mode=soil_gate_mode, soil_source=soil_source, slope_mode=slope_mode)
    scores["breakdown_json"] = build_breakdown(scores, species, sites, source_lookup(sources))
    final = scores[["point_id", "species_id", "s_rule", "s_prob", "breakdown_json", "confidence"]].copy()
    final["s_rule"] = final.s_rule.round(4); final["confidence"] = final.confidence.round(4)
    final.to_csv(dest / "site_scores.csv", index=False)
    con = sqlite3.connect(dest / "site_scores.db")
    con.execute("DROP TABLE IF EXISTS site_scores")
    con.execute("CREATE TABLE site_scores(point_id INTEGER, species_id INTEGER, s_rule REAL, s_prob REAL NULL, "
                "breakdown_json TEXT, confidence REAL)")
    con.executemany("INSERT INTO site_scores VALUES (?,?,?,?,?,?)",
                    ((int(a), int(b), float(c), None, e, float(f)) for a, b, c, _, e, f in final.itertuples(index=False)))
    con.execute("CREATE INDEX ix_scores_pt ON site_scores(point_id, species_id)")
    con.execute("CREATE INDEX ix_scores_sp ON site_scores(species_id)")
    con.commit(); con.close()
    viable = scores.groupby("species_id").s_rule.apply(lambda s: int((s >= 0.5).sum()))
    print(f"soil gate mode: {SOIL_GATE_MODE if soil_gate_mode is None else soil_gate_mode}")
    smode = SLOPE_MODE if slope_mode is None else slope_mode
    print(f"slope mode: {smode}" + (f" (margin {SLOPE_GRADED_MARGIN_FRACTION:.0%} of the species limit; {int(scores.slope_graded.sum())} pairs eligible only because of it)" if smode == "graded" else " (the old gate)"))
    (dest / "score_run.json").write_text(json.dumps({"slope_mode": smode, "slope_graded_margin_fraction": SLOPE_GRADED_MARGIN_FRACTION if smode == "graded" else None,
                                                     "soil_gate_mode": SOIL_GATE_MODE if soil_gate_mode is None else soil_gate_mode, "pairs": int(len(final)),
                                                     "eligible_pairs": int((scores.s_rule >= ELIGIBLE_S).sum()), "slope_graded_pairs": int(scores.slope_graded.sum())}, indent=1), encoding="utf-8")
    col, src = site_texture_column(sites, soil_source)
    print(f"soil source: {src} ({col}); squares with a texture: {int(sites[col].notna().sum())} of {len(sites)}")
    zs = sites.zoning_status.value_counts().to_dict() if "zoning_status" in sites else {}
    print(f"points scored: {len(sites)} of {n_all} {zs or ''}| species: {len(species)} | rows: {len(final)}")
    print(f"water distance available for {int(sites.water_dist_m.notna().sum())} points")
    print(f"S >= 0.50 pairs: {int((scores.s_rule >= 0.5).sum())} ({(scores.s_rule >= 0.5).mean():.1%}); S == 0: {(scores.s_rule == 0).mean():.1%}")
    print(f"species with no viable (S>=0.50) point: {int((viable == 0).sum())}")
    print(f"written to {dest}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--water", default="data/SMR_WATERBODIES_POLY.shp", help="waterbodies layer for the wetness term")
    ap.add_argument("--soil-gate-mode", choices=("soft", "hard"), default=None, help=f"override SOIL_GATE_MODE ({SOIL_GATE_MODE})")
    ap.add_argument("--slope-mode", choices=("graded", "hard"), default=None, help=f"override SLOPE_MODE ({SLOPE_MODE}); hard = the old slope gate")
    ap.add_argument("--soil-source", choices=("lgu", "legacy"), default=None, help=f"override SOIL_SOURCE ({SOIL_SOURCE})")
    a = ap.parse_args()
    run(a.out, a.water, a.soil_gate_mode, a.soil_source, a.slope_mode)


if __name__ == "__main__":
    main()
