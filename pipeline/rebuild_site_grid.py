#!/usr/bin/env python3
"""
rebuild_site_grid.py - Day 1 site grid rebuild.

Fixes the defects found in backend/Working_Points.csv:
  * slope_1 is an exact copy of elevation_  -> real slope (percent) is recomputed from the elevation grid
  * soil_ph is random (uniform 5.5-7.5)      -> dropped (no real pH layer yet; do not score pH)
  * 167 rows repeat a grid cell              -> one row per cell (keeps the first nearest-feature match, n == 1)
  * no land-use zone on the points           -> zone joined from LandUses.shp; legal flag from the 11 legal zones

Slope method: finite differences on the ~100 m grid (central difference where both neighbours exist,
one-sided at edges and holes). It is coarse: 100 m cells smooth real terrain. State this in the thesis.

Outputs (data/processed):
    site_points_clean.csv     one row per grid cell
    grid_report.txt           counts, coverage, dropped columns
    optimizing_survival.db    table site_points (replaced)

Usage:
    python pipeline/rebuild_site_grid.py --input backend/Working_Points.csv --landuse data/LandUses.shp --out data/processed
"""
import argparse, sqlite3, sys
from pathlib import Path
import numpy as np
import pandas as pd

# ZONE_RULES: what each land-use zone of data/LandUses.shp means for planting. ONE table; change a value, then re-run the scripts listed in CLAUDE.md
# ("How to change a zone rule"). Values:
#   confirmed   = a planting zone the MPDC has answered for: scored, no zoning flag          (is_legal_zone = True)
#   unconfirmed = scored like the others but flagged zoning_unconfirmed; the flag note names the zone (an LGU decision is still needed)
#   excluded    = never scored, never planned (grey square)
# Round 15a: the answers of the MPDC (Elaine R. De Jesus, MENRO PO III / OIC), signed form of 7 Oct 2026 ("open to tree planting?"):
#   Yes: Forest, Agricultural, Socialized Housing, Buffer, Parks and Recreation, General Institutional (and the LGU spelling Zonec), Special Reserved, Medium Industrial,
#        Minor Commercial, Light Industrial, Major Commercial and Major Commercial Mixed Use (no squares in the grid).
#   Yes with conditions: High Density Residential, Medium Density Residential, Institutional Research, Sanitary Landfill (written note "w/ DENR").
#   No: Cemetery, Quarry Sub-Zone.  The area outside the zoning map (Forest Reserve, Watershed) is open and stays flagged. data/LandUses.shp is the current layer.
# Before round 15a: 6,251 confirmed / 1,279 unconfirmed / 558 excluded.
ZONE_RULES = {
    "Forest Zone": "confirmed",                                # MPDC 7 Oct 2026: yes
    "Agricultural Zone": "confirmed",                          # MPDC: yes
    "Socialized Housing Zone": "confirmed",                    # MPDC: yes
    "Buffer Zone": "confirmed",                                # MPDC: yes
    "Parks and Recreation Zone": "confirmed",                  # MPDC: yes
    "General Institutional Zone": "confirmed",                 # MPDC: yes
    "General Institutional Zonec": "confirmed",                # MPDC: yes (the LGU spelling 'Zonec' is kept as written in the layer)
    "Special Reserved Zone": "confirmed",                      # MPDC: yes (355 squares; may be converted to other use)
    "Medium Industrial Zone": "confirmed",                     # MPDC: yes (65 squares; may be converted to other use)
    "Minor Commercial - Mixed Use Zone": "confirmed",          # MPDC: yes (61 squares; may be converted to other use)
    "Light Industrial Zone": "confirmed",                      # MPDC: yes (3 squares; may be converted to other use)
    "High Density Residential - Mixed Use Zone": "confirmed",  # MPDC: yes with conditions (private land: needs permission)
    "Medium Density Residential Zone": "confirmed",            # MPDC: yes with conditions (private land: needs permission)
    "Institutional Research Zone": "confirmed",                # MPDC: yes with conditions (needs permission)
    "Sanitary Landfill": "confirmed",                          # MPDC: yes with conditions, written note "w/ DENR" (19 squares)
    "Major Commercial Zone": "confirmed",                      # MPDC: yes (no grid squares)
    "Major Commercial - Mixed Use Zone": "confirmed",          # MPDC: yes (no grid squares)
    "Cemetery Zone": "excluded",                               # MPDC: no (23 squares)
    "Quarry Sub-Zone": "excluded",                             # MPDC: no (55 squares)
}
# ZONE_CONDITION: a short plain text per zone for the squares that are open only with a condition (PROVISIONAL: from the MPDC interview of 7 Oct 2026, to be confirmed in writing).
# Added to every square as zone_condition (empty = no condition). The field kit, the API and the dashboard can show it.
ZONE_CONDITION_PRIVATE = "needs permission (private land)"
ZONE_CONDITION_DENR = "needs DENR permission"
ZONE_CONDITION_CONVERT = "may be converted to other use"
ZONE_CONDITION_FOREST_RESERVE = "inside Forest Reserve: MENRO/DENR permit"
ZONE_CONDITIONS = {
    "High Density Residential - Mixed Use Zone": ZONE_CONDITION_PRIVATE,
    "Medium Density Residential Zone": ZONE_CONDITION_PRIVATE,
    "Institutional Research Zone": ZONE_CONDITION_PRIVATE,
    "Sanitary Landfill": ZONE_CONDITION_DENR,
    "Special Reserved Zone": ZONE_CONDITION_CONVERT,
    "Medium Industrial Zone": ZONE_CONDITION_CONVERT,
    "Minor Commercial - Mixed Use Zone": ZONE_CONDITION_CONVERT,
    "Light Industrial Zone": ZONE_CONDITION_CONVERT,
}
OUTSIDE_ZONING_CONDITION = ZONE_CONDITION_FOREST_RESERVE      # a square outside every zoning polygon
ZONE_CONDITION_SOURCE = "MPDC (Elaine R. De Jesus, MENRO PO III/OIC), signed form of 7 Oct 2026; provisional"
UNKNOWN_ZONE_RULE = "excluded"          # a zone name that is not in ZONE_RULES (the rebuild report lists it)
OUTSIDE_ZONING_RULE = "unconfirmed"     # a square outside every zoning polygon: the satellite shows forest, the zoning file has a gap (set "excluded" to leave them out)
RULE_VALUES = ("confirmed", "unconfirmed", "excluded")
VALID_ZONES = [z for z, r in ZONE_RULES.items() if r == "confirmed"]   # the legal zones (kept for older readers of this module)
# SOIL_SOURCE: where the soil texture of the scores comes from. "lgu" = the LGU soil map (BSWM), digitized by us (pipeline/lgu_soil.py; PROVISIONAL, not verified by the agriculturist);
# "legacy" = the four world-soil-database codes with their legacy textures (also UNVERIFIED). The legacy columns are always kept; with "legacy" nothing else is written.
SOIL_SOURCE = "lgu"
SOIL_SOURCE_TEXT = "LGU soil map (BSWM), digitized by us, provisional"
# Legacy translation from backend/app.py. UNVERIFIED - needs a sourced mapping before it is used for hard limits.
SOIL_LEGACY = {
    4478: ("Gleyic Cambisol", "Clay Loam"), 4413: ("Nitisol", "Clay"),
    4546: ("Rhodic Nitisol", "Clay"), 7001: ("Technosol", None),
}
REQUIRED = ["row_index", "col_index", "x", "y", "elevation_", "soil_type", "feature_x", "feature_y", "TYPE", "n", "distance"]

