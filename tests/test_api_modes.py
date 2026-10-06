"""Tests for the two-way setup in api_v2.py: GET /grid with several species, GET /areas/rank, GET /geo/zones, POST /rank/area.
Run from the repo root:  python -m pytest tests/test_api_modes.py"""
import re, sys
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

PURPOSES = ("urban", "planting", "watershed")
GRID_LIMIT = 250_000


@pytest.fixture(scope="module")
def client():
    api_v2.API_CFG["include_unzoned"] = False            # these tests pin the behaviour of include_unzoned=false (the squares outside the zoning map are not planting squares)
    try:
        with TestClient(api_v2.app) as c:
            yield c
    finally:
        api_v2.API_CFG["include_unzoned"] = True


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


def walk(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)
    else:
        yield o


def wmat(data, purpose, ids):
    ks = [data.species_idx[i] for i in ids]
    S, P = data.ctx.S[:, ks], data.ctx.P[purpose][ks]
    return np.where(S >= 0.5, S * P[None, :], 0.0), S >= 0.5


def box(minlon, minlat, maxlon, maxlat):
    return {"type": "Polygon", "coordinates": [[[minlon, minlat], [maxlon, minlat], [maxlon, maxlat], [minlon, maxlat], [minlon, minlat]]]}


def zone_box(data, zone, pad=0.0005):
    s = data.ctx.sites[data.ctx.sites.zone_desc == zone]
    return box(s.lon.min() - pad, s.lat.min() - pad, s.lon.max() + pad, s.lat.max() + pad)


# ---- GET /grid with several species ------------------------------------------------------------------------------------
@pytest.mark.parametrize("purpose", PURPOSES)
@pytest.mark.parametrize("ids", [[8], [8, 22], [1, 2, 8, 13, 36]])
def test_all_is_never_above_any_at_any_point(client, purpose, ids):
    q = {"purpose": purpose, "species_ids": ",".join(map(str, ids))}
    a = client.get("/grid", params={**q, "mode": "all"}).json()["columns"]["W"]
    b = client.get("/grid", params={**q, "mode": "any"}).json()["columns"]["W"]
    assert len(a) == len(b) == 6251 and all(x <= y + 1e-9 for x, y in zip(a, b))
    assert sum(1 for x in a if x > 0) <= sum(1 for y in b if y > 0)


@pytest.mark.parametrize("mode", ["all", "any"])
def test_multi_grid_matches_an_independent_calculation(client, data, mode):
    ids = [3, 8, 22, 40]
    j = client.get("/grid", params={"purpose": "urban", "species_ids": "40,8,3,22,8", "mode": mode}).json()      # order and duplicates do not matter
    W, feas = wmat(data, "urban", ids)
    want = np.where(feas.all(axis=1), W.min(axis=1), 0.0) if mode == "all" else W.max(axis=1)
    c = j["columns"]
    assert np.allclose(c["W"], want, atol=6e-4) and j["species_ids"] == ids and j["mode"] == mode and j["species_id"] == -1
    assert np.array_equal(c["n_eligible_species"], feas.sum(axis=1))                                             # how many SELECTED species suit the point
    best = np.array(c["best_species_id"])
    arr = np.array(ids)
    assert (best[want == 0] == -1).all() and (best[want > 0] == (arr[W.argmin(axis=1)] if mode == "all" else arr[W.argmax(axis=1)])[want > 0]).all()
    if mode == "all":
        suitable = np.array(c["W"]) > 0
        assert (suitable == feas.all(axis=1)).all()                                  # suitable only if every selected species has S >= 0.50
        assert (np.array(c["n_eligible_species"])[suitable] == len(ids)).all()


def test_one_species_gives_the_same_scores_in_both_modes_and_as_the_old_parameter(client):
    old = client.get("/grid", params={"purpose": "watershed", "species_id": 8}).json()
    for mode in ("all", "any"):
        new = client.get("/grid", params={"purpose": "watershed", "species_ids": "8", "mode": mode}).json()
        assert new["columns"]["W"] == old["columns"]["W"] and new["columns"]["best_species_id"] == old["columns"]["best_species_id"]
        assert new["columns"]["point_id"] == old["columns"]["point_id"]


