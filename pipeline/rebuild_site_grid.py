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

VALID_ZONES = [  # same list as generate_targets.py / filter_zones.py (includes the LGU typo 'Zonec')
    "Parks and Recreation Zone", "Buffer Zone", "General Institutional Zone", "Institutional Research Zone",
    "Forest Zone", "General Institutional Zonec", "Medium Density Residential Zone",
    "High Density Residential - Mixed Use Zone", "Socialized Housing Zone", "Agricultural Zone", "Cemetery Zone",
]
# Legacy translation from backend/app.py. UNVERIFIED - needs a sourced mapping before it is used for hard limits.
SOIL_LEGACY = {
    4478: ("Gleyic Cambisol", "Clay Loam"), 4413: ("Nitisol", "Clay"),
    4546: ("Rhodic Nitisol", "Clay"), 7001: ("Technosol", None),
}
REQUIRED = ["row_index", "col_index", "x", "y", "elevation_", "soil_type", "feature_x", "feature_y", "TYPE", "n", "distance"]

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
        o["is_legal_zone"] = o.zone_desc.isin(VALID_ZONES)
        rep.append(f"points with a land-use zone: {o.zone_desc.notna().sum()} of {len(o)}; legal zones: {int(o.is_legal_zone.sum())}")
        rep.append("zones: " + str(o.zone_desc.fillna("(outside zoning)").value_counts().to_dict()))
    except Exception as e:                                               # geopandas missing or file missing
        rep.append(f"land-use join SKIPPED: {e}")
        o["zone_code"] = None; o["zone_desc"] = None; o["is_legal_zone"] = None

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
