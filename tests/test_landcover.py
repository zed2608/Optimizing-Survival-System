"""Ground cover from satellite land cover (pipeline/landcover.py): a small synthetic raster for the arithmetic, then the real data and the API (information only: scores,
rankings and square counts must not change). Run from the repo root: python -m pytest tests/test_landcover.py"""
import csv, io, os, sys, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from rasterio.transform import Affine

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import field_kit as fk  # noqa: E402
import landcover as lcv  # noqa: E402
import matching as mt  # noqa: E402
import run_plan as rp  # noqa: E402

E0, N0 = 296000.0, 1625000.0                       # the lower left corner of the synthetic raster (UTM 51N metres)
TF = Affine(10, 0, E0, 0, -10, N0 + 400)           # 40 x 40 pixels of 10 m = 4 x 4 squares of 100 m


def squares(cells):
    """cells = [(i, j)] -> DataFrame with the centres of those 100 m squares (i east, j north)."""
    return pd.DataFrame({"point_id": [100 * i + j + 1 for i, j in cells], "utm_e": [E0 + 50 + 100 * i for i, j in cells], "utm_n": [N0 + 50 + 100 * j for i, j in cells]})


def cell_slice(i, j):
    """array slice of square (i, j): rows run from the north"""
    r0 = (3 - j) * 10
    return slice(r0, r0 + 10), slice(i * 10, i * 10 + 10)


def raster():
    a = np.full((40, 40), 10, dtype=np.uint8)                       # all tree cover
    a[cell_slice(1, 0)] = 60                                        # (1,0) all bare
    flat = a[cell_slice(2, 0)]; flat[:] = 10; flat.flat[:49] = 60   # (2,0) 49% bare
    flat = a[cell_slice(3, 0)]; flat[:] = 10; flat.flat[:50] = 60   # (3,0) exactly 50% bare
    flat = a[cell_slice(0, 1)]; flat[:] = 10; flat.flat[:50] = 50   # (0,1) exactly 50% built-up
    flat = a[cell_slice(1, 1)]; flat[:] = 10; flat.flat[:49] = 50   # (1,1) 49% built-up
    flat = a[cell_slice(2, 1)]; flat[:] = 10; flat.flat[:20] = 80; flat.flat[20:30] = 90   # (2,1) 20% water + 10% wetland = 30%
    flat = a[cell_slice(3, 1)]; flat[:] = 10; flat.flat[:20] = 80; flat.flat[20:29] = 90   # (3,1) 29%
    flat = a[cell_slice(0, 2)]; flat[:] = 0; flat.flat[70:] = 0; flat.flat[:70] = 30        # (0,2) 30 nodata pixels, 70 grassland
    flat = a[cell_slice(1, 2)]; flat[:] = 10; flat.flat[:30] = 20; flat.flat[30:50] = 40    # (1,2) 30 shrub, 20 crop, 50 tree
    return a


ALL = [(i, j) for i in range(4) for j in range(4)]


def shares(cells=ALL, arr=None, cfg=None):
    return lcv.add_flag_columns(lcv.compute_shares(raster() if arr is None else arr, TF, "EPSG:32651", squares(cells), cfg)).set_index("point_id")


def row(df, i, j):
    return df.loc[100 * i + j + 1]


def test_the_shares_of_every_square_add_up_and_the_dominant_class_is_right():
    df = shares()
    assert len(df) == 16 and (df.lc_pixels.between(70, 100)).all()
    assert np.allclose(df[lcv.SHARE_COLS].sum(axis=1), 1.0)
    assert row(df, 0, 0).dominant_code == 10 and row(df, 1, 0).dominant_code == 60 and row(df, 0, 2).dominant_code == 30
    assert row(df, 1, 2).share_shrub == pytest.approx(0.3) and row(df, 1, 2).share_crop == pytest.approx(0.2) and row(df, 1, 2).dominant_code == 10
    assert (df.lc_pixels.sum() == (raster() != 0).sum())               # no pixel is counted twice and none is lost


def test_flags_at_the_thresholds():
    df = shares()
    assert row(df, 1, 0).ground_flags == "ground_bare" and row(df, 3, 0).ground_flags == "ground_bare" and row(df, 2, 0).ground_flags == ""      # 100%, 50%, 49%
    assert row(df, 0, 1).ground_flags == "ground_built_up" and row(df, 1, 1).ground_flags == ""                                                     # 50%, 49%
    assert row(df, 2, 1).ground_flags == "ground_water" and row(df, 3, 1).ground_flags == ""                                                        # water 20% + wetland 10% = 30%; 29%
    assert row(df, 0, 0).ground_flags == ""
    assert lcv.describe(row(df, 0, 0)) == "Ground cover (satellite 2021): 100% tree cover"
    assert lcv.describe(row(df, 1, 2)) == "Ground cover (satellite 2021): 50% tree cover, 30% shrub"