def test_multi_grid_is_compact_has_no_nulls_and_documents_itself(client):
    import re as _re
    r = client.get("/grid", params={"purpose": "planting", "species_ids": "1,2,3,4,5,6,7,8", "mode": "any"})
    j = r.json()
    assert len(r.content) < GRID_LIMIT, len(r.content)
    assert None not in list(walk(j)) and not _re.search(rb"[:\[,]null", r.content)
    assert j["missing"]["marker"] == -1 and "limiting" in client.get("/grid", params={"purpose": "planting", "species_ids": "1,2", "mode": "all"}).json()["best_species_meaning"]
    assert "HIGHEST" in j["w_definition"] and "selected species" in j["n_eligible_scope"]
    assert "max-age" in r.headers["cache-control"]


def test_an_empty_or_bad_selection_is_rejected_with_a_clear_message(client):
    for bad in ("", " ", ",", " , "):
        r = client.get("/grid", params={"purpose": "urban", "species_ids": bad})
        assert r.status_code == 422 and "at least one species id" in r.json()["detail"], bad
    assert client.get("/grid", params={"purpose": "urban", "species_ids": "a,b"}).status_code == 422
    assert client.get("/grid", params={"purpose": "urban", "species_ids": "1.5"}).status_code == 422
    r = client.get("/grid", params={"purpose": "urban", "species_ids": "1,999"})
    assert r.status_code == 404 and "999" in r.json()["detail"]
    assert client.get("/grid", params={"purpose": "urban", "species_ids": "1,2", "mode": "some"}).status_code == 422
    assert client.get("/grid", params={"purpose": "fruit", "species_ids": "1"}).status_code == 422
    r = client.get("/grid", params={"purpose": "urban", "species_id": 1, "species_ids": "1,2"})
    assert r.status_code == 422 and "not both" in r.json()["detail"]


def test_old_grid_calls_still_work(client, data):
    base = client.get("/grid", params={"purpose": "urban"})
    assert base.status_code == 200 and len(base.content) < GRID_LIMIT
    j = base.json()
    assert j["n"] == 6251 and j["species_id"] == -1 and j["mode"] == "best" and j["species_ids"] == [] and "all species" in j["n_eligible_scope"]
    W = np.where(data.ctx.S >= 0.5, data.ctx.S * data.ctx.P["urban"][None, :], 0.0)
    assert np.allclose(j["columns"]["W"], W.max(axis=1), atol=6e-4)
    one = client.get("/grid", params={"purpose": "urban", "species_id": 8}).json()
    assert one["species_id"] == 8 and one["mode"] == "single" and one["columns"]["W"] != j["columns"]["W"]
    assert client.get("/grid", params={"purpose": "fruit"}).status_code == 422
    assert client.get("/grid", params={"purpose": "urban", "species_id": 999}).status_code == 404
    assert all((p, None) in data.grid_cache for p in PURPOSES)


def test_multi_grids_are_cached_by_key_and_the_cache_is_bounded(client, data):
    a = client.get("/grid", params={"purpose": "urban", "species_ids": "5,1", "mode": "all"}).content
    assert ("urban", (1, 5), "all") in data.multi_cache
    assert client.get("/grid", params={"purpose": "urban", "species_ids": "1,5", "mode": "all"}).content == a == data.multi_cache[("urban", (1, 5), "all")]
    assert ("urban", (1, 5), "any") not in data.multi_cache
    for i in range(1, 45):
        client.get("/grid", params={"purpose": "planting", "species_ids": f"{i},{i + 1}", "mode": "any"})
    assert len(data.multi_cache) <= data.cfg["multi_cache_max"]


