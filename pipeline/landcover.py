#!/usr/bin/env python3
"""
landcover.py - ground cover of every grid square from ESA WorldCover 10 m (2021, v200). INFORMATION AND FLAGS ONLY: no score, rank or plan depends on it.

  python pipeline/landcover.py clip      # read ONE window of the public cloud-optimised tile (a few MB) and save it under data/external/worldcover/
  python pipeline/landcover.py compute   # offline: shares of each class inside every 100 m square -> data/processed/site_landcover.csv (+ DB table, report)

For every grid square the 10 m pixels whose centre lies inside the square (centre +/- 50 m, worked out in metres in UTM 51N) are counted; the share of each class is
count / valid pixels. A pixel with the raster's nodata value (0) is not counted. A square whose valid pixels cover less than MIN_COVERAGE of the footprint keeps its
shares EMPTY (missing, never zero). Data: ESA WorldCover 10 m 2021 v200, DOI 10.5281/zenodo.7254221, CC BY 4.0 (see docs/DATA_SOURCES.md).
"""
import argparse, sqlite3, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# =====================================================================================================================
# CONFIG - PROVISIONAL (thresholds of the information flags; the agriculturist / LGU should confirm them)
# =====================================================================================================================
LC_CFG = {
    "tile_url": "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E120_Map.tif",
    "clip_file": "data/external/worldcover/worldcover_2021_v200_sanmateo.tif",
    "clip_margin_deg": 0.004,           # the window is the grid's bounding box plus this margin (about 400 m)
    "site_crs": "EPSG:32651",           # UTM 51N, the CRS of utm_e / utm_n
    "half_side_m": 50.0,                # a square is its centre +/- 50 m
    "min_coverage": 0.5,                # shares are missing when fewer than this part of the footprint has valid pixels
    "flag_bare_share": 0.50,            # ground_bare: bare / sparse vegetation share >= this
    "flag_built_share": 0.50,           # ground_built_up: built-up share >= this
    "flag_water_share": 0.30,           # ground_water: water + herbaceous wetland + mangrove share >= this
    "info_tree_share": 0.50,            # an information line (not a flag) when tree cover >= this
    "barangay_shp": "data/BRGY_BOUNDARY.shp",
}
# ESA codes -> (column, plain name). 70 snow/ice and 100 moss/lichen are summed in "other".
CLASSES = {
    10: ("share_tree", "tree cover"), 20: ("share_shrub", "shrubland"), 30: ("share_grass", "grassland"), 40: ("share_crop", "cropland"),
    50: ("share_built", "built-up"), 60: ("share_bare", "bare or sparse vegetation"), 80: ("share_water", "permanent water"),
    90: ("share_wetland", "herbaceous wetland"), 95: ("share_mangrove", "mangroves"), 70: ("share_other", "snow and ice"), 100: ("share_other", "moss and lichen"),
}
SHARE_COLS = ["share_tree", "share_shrub", "share_grass", "share_crop", "share_built", "share_bare", "share_water", "share_wetland", "share_mangrove", "share_other"]
COL_CODE = {"share_tree": 10, "share_shrub": 20, "share_grass": 30, "share_crop": 40, "share_built": 50, "share_bare": 60, "share_water": 80, "share_wetland": 90,
            "share_mangrove": 95, "share_other": 100}
CODE_NAME = {10: "tree cover", 20: "shrubland", 30: "grassland", 40: "cropland", 50: "built-up", 60: "bare or sparse vegetation", 80: "permanent water",
             90: "herbaceous wetland", 95: "mangroves", 100: "other (snow, ice, moss, lichen)"}
FLAG_NOTES = {
    "ground_bare": "Satellite land cover (2021) looks bare: check on the ground before planting",
    "ground_built_up": "Satellite land cover (2021) looks built-up: check on the ground before planting",
    "ground_water": "Satellite land cover (2021) looks like water or wetland: check on the ground before planting",
}
SOURCE = {
    "name": "ESA WorldCover 10 m 2021 v200", "doi": "10.5281/zenodo.7254221", "license": "CC BY 4.0", "year": 2021,
    "attribution": "(c) ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium",
    "accuracy": "global overall accuracy 76.7% (Product Validation Report V2.0, Wageningen University and IIASA)",
    "url": "https://esa-worldcover.org/en/data-access",
}
# =====================================================================================================================