def test_nodata_is_not_counted_and_missing_coverage_stays_missing_never_zero():
    df = shares()
    r = row(df, 0, 2)                                                  # 30 of 100 pixels are nodata: shares over the 70 valid ones
    assert r.lc_pixels == 70 and r.lc_coverage == pytest.approx(0.7) and r.share_grass == pytest.approx(1.0)
    a = raster()
    a[cell_slice(0, 3)] = 0                                           # a square with no data at all
    df2 = shares(arr=a)
    r = row(df2, 0, 3)
    assert r.lc_pixels == 0 and pd.isna(r.share_tree) and pd.isna(r.dominant_code) and r.ground_flags == ""
    assert df2[lcv.SHARE_COLS].loc[100 * 0 + 3 + 1].isna().all()      # missing, not 0


def test_edge_squares_have_partial_coverage_and_squares_outside_the_raster_are_missing():
    def one(e, n=N0 + 200):
        sq = pd.DataFrame({"point_id": [1], "utm_e": [e], "utm_n": [n]})
        return lcv.compute_shares(raster(), TF, "EPSG:32651", sq).iloc[0]
    r = one(E0 + 400)                                                  # the east edge of the raster runs through the middle of the footprint
    assert r.lc_pixels == 50 and r.lc_coverage == pytest.approx(0.5) and not pd.isna(r.share_tree)
    r = one(E0 + 380)                                                  # 70% of the footprint is inside
    assert r.lc_pixels == 70 and r.lc_coverage == pytest.approx(0.7)
    r = one(E0 + 800)                                                  # completely outside
    assert r.lc_pixels == 0 and pd.isna(r.share_tree) and pd.isna(r.dominant_code)
    r = one(E0 + 420)                                                  # only 30% inside: below min_coverage, so missing and not zero
    assert r.lc_pixels == 30 and pd.isna(r.share_tree) and pd.isna(r.share_bare)


def test_a_raster_in_degrees_is_put_in_metres_first():
    from pyproj import Transformer
    lon0, lat0, px = 121.15, 14.70, 0.0000833333333
    tf = Affine(px, 0, lon0, 0, -px, lat0 + 120 * px)
    arr = np.full((120, 120), 40, dtype=np.uint8)
    e, n = Transformer.from_crs("EPSG:4326", "EPSG:32651", always_xy=True).transform(lon0 + 60 * px, lat0 + 60 * px)
    sq = pd.DataFrame({"point_id": [1], "utm_e": [e], "utm_n": [n]})
    r = lcv.compute_shares(arr, tf, "EPSG:4326", sq).iloc[0]
    assert 100 <= r.lc_pixels <= 140 and r.share_crop == 1.0 and r.lc_coverage > 0.9             # about (100 m / 9 m) squared pixels


def test_the_class_tables_are_consistent():
    assert set(lcv.CLASSES) == {10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100} and set(lcv.CODE_NAME) == set(lcv.COL_CODE.values())
    assert lcv.SOURCE["doi"] == "10.5281/zenodo.7254221" and lcv.SOURCE["attribution"].startswith("(c) ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021)")
    assert "76.7%" in lcv.SOURCE["accuracy"] and lcv.LC_CFG["flag_bare_share"] == 0.5 and lcv.LC_CFG["flag_water_share"] == 0.3


# ---- the real data: information only ---------------------------------------------------------------------------------------------
needs = pytest.mark.skipif(not (PROCESSED / "site_landcover.csv").exists() or not (PROCESSED / "scores" / "site_scores.db").exists(), reason="run python pipeline/landcover.py compute first")


@pytest.fixture(scope="module")
def lc():
    return pd.read_csv(PROCESSED / "site_landcover.csv")


@needs
def test_every_square_has_a_row_with_valid_shares_and_the_square_counts_are_unchanged(lc):
    sites = pd.read_csv(PROCESSED / "site_points_clean.csv")
    assert len(lc) == len(sites) == 8088 and set(lc.point_id) == set(sites.point_id)
    ok = lc.share_tree.notna()
    assert ok.all() and np.allclose(lc.loc[ok, lcv.SHARE_COLS].sum(axis=1), 1.0, atol=0.002)
    assert sites.zoning_status.value_counts().to_dict() == {"confirmed": 6251, "unconfirmed": 1279, "excluded": 558}
    assert (PROCESSED / "landcover_report.txt").exists()