# ---- GET /areas/rank -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("by,n", [("barangay", 15), ("zone", 11)])
def test_areas_rank_is_a_ranked_table_that_matches_an_independent_calculation(client, data, by, n):
    ids = [8, 22]
    r = client.get("/areas/rank", params={"purpose": "urban", "species_ids": "22,8", "mode": "all", "by": by})
    assert r.status_code == 200 and len(r.content) < 20_000
    j = r.json()
    rows = j["areas"]
    assert j["n_areas"] == len(rows) == n and j["by"] == by and j["species_ids"] == ids and j["legal_points"] == 6251
    assert [x["rank"] for x in rows] == list(range(1, n + 1)) and [x["mean_W"] for x in rows] == sorted((x["mean_W"] for x in rows), reverse=True)
    assert sum(x["legal_points"] for x in rows) == 6251
    W, feas = wmat(data, "urban", ids)
    score = np.where(feas.all(axis=1), W.min(axis=1), 0.0)
    labels = data.ctx.sites.zone_desc.to_numpy() if by == "zone" else np.array(data.barangay_names, dtype=object)[data.point_barangay]
    for x in rows:
        m = labels == x["name"]
        assert x["legal_points"] == m.sum() and abs(x["mean_W"] - score[m].mean()) < 6e-4
        assert x["suitable_points"] == (score[m] > 0).sum() and abs(x["share_suitable"] - (score[m] > 0).mean()) < 1e-4
        if x["suitable_points"]:
            assert abs(x["mean_W_where_suitable"] - score[m][score[m] > 0].mean()) < 6e-4
        assert len(x["bbox"]) == 4 and x["bbox"][0] < x["bbox"][2] and x["display_name"]
    assert None not in list(walk(j))


def test_areas_rank_any_is_never_below_all_and_uses_the_missing_marker(client, data, monkeypatch):
    q = {"purpose": "watershed", "species_ids": "1,8,36,40", "by": "barangay"}
    a = {x["name"]: x for x in client.get("/areas/rank", params={**q, "mode": "all"}).json()["areas"]}
    b = {x["name"]: x for x in client.get("/areas/rank", params={**q, "mode": "any"}).json()["areas"]}
    assert all(a[k]["mean_W"] <= b[k]["mean_W"] + 1e-9 and a[k]["suitable_points"] <= b[k]["suitable_points"] for k in a)
    monkeypatch.setattr(data.ctx, "S", np.zeros_like(data.ctx.S))
    monkeypatch.setattr(data, "areas_cache", type(data.areas_cache)())
    j = client.get("/areas/rank", params=q).json()
    assert all(x["mean_W"] == 0 and x["suitable_points"] == 0 and x["share_suitable"] == 0 and x["mean_W_where_suitable"] == -1 for x in j["areas"])
    assert j["missing"]["marker"] == -1 and None not in list(walk(j))


def test_areas_rank_errors_and_cache(client, data):
    assert client.get("/areas/rank", params={"purpose": "urban", "species_ids": ""}).status_code == 422
    assert client.get("/areas/rank", params={"purpose": "urban"}).status_code == 422
    assert client.get("/areas/rank", params={"purpose": "urban", "species_ids": "1", "by": "street"}).status_code == 422
    assert client.get("/areas/rank", params={"purpose": "fruit", "species_ids": "1"}).status_code == 422
    assert client.get("/areas/rank", params={"purpose": "urban", "species_ids": "999"}).status_code == 404
    q = {"purpose": "planting", "species_ids": "4,5", "mode": "any", "by": "zone"}
    a = client.get("/areas/rank", params=q).content
    assert a == client.get("/areas/rank", params=q).content == data.areas_cache[("planting", (4, 5), "any", "zone")]