def clip(cfg=None, source=None, dest=None):
    """Read one window of the tile (the grid's bounding box plus a margin) and save it as a small GeoTIFF. Needs the internet ONCE. source = a local tile path or the URL."""
    import rasterio
    from rasterio.windows import from_bounds
    c = LC_CFG if cfg is None else cfg
    pts = pd.read_csv(ROOT / "data" / "processed" / "site_points_clean.csv", usecols=["lon", "lat"])
    m = c["clip_margin_deg"]
    bounds = (pts.lon.min() - m, pts.lat.min() - m, pts.lon.max() + m, pts.lat.max() + m)
    src_path = source or ("/vsicurl/" + c["tile_url"])
    out = Path(dest or ROOT / c["clip_file"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(src_path) as s:
        win = from_bounds(*bounds, transform=s.transform).round_offsets().round_lengths()
        data = s.read(1, window=win)
        prof = s.profile.copy()
        prof.update(driver="GTiff", height=data.shape[0], width=data.shape[1], transform=s.window_transform(win), compress="deflate", tiled=False, blockxsize=None, blockysize=None)
        for k in ("blockxsize", "blockysize"):
            prof.pop(k, None)
        prof.pop("tiled", None)
        with rasterio.open(out, "w", **prof) as d:
            d.write(data, 1)
            d.update_tags(source=c["tile_url"], product=SOURCE["name"], doi=SOURCE["doi"], license=SOURCE["license"], attribution=SOURCE["attribution"])
    print(f"clipped window {bounds} -> {out} ({out.stat().st_size / 1e6:.2f} MB, {data.shape[1]} x {data.shape[0]} pixels)")
    return out


def compute_shares(arr, transform, crs, squares, cfg=None, nodata=0):
    """
    Shares of every class inside each square. arr = 2-D class codes, transform / crs = those of the raster, squares = DataFrame with point_id, utm_e, utm_n.
    The pixel centres are put in metres (cfg site_crs) and a pixel belongs to the square whose centre is within +/- half_side_m (both axes). Returns one row per square:
    lc_pixels (valid pixels), lc_coverage (valid pixels / pixels expected), share_* columns (NaN when coverage < min_coverage), dominant_code (NaN when missing).
    """
    from scipy.spatial import cKDTree
    c = LC_CFG if cfg is None else cfg
    h, w = arr.shape
    rows, cols = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    xs, ys = transform * (cols.ravel() + 0.5, rows.ravel() + 0.5)
    xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    crs_s = str(crs)
    if crs_s != c["site_crs"] and not crs_s.endswith(c["site_crs"].split(":")[-1]):
        from pyproj import Transformer
        xs, ys = Transformer.from_crs(crs_s, c["site_crs"], always_xy=True).transform(xs, ys)
    codes = arr.ravel()
    half = c["half_side_m"]
    ctr = squares[["utm_e", "utm_n"]].to_numpy(dtype=float)
    tree = cKDTree(ctr)
    dist, idx = tree.query(np.column_stack([xs, ys]), k=1, p=np.inf, distance_upper_bound=half + 1e-6)
    n = len(squares)
    inside = idx < n                                                      # cKDTree answers n for "nothing within the bound"
    # a pixel exactly on a shared edge is given to one square only (the nearest, then the first): no pixel is counted twice
    tot = np.bincount(idx[inside], minlength=n + 1)[:n]
    valid_px = inside & (codes != nodata)
    out = {"point_id": squares.point_id.to_numpy()}
    counts = {col: np.zeros(n) for col in SHARE_COLS}
    for code, (col, _) in CLASSES.items():
        m = valid_px & (codes == code)
        counts[col] += np.bincount(idx[m], minlength=n + 1)[:n]
    valid = np.sum([counts[col] for col in SHARE_COLS], axis=0)          # valid pixels of a known class
    other_px = np.bincount(idx[valid_px], minlength=n + 1)[:n] - valid   # valid pixels with a code that is not in the table: counted as "other"
    counts["share_other"] += other_px
    valid = valid + other_px
    pix_m = float(np.median(np.abs(np.diff(xs[:w])))) if w > 1 else 10.0
    expected = (2 * half / max(pix_m, 1e-9)) ** 2 if pix_m > 0 else np.nan
    # coverage is judged against the pixels that exist inside the footprint (valid + nodata) AND against a full footprint, so a square at the raster's edge is partly missing
    coverage = np.where(expected > 0, valid / expected, 0.0)
    coverage = np.clip(coverage, 0.0, 1.0)
    ok = (coverage >= c["min_coverage"]) & (valid > 0)
    out["lc_pixels"] = valid.astype(int)
    out["lc_coverage"] = np.round(coverage, 3)
    for col in SHARE_COLS:
        out[col] = np.where(ok, counts[col] / np.where(valid > 0, valid, 1), np.nan)
    df = pd.DataFrame(out)
    sh = df[SHARE_COLS].to_numpy()
    codes_by_col = np.array([COL_CODE[col] for col in SHARE_COLS])
    with np.errstate(all="ignore"):
        best = np.nanargmax(np.where(np.isnan(sh), -1.0, sh), axis=1)     # ties go to the first column (the lower ESA code)
    df["dominant_code"] = np.where(ok, codes_by_col[best], np.nan)
    return df


def ground_flags(row, cfg=None):
    """['ground_bare', ...] for one row of shares (empty list when the shares are missing)."""
    c = LC_CFG if cfg is None else cfg
    if pd.isna(row["share_tree"]):
        return []
    fl = []
    if row["share_bare"] >= c["flag_bare_share"] - 1e-9:
        fl.append("ground_bare")
    if row["share_built"] >= c["flag_built_share"] - 1e-9:
        fl.append("ground_built_up")
    if row["share_water"] + row["share_wetland"] + row["share_mangrove"] >= c["flag_water_share"] - 1e-9:
        fl.append("ground_water")
    return fl


def add_flag_columns(df, cfg=None):
    """df with the share columns -> adds ground_flags (';'-joined) and the share_water_all column (water + wetland + mangrove)."""
    df = df.copy()
    df["ground_flags"] = [";".join(ground_flags(r, cfg)) for _, r in df.iterrows()]
    return df


def describe(row, cfg=None):
    """The one line of the point panel: 'Ground cover (satellite 2021): 62% tree cover, 30% bare' (the two biggest shares of at least 5%), or None when missing."""
    if pd.isna(row["share_tree"]):
        return None
    names = {"share_tree": "tree cover", "share_shrub": "shrub", "share_grass": "grass", "share_crop": "cropland", "share_built": "built-up", "share_bare": "bare",
             "share_water": "water", "share_wetland": "wetland", "share_mangrove": "mangrove", "share_other": "other"}
    top = sorted(((row[c_], n_) for c_, n_ in names.items() if row[c_] >= 0.05), reverse=True)[:2]
    return "Ground cover (satellite 2021): " + ", ".join(f"{round(100 * s)}% {n_}" for s, n_ in top) if top else "Ground cover (satellite 2021): no class reaches 5%"


def run(out_dir="data/processed", raster=None, cfg=None):
    import rasterio
    c = LC_CFG if cfg is None else cfg
    out = Path(out_dir)
    sites = pd.read_csv(out / "site_points_clean.csv")
    path = Path(raster or ROOT / c["clip_file"])
    if not path.is_file():
        sys.exit(f"{path} not found: run  python pipeline/landcover.py clip  once (needs the internet), then compute works offline")
    with rasterio.open(path) as s:
        arr = s.read(1)
        sh = compute_shares(arr, s.transform, s.crs, sites, c, nodata=s.nodata if s.nodata is not None else 0)
    sh = add_flag_columns(sh, c)
    sh["dominant_class"] = sh.dominant_code.map(lambda v: CODE_NAME.get(int(v)) if pd.notna(v) else None)
    for col in SHARE_COLS:
        sh[col] = sh[col].round(4)
    sh.to_csv(out / "site_landcover.csv", index=False)
    con = sqlite3.connect(out / "optimizing_survival.db")
    sh.to_sql("site_landcover", con, if_exists="replace", index=False)
    con.execute("CREATE INDEX IF NOT EXISTS ix_site_landcover ON site_landcover(point_id)")
    con.commit()
    con.close()
    # report: counts per dominant class, overall and per barangay
    rep = [f"ground cover from {SOURCE['name']} ({SOURCE['doi']}), {SOURCE['license']}", f"raster: {path.name}", f"squares: {len(sh)}; with shares: {int(sh.share_tree.notna().sum())}; missing: {int(sh.share_tree.isna().sum())}",
           "dominant class: " + str(sh.dominant_class.value_counts(dropna=False).to_dict()),
           "flags: " + str({f: int(sh.ground_flags.str.contains(f).sum()) for f in FLAG_NOTES}),
           f"thresholds (provisional): bare >= {c['flag_bare_share']:.0%}, built-up >= {c['flag_built_share']:.0%}, water >= {c['flag_water_share']:.0%}, tree-cover info >= {c['info_tree_share']:.0%}"]
    try:
        import geopandas as gpd
        g = gpd.read_file(ROOT / c["barangay_shp"]).to_crs("EPSG:4326")
        pts = gpd.GeoDataFrame(sites[["point_id"]], geometry=gpd.points_from_xy(sites.lon, sites.lat), crs="EPSG:4326")
        j = gpd.sjoin(pts, g[["BRGY_NAME", "geometry"]], how="left", predicate="intersects").drop_duplicates("point_id").set_index("point_id")
        sh["barangay"] = sh.point_id.map(j.BRGY_NAME)
        tab = sh.groupby(["barangay", "dominant_class"], dropna=False).size().unstack(fill_value=0)
        rep += ["", "per barangay (squares by dominant class):", tab.to_string()]
    except Exception as e:                                               # geopandas or the shapefile missing: the report only loses this table
        rep.append(f"per-barangay table skipped: {e}")
    (out / "landcover_report.txt").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep[:6]))
    print("written to", out)
    return sh


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["clip", "compute"])
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--raster", help="clip: a local tile instead of the URL; compute: another clipped raster")
    a = ap.parse_args()
    if a.action == "clip":
        clip(source=a.raster)
    else:
        run(a.out, a.raster)


if __name__ == "__main__":
    main()