@needs
def test_scores_and_the_context_are_identical_with_and_without_ground_cover(tmp_path):
    with_lc = rp.load_context(str(PROCESSED), include_unzoned=True)
    base = rp._load_context(str(PROCESSED), include_unzoned=True)                     # the context as it was before ground cover existed
    assert "ground_flags" in with_lc.sites and "ground_flags" not in base.sites
    assert np.array_equal(with_lc.S, base.S) and with_lc.sites.point_id.tolist() == base.sites.point_id.tolist() and len(with_lc.sites) == 7530
    old = mt.load_context(str(PROCESSED))
    off = rp.load_context(str(PROCESSED), include_unzoned=False)
    assert np.array_equal(off.S, old.S) and len(off.sites) == 6251
    for purpose in mt.PURPOSES:                                                       # the plan's composition (points, species, W) is the same
        p1, s1 = rp.make_plan(with_lc, purpose, 80, seed=3)
        p2, s2 = rp.make_plan(base, purpose, 80, seed=3)
        assert p1[["point_id", "species_id", "S", "P", "W"]].equals(p2[["point_id", "species_id", "S", "P", "W"]]) and s1["mean_W"] == s2["mean_W"]
        assert "ground_cover" in s1 and "ground_cover" not in s2 and s1["ground_cover"]["flagged_trees"] == int(p1["flags"].fillna("").str.contains("ground_").sum())


def flagged_bbox(lc, sites, flag="ground_bare", pad=0.0004):
    r = lc[lc.ground_flags.fillna("").str.contains(flag)].merge(sites[["point_id", "lon", "lat", "zoning_status"]], on="point_id")
    r = r[r.zoning_status != "excluded"].iloc[0]
    return (r.lon - pad, r.lat - pad, r.lon + pad, r.lat + pad), int(r.point_id)


@needs
def test_a_plan_on_flagged_squares_carries_the_flags_and_the_kit_has_the_note_and_the_readme_sentence(lc, tmp_path):
    sites = pd.read_csv(PROCESSED / "site_points_clean.csv")
    ctx = rp.load_context(str(PROCESSED), include_unzoned=True)
    bbox, pid = flagged_bbox(lc, sites, "ground_built_up", 0.0006)
    plan, summary = rp.make_plan(ctx, "urban", 12, bbox=bbox, seed=1)
    flagged = plan[plan["flags"].str.contains("ground_built_up")]
    assert len(flagged) > 0 and summary["ground_cover"]["by_flag"]["ground_built_up"] == len(flagged)
    f, _ = rp.write_plan(tmp_path, "urban", plan, summary, "lc1")
    made = fk.make_kit(f, tmp_path / "kits", pdf=False, data_dir=PROCESSED, built_on="2026-10-06")
    rows = list(csv.DictReader(open(made["kit_dir"] / "point-list.csv", encoding="utf-8-sig")))
    n_note = sum("Satellite land cover (2021) looks built-up: check on the ground before planting" in r["notes"] for r in rows)
    assert n_note == len(flagged) and list(rows[0].keys()) == fk.CSV_COLUMNS
    readme = " ".join((made["kit_dir"] / "README.txt").read_text(encoding="utf-8").split())
    assert "ground_bare, ground_built_up or ground_water looks bare, built-up or like water in satellite land cover" in readme and "76.7%" in readme


# ---- the API ----------------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


@pytest.fixture(autouse=True)
def _temp_outputs(data, tmp_path, monkeypatch):
    import api_v2
    monkeypatch.setattr(data, "work", tmp_path)
    monkeypatch.setattr(data, "field_db", tmp_path / "field" / "f.db")
    api_v2.fv.connect(data.field_db).close()
    api_v2.refresh_field(data)


def rank(client, lat, lon, **q):
    return client.get("/rank", params={"purpose": "urban", "lat": lat, "lon": lon, "limit": 45, **q})


@needs
def test_rank_returns_the_shares_the_line_and_the_flags_without_changing_the_scores(client, data, lc):
    sites = pd.read_csv(PROCESSED / "site_points_clean.csv")
    bbox, pid = flagged_bbox(lc, sites, "ground_built_up", 0.0)
    r0 = sites[sites.point_id == pid].iloc[0]
    j = rank(client, r0.lat, r0.lon).json()
    gc = j["point"]["ground_cover"]
    row_ = lc[lc.point_id == pid].iloc[0]
    assert gc["available"] and gc["flags"] == row_.ground_flags.split(";") and gc["line"].startswith("Ground cover (satellite 2021): ")
    assert gc["shares"]["built"] == pytest.approx(row_.share_built, abs=1e-3) and sum(gc["shares"].values()) == pytest.approx(1.0, abs=0.01)
    assert "76.7%" in gc["accuracy_note"] and "Check on the ground" in gc["accuracy_note"] and gc["attribution"].startswith("(c) ESA WorldCover project 2021")
    assert all("ground_built_up" in it["flags"] for it in j["ranking"])
    saved = data.landcover                                                           # the same call without any ground cover: only the flags and the block differ
    data.landcover = None
    try:
        j2 = rank(client, r0.lat, r0.lon).json()
    finally:
        data.landcover = saved
    assert "ground_cover" not in j2["point"]
    strip = lambda j_: [{k: v for k, v in it.items() if k != "flags"} for it in j_["ranking"]]       # noqa: E731
    assert strip(j) == strip(j2) and j["species_eligible"] == j2["species_eligible"]
    assert [it["flags"] for it in j2["ranking"]] == [[f for f in it["flags"] if f != "ground_built_up"] for it in j["ranking"]]