def zone_condition(zone_desc, conditions=None):
    """The plain condition text of every square (empty text = open without a condition); a square outside every polygon gets OUTSIDE_ZONING_CONDITION."""
    c = ZONE_CONDITIONS if conditions is None else conditions
    z = pd.Series(zone_desc)
    return np.where(z.isna(), OUTSIDE_ZONING_CONDITION, z.map(lambda n: c.get(n, "")))


def zoning_status(zone_desc, rules=None):
    """confirmed | unconfirmed | excluded for every square, from ZONE_RULES (a square outside every polygon follows OUTSIDE_ZONING_RULE)."""
    r = ZONE_RULES if rules is None else rules
    bad = [v for v in list(r.values()) + [UNKNOWN_ZONE_RULE, OUTSIDE_ZONING_RULE] if v not in RULE_VALUES]
    if bad:
        raise ValueError(f"zone rules must be one of {RULE_VALUES}, got {bad}")
    z = pd.Series(zone_desc)
    return np.where(z.isna(), OUTSIDE_ZONING_RULE, z.map(lambda n: r.get(n, UNKNOWN_ZONE_RULE)))


def derivative(Z, step, axis):
    """Finite difference along axis. Returns (d, kind) with kind 2=central, 1=one-sided, 0=none."""
    Zp = np.roll(Z, -1, axis=axis); Zm = np.roll(Z, 1, axis=axis)
    if axis == 1: Zp[:, -1] = np.nan; Zm[:, 0] = np.nan
    else: Zp[-1, :] = np.nan; Zm[0, :] = np.nan
    central = (Zp - Zm) / (2 * step); fwd = (Zp - Z) / step; bwd = (Z - Zm) / step
    d = np.where(np.isfinite(central), central, np.where(np.isfinite(fwd), fwd, bwd))
    kind = np.where(np.isfinite(central), 2, np.where(np.isfinite(fwd) | np.isfinite(bwd), 1, 0))
    return d, kind

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default="backend/Working_Points.csv")
    ap.add_argument("--landuse", default="data/LandUses.shp", help="optional; needs geopandas")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--soil-source", choices=("lgu", "legacy"), default=None, help=f"override SOIL_SOURCE ({SOIL_SOURCE}); legacy = the output of before, byte for byte")
    ap.add_argument("--soil-csv", default=None, help="the digitized LGU soil table (default <out>/site_soil_lgu.csv, made by pipeline/lgu_soil.py)")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rep = []
    d = pd.read_csv(a.input)
    miss = [c for c in REQUIRED if c not in d.columns]
    if miss: sys.exit(f"missing columns in {a.input}: {miss}")
    rep.append(f"input rows: {len(d)}")

    # ---- sanity findings on the legacy columns
    same = bool((d["elevation_"] == d.get("slope_1", np.nan)).all()) if "slope_1" in d else False
    rep.append(f"legacy slope_1 identical to elevation_ in every row: {same}")
    if "soil_ph" in d:
        rep.append(f"legacy soil_ph range {d.soil_ph.min():.2f}-{d.soil_ph.max():.2f}, distinct values {d.soil_ph.nunique()} of {len(d)} -> synthetic, dropped")

    # ---- one row per cell
    d = d.sort_values(["row_index", "col_index", "n"]).drop_duplicates(["row_index", "col_index"], keep="first").reset_index(drop=True)
    rep.append(f"rows after one-per-cell: {len(d)} (removed {int(rep[0].split(': ')[1]) - len(d)} repeated-cell rows)")

    # ---- slope from the elevation grid
    R, C = int(d.row_index.max()) + 1, int(d.col_index.max()) + 1
    Z = np.full((R, C), np.nan); X = np.full((R, C), np.nan); Y = np.full((R, C), np.nan)
    Z[d.row_index, d.col_index] = d.elevation_; X[d.row_index, d.col_index] = d.x; Y[d.row_index, d.col_index] = d.y
    lat0 = float(np.nanmedian(Y))
    dx = float(np.nanmedian(np.abs(np.diff(X, axis=1)))) * 111320 * np.cos(np.radians(lat0))
    dy = float(np.nanmedian(np.abs(np.diff(Y, axis=0)))) * 110574
    rep.append(f"grid {R} x {C}; cell size ~{dx:.1f} m (E-W) x {dy:.1f} m (N-S)")
    gx, kx = derivative(Z, dx, 1); gy, ky = derivative(Z, dy, 0)
    gx0 = np.where(np.isfinite(gx), gx, 0.0); gy0 = np.where(np.isfinite(gy), gy, 0.0)
    slope_pct = 100 * np.hypot(gx0, gy0)
    have = (kx > 0) | (ky > 0)
    method = np.where((kx == 2) & (ky == 2), "full", np.where(have, "partial", "none"))
    d["slope_pct"] = np.where(have[d.row_index, d.col_index], slope_pct[d.row_index, d.col_index], np.nan).round(2)
    d["slope_deg"] = np.degrees(np.arctan(d.slope_pct / 100)).round(2)
    d["slope_method"] = method[d.row_index, d.col_index]
    v = d.slope_pct.dropna()
    rep.append(f"slope method: {d.slope_method.value_counts().to_dict()}  (partial = only one axis available, may under-estimate)")
    rep.append(f"slope % median {v.median():.1f}, p90 {v.quantile(.9):.1f}, max {v.max():.1f}; share > 30%: {(v > 30).mean():.1%}; > 50%: {(v > 50).mean():.1%}")

    # ---- clean output table
    o = pd.DataFrame({
        "point_id": d["id"].astype(int), "cell_row": d.row_index.astype(int), "cell_col": d.col_index.astype(int),
        "lon": d.x.round(6), "lat": d.y.round(6),
        "utm_e": d.feature_x.round(1), "utm_n": d.feature_y.round(1),            # UTM zone 51N (point coordinates in the source file)
        "elev_m": d.elevation_.astype(float), "slope_pct": d.slope_pct, "slope_deg": d.slope_deg, "slope_method": d.slope_method,
        "soil_code": d.soil_type.astype(int),
        "soil_name_legacy": d.soil_type.map(lambda c: SOIL_LEGACY.get(int(c), (None, None))[0]),
        "soil_texture_legacy": d.soil_type.map(lambda c: SOIL_LEGACY.get(int(c), (None, None))[1]),
        "soil_mapping_status": "unverified",
        "nearest_feature_type": d.TYPE, "nearest_feature_class": d.get("CLASS"), "nearest_feature_dist_m": d.distance.round(1),
    })
    if o.point_id.duplicated().any():
        rep.append("WARNING: point_id not unique after dedupe; using cell index as id"); o["point_id"] = range(1, len(o) + 1)

    # ---- land-use zone
    try:
        import geopandas as gpd
        zones = gpd.read_file(a.landuse)
        pts = gpd.GeoDataFrame(o[["point_id"]], geometry=gpd.points_from_xy(o.lon, o.lat), crs="EPSG:4326")
        if zones.crs is not None and zones.crs.to_string() != "EPSG:4326": zones = zones.to_crs("EPSG:4326")
        j = gpd.sjoin(pts, zones[["CODE", "DESCRIPTIO", "geometry"]], how="left", predicate="within").drop_duplicates("point_id")
        z = j.set_index("point_id")
        o["zone_code"] = o.point_id.map(z["CODE"]); o["zone_desc"] = o.point_id.map(z["DESCRIPTIO"])
        o["zoning_status"] = zoning_status(o.zone_desc)
        o["is_legal_zone"] = o.zoning_status == "confirmed"                  # confirmed legal zone ONLY (unchanged meaning)
        o["zone_condition"] = np.where(o.zoning_status == "excluded", "", zone_condition(o.zone_desc))      # round 15a: a short plain condition for squares that are open only with permission
        unknown = sorted(set(o.zone_desc.dropna()) - set(ZONE_RULES))
        if unknown:
            rep.append(f"WARNING: zones not in ZONE_RULES (treated as {UNKNOWN_ZONE_RULE}): {unknown}")
        rep.append(f"points with a land-use zone: {o.zone_desc.notna().sum()} of {len(o)}; legal zones: {int(o.is_legal_zone.sum())}")
        rep.append("zoning_status: " + str(o.zoning_status.value_counts().to_dict())
                   + "  (confirmed = inside a legal zone; unconfirmed = outside every zoning polygon, scored but flagged; excluded = a named non-planting zone, not scored)")
        rep.append("zones: " + str(o.zone_desc.fillna("(outside zoning)").value_counts().to_dict()))
        rep.append("zone_condition: " + str(o.zone_condition.replace("", "(none)").value_counts().to_dict()) + "  (" + ZONE_CONDITION_SOURCE + ")")
    except Exception as e:                                               # geopandas missing or file missing
        rep.append(f"land-use join SKIPPED: {e}")
        o["zone_code"] = None; o["zone_desc"] = None; o["is_legal_zone"] = None; o["zoning_status"] = None; o["zone_condition"] = None

    soil_source = a.soil_source or SOIL_SOURCE
    if soil_source not in ("lgu", "legacy"):
        sys.exit(f"SOIL_SOURCE must be 'lgu' or 'legacy', got {soil_source!r}")
    if soil_source == "lgu":                                             # the LGU soil map digitized by pipeline/lgu_soil.py (the legacy columns above are KEPT)
        f = Path(a.soil_csv) if a.soil_csv else out / "site_soil_lgu.csv"
        if not f.is_file():
            sys.exit(f"SOIL_SOURCE is 'lgu' but {f} is missing: run  python pipeline/lgu_soil.py compute --out {out}  first (or use --soil-source legacy)")
        s = pd.read_csv(f).set_index("point_id")
        o["soil_series_lgu"] = o.point_id.map(s["soil_series"])
        o["soil_texture_lgu"] = o.point_id.map(s["soil_texture"])
        o["soil_purity"] = o.point_id.map(s["purity"])
        o["soil_source"] = np.where(o.soil_series_lgu.notna(), SOIL_SOURCE_TEXT, None)
        rep.append(f"soil source: LGU soil map ({f.name}): series for {int(o.soil_series_lgu.notna().sum())} of {len(o)} squares ({int(o.soil_series_lgu.isna().sum())} without: outside the soil map); "
                   + str(o.soil_series_lgu.value_counts().to_dict()))
        rep.append("soil texture (LGU): " + str(o.soil_texture_lgu.value_counts().to_dict()) + "  (PROVISIONAL: scanned map digitized by us, not verified by the agriculturist)")
    rep.append("soil codes: " + str(o.soil_code.value_counts().to_dict()) + "  (texture mapping is UNVERIFIED)")
    rep.append("dropped columns: slope_1 (copy of elevation), soil_ph (synthetic), Recommende, Survivabil (legacy outputs), polygon/shape columns")
    rep.append("NOT available yet: real soil pH, rainfall, temperature, existing mature trees, canopy context")

    o.to_csv(out / "site_points_clean.csv", index=False)
    (out / "grid_report.txt").write_text("\n".join(rep) + "\n")
    con = sqlite3.connect(out / "optimizing_survival.db"); o.to_sql("site_points", con, if_exists="replace", index=False)
    con.execute("CREATE INDEX IF NOT EXISTS ix_site_en ON site_points(utm_e, utm_n)"); con.commit(); con.close()
    print("\n".join(rep)); print("written to", out)

if __name__ == "__main__":
    main()
