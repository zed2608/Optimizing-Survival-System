#!/usr/bin/env python3
"""
qa_day1.py - automatic checks on the Day 1 outputs. Exit code 1 if any check FAILS.

    python pipeline/qa_day1.py --out data/processed
"""
import argparse, sqlite3, sys
from pathlib import Path
import numpy as np
import pandas as pd

results = []
def check(name, ok, detail="", warn=False):
    results.append(("PASS" if ok else ("WARN" if warn else "FAIL"), name, detail))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="data/processed"); a = ap.parse_args()
    out = Path(a.out)
    sp = pd.read_csv(out / "species_clean.csv"); src = pd.read_csv(out / "species_sources.csv")
    rep = pd.read_csv(out / "ingest_report.csv"); site = pd.read_csv(out / "site_points_clean.csv")

    # ---------------- species
    check("45 species rows", len(sp) == 45, f"{len(sp)} rows")
    check("species names unique and clean", sp.common_name.is_unique and not sp.common_name.str.contains(r"\[").any())
    cited = src[src.source_url.notna()].groupby("species_id").size().reindex(sp.species_id).fillna(0)
    check("every species has cited values", (cited > 0).all(), f"min cited cells per species = {int(cited.min())}")
    check("every species has >= 30 cited cells", (cited >= 30).all(), f"min = {int(cited.min())}", warn=True)
    for lo, hi in (("elev_min_m", "elev_max_m"), ("rain_min_mm", "rain_max_mm"), ("temp_min_c", "temp_max_c"), ("ph_min", "ph_max"), ("spacing_min_m", "spacing_max_m")):
        bad = sp[(sp[lo].notna()) & (sp[hi].notna()) & (sp[lo] > sp[hi])]
        check(f"{lo} <= {hi}", bad.empty, ", ".join(bad.common_name))
    for c in ("shade_tol", "drought_tol", "waterlog_tol", "typhoon_res"):
        bad = sp[~sp[c].isin(["Low", "Medium", "High"]) & sp[c].notna()]
        check(f"{c} in Low/Medium/High", bad.empty, ", ".join(bad.common_name))
        check(f"{c} filled for all species", sp[c].notna().all(), f"{int(sp[c].isna().sum())} missing", warn=True)
    check("growth_rate in Slow/Medium/Fast", sp.growth_rate.dropna().isin(["Slow", "Medium", "Fast"]).all())
    mm = sp.planting_months.dropna().map(lambda s: all(1 <= int(x) <= 12 for x in str(s).split(";")))
    check("planting months within 1-12", mm.all(), f"{int(sp.planting_months.isna().sum())} species without months", warn=False)
    check("corona types parsed", sp.corona_types.notna().all(), f"{int(sp.corona_types.isna().sum())} missing")
    check("at least one purpose tag per species", (sp.purpose_urban | sp.purpose_planting | sp.purpose_watershed).all(),
          ", ".join(sp[~(sp.purpose_urban | sp.purpose_planting | sp.purpose_watershed)].common_name), warn=True)
    url_rows = src[src.source_url.fillna("").str.startswith("http")]
    check("every URL source has a rank", url_rows.source_rank.notna().all())
    nonurl = src[src.source_url.notna() & ~src.source_url.fillna("").str.startswith("http")]
    check("cells citing a file that was not provided", nonurl.empty, f"{len(nonurl)} cells ({', '.join(sorted(set(src.loc[nonurl.index, 'species'])))}) - upload the file to verify", warn=True)
    high = rep[(rep.severity == "high") & (rep.issue != "file_source_not_provided")]
    check("no high-severity issues besides missing files", high.empty, f"{len(high)}: {dict(high.issue.value_counts())}")
    off = int(src.off_list.sum()); check("cited URLs outside your SOURCES list", off == 0, f"{off} cells - add them to the list deliberately or fix", warn=True)
    con = sqlite3.connect(out / "optimizing_survival.db")
    tabs = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    check("database tables present", {"species", "species_sources", "dataset_versions", "site_points"} <= tabs, str(sorted(tabs)))
    if "species" in tabs: check("db species rows match csv", con.execute("select count(*) from species").fetchone()[0] == len(sp))
    if "site_points" in tabs: check("db site_points rows match csv", con.execute("select count(*) from site_points").fetchone()[0] == len(site))
    con.close()

    # ---------------- site grid
    check("one row per grid cell", not site.duplicated(["cell_row", "cell_col"]).any(), f"{len(site)} cells")
    check("slope is not a copy of elevation", (site.slope_pct.dropna() - site.elev_m[site.slope_pct.notna()]).abs().max() > 1)
    check("slope within 0-200 %", site.slope_pct.dropna().between(0, 200).all(), f"max {site.slope_pct.max():.1f}")
    check("slope computed for >= 99% of cells", site.slope_pct.notna().mean() >= 0.99, f"{site.slope_pct.notna().mean():.1%}")
    part = (site.slope_method == "partial").mean()
    check("cells with a full (two-axis) slope", part < 0.15, f"{part:.1%} are 'partial' (one axis only; may under-estimate)", warn=True)
    # bounds of data/BRGY_BOUNDARY.shp are lon 121.107-121.252, lat 14.642-14.741; small tolerance added
    check("coordinates inside the San Mateo bounds", site.lon.between(121.10, 121.26).all() and site.lat.between(14.64, 14.75).all())
    check("no synthetic pH column", "soil_ph" not in site.columns and "ph" not in site.columns)
    if "zone_desc" in site and site.zone_desc.notna().any():
        out_z = site.zone_desc.isna().mean()
        check("points inside zoning polygons", out_z < 0.20, f"{out_z:.1%} are outside zoning", warn=True)
        check("legal-zone flag present", site.is_legal_zone.notna().all(), f"{int(site.is_legal_zone.sum())} legal points")
    else:
        check("land-use zone joined", False, "run with geopandas and data/LandUses.shp", warn=True)

    w = max(len(n) for _, n, _ in results)
    for s, n, d in results: print(f"[{s}] {n.ljust(w)}  {d}")
    f = sum(1 for s, _, _ in results if s == "FAIL"); wn = sum(1 for s, _, _ in results if s == "WARN")
    print(f"\n{len(results) - f - wn} passed, {wn} warnings, {f} failed")
    sys.exit(1 if f else 0)

if __name__ == "__main__":
    main()