# ---- GET /geo/zones --------------------------------------------------------------------------------------------------
def test_geo_zones_are_dissolved_legal_zones_with_bboxes(client, data):
    r = client.get("/geo/zones")
    assert r.status_code == 200 and len(r.content) < 300_000
    j = r.json()
    names = [f["properties"]["name"] for f in j["features"]]
    assert names == sorted(data.ctx.sites.zone_desc.dropna().unique()) and len(names) == 11 and "General Institutional Zonec" in names
    from shapely.geometry import shape
    for f in j["features"]:
        g = shape(f["geometry"])
        x0, y0, x1, y1 = f["properties"]["bbox"]
        assert g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty and x0 <= g.bounds[0] and g.bounds[2] <= x1 and y0 <= g.bounds[1] and g.bounds[3] <= y1
        assert f["properties"]["legal_grid_points"] == int((data.ctx.sites.zone_desc == f["properties"]["name"]).sum())
    assert None not in list(walk(j))


# ---- POST /rank/area -------------------------------------------------------------------------------------------------
def post(client, **body):
    return client.post("/rank/area", json={"purpose": "urban", **body})


def test_rank_area_for_a_barangay_by_any_spelling(client, data):
    base = post(client, barangay="STA ANA")
    assert base.status_code == 200, base.text
    j = base.json()
    assert j["area"]["type"] == "barangay" and j["area"]["name"] == "STA ANA" and j["area"]["display_name"] == "Santa Ana" and j["area"]["legal_points"] == 59
    for spelling in ("Santa Ana", "sta. ana", "SANTA  ANA"):
        assert post(client, barangay=spelling).json()["ranking"] == j["ranking"]
    assert post(client, barangay="Santo Niño").json()["area"]["name"] == "STO NINO"
    rows = j["ranking"]
    assert [r["rank"] for r in rows] == list(range(1, 11)) and [r["species_score"] for r in rows] == sorted((r["species_score"] for r in rows), reverse=True)
    mask = data.point_barangay == data.barangay_names.index("STA ANA")
    P = data.ctx.P["urban"]
    for r in rows[:5]:
        k = data.species_idx[r["species_id"]]
        s = data.ctx.S[mask, k]
        el = s >= 0.5
        assert r["suitable_points"] == el.sum() and abs(r["share_of_area_suitable"] - el.mean()) < 1e-4 and abs(r["P"] - P[k]) < 1e-4
        assert abs(r["mean_W_where_suitable"] - (s[el] * P[k]).mean()) < 1e-3
        assert {"p_confidence", "mean_site_confidence", "flags", "source_ids"} <= set(r) and r["mean_site_confidence"] != -1
    assert j["area"]["points_with_a_suitable_species"] <= 59 and j["species_with_suitable_points"] >= 10


def test_rank_area_for_a_zone_is_case_insensitive(client, data):
    j = post(client, zone="forest zone", limit=5).json()
    assert j["area"]["type"] == "zone" and j["area"]["name"] == "Forest Zone" and j["area"]["legal_points"] == 4368 and j["returned"] == 5
    assert post(client, zone="Forest Zone", limit=5).json()["ranking"] == j["ranking"]
    assert post(client, zone="General Institutional Zonec").json()["area"]["legal_points"] == 2


def test_rank_area_for_a_polygon_and_the_whole_municipality_agrees_with_rank_municipal(client, data):
    poly = zone_box(data, "Agricultural Zone")
    j = post(client, polygon=poly).json()
    from shapely.geometry import shape
    import shapely
    inside = shapely.contains_xy(shape(poly), data.ctx.sites.lon.to_numpy(), data.ctx.sites.lat.to_numpy())
    assert j["area"]["type"] == "polygon" and j["area"]["legal_points"] == inside.sum() >= 224 and len(j["area"]["bbox"]) == 4
    assert post(client, polygon={"type": "Feature", "properties": {}, "geometry": poly}).json()["area"]["legal_points"] == inside.sum()
    big = post(client, polygon=box(121.0, 14.5, 121.4, 14.9), limit=45).json()
    muni = client.get("/rank/municipal", params={"purpose": "urban", "limit": 45}).json()["ranking"]
    by_id = {r["species_id"]: r for r in big["ranking"]}
    assert big["area"]["legal_points"] == 6251
    for m in muni:
        a = by_id[m["species_id"]]
        assert a["suitable_points"] == m["eligible_points"] and abs(a["share_of_area_suitable"] - m["share_of_points_eligible"]) < 1e-3
        assert abs(a["mean_W_where_suitable"] - m["mean_W_where_eligible"]) < 1e-3 and abs(a["species_score"] - m["species_score"]) < 1e-3