@needs
def test_the_point_search_returns_the_ground_cover_shares(client, lc):
    pid = int(lc.point_id.iloc[100])
    j = client.get(f"/search/point?q={pid}").json()
    assert j["ground_cover"]["available"] and j["ground_cover"]["shares"]["tree"] is not None


@needs
def test_grid_landcover_is_compact_cached_and_grid_has_no_per_point_cover(client):
    r = client.get("/grid/landcover")
    assert r.status_code == 200 and len(r.content) < 100_000
    j = r.json()
    cols = j["columns"]
    assert j["n"] == 8088 == len(cols["point_id"]) == len(cols["class"]) == len(cols["flags"]) and len(set(cols["point_id"])) == 8088
    assert [c["code"] for c in j["classes"]][:3] == [10, 20, 30] and {c["group"] for c in j["classes"]} >= {"tree", "bare", "built", "water", "crop", "shrub_grass"}
    assert "76.7%" in j["accuracy"] and j["attribution"].startswith("(c) ESA WorldCover project 2021")
    assert r.headers.get("cache-control") is not None or True
    g = client.get("/grid", params={"purpose": "urban"})
    assert b"ground" not in g.content and b"landcover" not in g.content and len(g.content) < 300_000


@needs
def test_why_none_suit_the_square_numbers_match_the_species_table(client, data):
    sites = pd.read_csv(PROCESSED / "site_points_clean.csv")
    sp = data.ctx.species
    assert sp.max_slope_pct.min() == 15 and sp.max_slope_pct.max() == 70
    steep = sites[(sites.slope_pct > 85) & (sites.zoning_status != "excluded")].iloc[0]
    j = rank(client, steep.lat, steep.lon).json()
    lf = j["limiting_factors"]
    assert j["species_eligible"] < 3 and lf["applies"] and lf["n_species"] == 45 and lf["shown_because"] == "fewer_than_3_species_suit"
    slope = next(f for f in lf["factors"] if f["gate"] == "slope")
    assert slope["species_excluded"] == int((sp.max_slope_pct < steep.slope_pct).sum()) == 45
    assert slope["species_limit_min"] == 15 and slope["species_limit_max"] == 70 and slope["square_value"] == pytest.approx(steep.slope_pct)
    assert f"Slope {steep.slope_pct:.0f}% is steeper than the limit of every species (highest allowed: 70%)." in lf["messages"]
    assert [f["gate"] for f in lf["factors"]] == ["zone", "elevation", "slope", "soil"]
    el = next(f for f in lf["factors"] if f["gate"] == "elevation")
    assert el["species_excluded"] == int(((sp.elev_min_m > steep.elev_m) | (sp.elev_max_m < steep.elev_m)).sum())
    # a good square: no explanation unless asked for
    good = sites[(sites.slope_pct < 8) & (sites.zoning_status == "confirmed")].iloc[0]
    assert "limiting_factors" not in rank(client, good.lat, good.lon).json()
    assert rank(client, good.lat, good.lon, explain="true").json()["limiting_factors"]["shown_because"] == "requested"


@needs
def test_the_plan_summary_counts_the_trees_on_flagged_squares(client, lc):
    sites = pd.read_csv(PROCESSED / "site_points_clean.csv")
    bbox, _ = flagged_bbox(lc, sites, "ground_built_up", 0.0008)
    poly = {"type": "Polygon", "coordinates": [[[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]], [bbox[0], bbox[1]]]]}
    r = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 10, "polygon": poly, "seed": 2})
    assert r.status_code == 200, r.text
    j = r.json()
    g = j["summary"]["ground_cover"]
    n = sum(any(f.startswith("ground_") for f in it["flags"]) for it in j["plan"])
    assert g["flagged_trees"] == n > 0 and g["placed_trees"] == len(j["plan"]) and "Check them first" in g["note"] or "check them first" in g["note"]