def test_rank_area_returns_the_suggested_mix_from_the_palette_code(client, data, tmp_path, monkeypatch):
    monkeypatch.setattr(data, "work", tmp_path)                                               # keep the saved plan out of data/processed/plans
    j = post(client, zone="Forest Zone", n_saplings=300).json()
    mix = j["mix"]
    sp = mix["species"]
    assert 6 <= len(sp) <= 10 and abs(sum(s["share"] for s in sp) - 1.0) < 2e-3 and mix["n_saplings"] == 300
    assert all(s["share"] <= mix["caps"]["max_species_share"] + 1e-9 for s in sp)
    from collections import defaultdict
    g = defaultdict(float)
    for s in sp:
        g[s["genus"]] += s["share"]
    assert max(g.values()) <= mix["caps"]["max_genus_share"] + 1e-9 and mix["caps"]["status"] == "provisional"
    assert mix["common_planting_months"] and all({"common_name", "quota", "needs_both_sexes"} <= set(s) for s in sp)
    # exactly the palette the plan tool chooses for the same area and the same number of saplings (same code, same inputs)
    plan = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 300, "zone": "Forest Zone"}).json()
    assert [(p["species_id"], p["quota"]) for p in plan["palette"]] == [(s["species_id"], s["quota"]) for s in sp]
    assert plan["summary"]["palette_common_planting_months"] == mix["common_planting_months"]


def test_rank_area_sources_are_resolved_and_nothing_is_null(client):
    j = post(client, barangay="Maly").json()
    assert None not in list(walk(j))
    for r in j["ranking"]:
        for sid in r["source_ids"]["site_score"] + r["source_ids"]["purpose_score"]:
            assert j["sources"][str(sid)]["url"] and "rank" in j["sources"][str(sid)]
    assert j["limits"] and j["missing"]["marker"] == -1 and "W where the species is suitable" in j["score_definition"]


def test_rank_area_errors(client, data, monkeypatch):
    r = post(client, barangay="Atlantis")
    assert r.status_code == 400 and "Unknown barangay" in r.json()["detail"] and "Santa Ana" in r.json()["detail"]
    r = post(client, zone="Moon Base")
    assert r.status_code == 400 and "Unknown zone" in r.json()["detail"] and "Forest Zone" in r.json()["detail"]
    r = post(client)
    assert r.status_code == 422 and "exactly one area" in r.json()["detail"]
    r = post(client, barangay="Maly", zone="Forest Zone")
    assert r.status_code == 422 and "exactly one area" in r.json()["detail"]
    assert client.post("/rank/area", json={"purpose": "fruit", "barangay": "Maly"}).status_code == 422
    assert post(client, barangay="Maly", limit=0).status_code == 422 and post(client, barangay="Maly", limit=46).status_code == 422
    assert post(client, barangay="Maly", n_saplings=0).status_code == 422
    r = post(client, polygon=box(120.0, 10.0, 120.1, 10.1))                                   # a valid polygon with nothing inside
    assert r.status_code == 400 and "no legal-zone grid points" in r.json()["detail"]
    bowtie = {"type": "Polygon", "coordinates": [[[121.1, 14.6], [121.2, 14.7], [121.2, 14.6], [121.1, 14.7], [121.1, 14.6]]]}
    for bad in (bowtie, {"type": "Point", "coordinates": [121.1, 14.6]}, {"foo": 1}):
        r = post(client, polygon=bad)
        assert r.status_code == 422 and "polygon" in r.json()["detail"]
    monkeypatch.setattr(data.ctx, "S", np.zeros_like(data.ctx.S))                             # an area where no species is suitable
    r = post(client, barangay="Maly")
    assert r.status_code == 400 and "No species has eligible points" in r.json()["detail"]
