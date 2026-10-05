"""Tests for GET /geo/boundaries and GET /grid in api_v2.py (FastAPI TestClient, real data). Run from the repo root:
python -m pytest tests/test_api_geo.py"""
import json, sys, time
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

PURPOSES = ("urban", "planting", "watershed")
BOUNDARY_LIMIT, GRID_LIMIT = 300_000, 250_000


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


@pytest.fixture(scope="module")
def boundaries(client):
    r = client.get("/geo/boundaries")
    assert r.status_code == 200
    return r


def walk(o):
    """Every scalar value inside a JSON document."""
    if isinstance(o, dict):
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)
    else:
        yield o


def all_coords(c):
    if c and isinstance(c[0], (int, float)):
        yield c
    else:
        for x in c:
            yield from all_coords(x)


# ---- /geo/boundaries ---------------------------------------------------------------------------------------------------
def test_boundaries_is_geojson_with_the_municipality_and_15_barangays(boundaries):
    j = boundaries.json()
    assert boundaries.headers["content-type"].startswith("application/json") and "max-age" in boundaries.headers["cache-control"]
    assert j["type"] == "FeatureCollection" and len(j["features"]) == 16
    kinds = [f["properties"]["kind"] for f in j["features"]]
    assert kinds == ["municipality"] + ["barangay"] * 15
    for f in j["features"]:
        assert f["type"] == "Feature" and f["geometry"]["type"] in ("Polygon", "MultiPolygon") and f["geometry"]["coordinates"]
    assert "EPSG:4326" in j["crs"] and "BRGY_BOUNDARY" in j["source"] and j["simplify_tolerance_deg"] > 0


def test_boundaries_size_is_under_the_limit_and_served_from_memory(client, data, boundaries):
    assert len(boundaries.content) < BOUNDARY_LIMIT, len(boundaries.content)
    assert boundaries.content == data.boundaries_body == client.get("/geo/boundaries").content
    assert data.boundaries_info["bytes"] == len(boundaries.content)


def test_barangay_names_and_display_names_follow_the_place_search_aliases(boundaries):
    import geopandas as gpd
    names = sorted(gpd.read_file(ROOT / "data" / "BRGY_BOUNDARY.shp").BRGY_NAME)
    brg = [f["properties"] for f in boundaries.json()["features"][1:]]
    assert [b["name"] for b in brg] == names and len(set(names)) == 15
    disp = {b["name"]: b["display_name"] for b in brg}
    assert disp["STA ANA"] == "Santa Ana" and disp["STO NINO"] == "Santo Nino"
    assert disp["AMPID II"] == "Ampid II" and disp["GUITNANG BAYAN II"] == "Guitnang Bayan II" and disp["PINTUNG BUKAWE"] == "Pintung Bukawe"
    assert api_v2.display_name("Sto. Niño", api_v2.API_CFG["place_aliases"]) == "Santo Nino"
    assert all("sta " not in b["display_name"].lower() and "sto " not in b["display_name"].lower() for b in brg)


def test_bbox_contains_every_coordinate_and_each_label_point(boundaries):
    j = boundaries.json()
    x0, y0, x1, y1 = j["bbox"]
    assert j["features"][0]["properties"]["bbox"] == j["bbox"] and 121.0 < x0 < x1 < 121.4 and 14.5 < y0 < y1 < 14.9
    from shapely.geometry import Point, shape
    for f in j["features"]:
        b = f["properties"]["bbox"]
        for lon, lat in all_coords(f["geometry"]["coordinates"]):
            assert b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and x0 <= lon <= x1 and y0 <= lat <= y1
        if f["properties"]["kind"] == "barangay":
            lp = f["properties"]["label_point"]
            assert shape(f["geometry"]).buffer(1e-4).contains(Point(lp["lon"], lp["lat"]))              # labels sit inside their barangay


def test_municipal_outline_is_the_union_of_the_barangays(boundaries):
    import geopandas as gpd
    import shapely
    from shapely.geometry import shape
    j = boundaries.json()
    outline = gpd.GeoSeries([shape(j["features"][0]["geometry"])], crs=4326).to_crs(32651).area.iloc[0] / 1e6
    original = gpd.read_file(ROOT / "data" / "BRGY_BOUNDARY.shp").to_crs(32651)
    union_area = shapely.union_all(original.geometry.values).area / 1e6
    assert abs(outline - union_area) / union_area < 0.01                                                    # within 1% after simplifying
    assert abs(j["features"][0]["properties"]["area_km2"] - union_area) < 0.1
    parts = sum(gpd.GeoSeries([shape(f["geometry"])], crs=4326).to_crs(32651).area.iloc[0] for f in j["features"][1:]) / 1e6
    assert abs(outline - parts) / parts < 0.02                                                              # barangays tile the outline


def test_simplified_barangays_still_look_like_the_originals(boundaries):
    import geopandas as gpd
    from shapely.geometry import shape
    orig = gpd.read_file(ROOT / "data" / "BRGY_BOUNDARY.shp").to_crs(32651).set_index("BRGY_NAME")
    for f in boundaries.json()["features"][1:]:
        g = gpd.GeoSeries([shape(f["geometry"])], crs=4326).to_crs(32651).iloc[0]
        o = orig.geometry[f["properties"]["name"]]
        assert g.is_valid and abs(g.area - o.area) / o.area < 0.02 and g.hausdorff_distance(o) < 150            # metres


def test_legal_grid_points_per_barangay_agree_with_the_grid_endpoint(client, data, boundaries):
    j = boundaries.json()
    g = client.get("/grid", params={"purpose": "urban"}).json()
    counts = np.bincount([b for b in g["columns"]["barangay"] if b >= 0], minlength=15)
    assert [f["properties"]["legal_grid_points"] for f in j["features"][1:]] == counts.tolist()
    assert j["points_outside_every_barangay"] == g["columns"]["barangay"].count(-1)
    from shapely.geometry import shape
    import shapely
    out = shape(j["features"][0]["geometry"])
    inside = shapely.contains_xy(out.buffer(0.0003), np.array(g["columns"]["lon"]), np.array(g["columns"]["lat"]))
    assert inside.mean() > 0.999                                                                           # the grid lies within the outline


# ---- /grid -----------------------------------------------------------------------------------------------------------
def grid_of(client, purpose, species_id=None):
    params = {"purpose": purpose, **({"species_id": species_id} if species_id is not None else {})}
    r = client.get("/grid", params=params)
    assert r.status_code == 200, r.text
    return r


@pytest.mark.parametrize("purpose", PURPOSES)
def test_grid_shape_size_and_columns(client, data, purpose):
    r = grid_of(client, purpose)
    j = r.json()
    assert len(r.content) < GRID_LIMIT, len(r.content)
    assert r.headers["content-type"].startswith("application/json") and "max-age" in r.headers["cache-control"]
    cols = j["columns"]
    assert set(cols) == {"point_id", "lon", "lat", "W", "best_species_id", "n_eligible_species", "barangay"}
    assert j["n"] == 6251 and all(len(v) == 6251 for v in cols.values())
    assert j["purpose"] == purpose and j["species_id"] == -1 and len(j["barangays"]) == 15 == len(j["barangays_display"])
    assert sorted(cols["point_id"]) == sorted(data.ctx.sites.point_id.astype(int).tolist()) and len(set(cols["point_id"])) == 6251
    assert np.allclose(cols["lon"], np.round(data.ctx.sites.lon, 5)) and np.allclose(cols["lat"], np.round(data.ctx.sites.lat, 5))


@pytest.mark.parametrize("purpose", PURPOSES)
def test_grid_values_match_an_independent_calculation(client, data, purpose):
    cols = grid_of(client, purpose).json()["columns"]
    ctx = data.ctx
    S, P = ctx.S, ctx.P[purpose]
    W = np.where(S >= 0.5, S * P[None, :], 0.0)
    assert np.allclose(cols["W"], W.max(axis=1), atol=6e-4)
    ids = ctx.species.species_id.to_numpy()
    best = np.array(cols["best_species_id"])
    ok = W.max(axis=1) > 0
    assert (best[~ok] == -1).all() and (best[ok] == ids[W.argmax(axis=1)][ok]).all()
    assert (np.array(cols["W"])[best == -1] == 0).all() and (np.array(cols["n_eligible_species"]) == (S >= 0.5).sum(axis=1)).all()
    assert min(cols["W"]) >= 0 and max(cols["W"]) <= 1 and set(cols["barangay"]) <= set(range(-1, 15))


def test_grid_never_returns_null_and_documents_its_missing_marker(client):
    r = grid_of(client, "urban")
    j = r.json()
    import re
    assert None not in list(walk(j)) and not re.search(rb"[:\[,]null", r.content)           # no JSON null anywhere
    m = j["missing"]
    assert m["marker"] == -1 and set(m["columns"]) == {"species_id", "best_species_id", "barangay"} and "null" in m["note"].lower() and "index" in m["note"]
    assert j["w_definition"].startswith("W = S x P if S >= 0.50 else 0") and j["rounding"] == {"lon_lat_decimals": 5, "W_decimals": 3}


def test_the_missing_marker_is_used_when_nothing_is_suitable(client, data, monkeypatch):
    import numpy as np
    S0 = np.zeros_like(data.ctx.S)
    monkeypatch.setattr(data.ctx, "S", S0)
    monkeypatch.setattr(data, "grid_cache", {})
    j = client.get("/grid", params={"purpose": "urban"}).json()
    assert set(j["columns"]["best_species_id"]) == {-1} and set(j["columns"]["W"]) == {0} and set(j["columns"]["n_eligible_species"]) == {0}


@pytest.mark.parametrize("species_id", [1, 8, 36])
def test_species_filter_colours_by_that_species_only(client, data, species_id):
    j = grid_of(client, "watershed", species_id).json()
    cols = j["columns"]
    k = data.species_idx[species_id]
    S, P = data.ctx.S[:, k], data.ctx.P["watershed"][k]
    assert j["species_id"] == species_id and np.allclose(cols["W"], np.where(S >= 0.5, S * P, 0.0), atol=6e-4)
    assert set(cols["best_species_id"]) <= {species_id, -1}
    assert ((np.array(cols["W"]) > 0) == (np.array(cols["best_species_id"]) == species_id)).all()
    assert np.array_equal(cols["n_eligible_species"], grid_of(client, "watershed").json()["columns"]["n_eligible_species"])
    assert cols["W"] != grid_of(client, "watershed").json()["columns"]["W"] and len(client.get("/grid", params={"purpose": "watershed", "species_id": species_id}).content) < GRID_LIMIT


def test_purposes_give_different_colours(client):
    a, b = (grid_of(client, p).json()["columns"]["W"] for p in ("urban", "watershed"))
    assert a != b


def test_grid_agrees_with_the_rank_endpoint_at_a_point(client, data):
    cols = grid_of(client, "urban").json()["columns"]
    for i in (0, 500, 3000, 6000):
        r = client.get("/rank", params={"purpose": "urban", "lat": cols["lat"][i], "lon": cols["lon"][i], "limit": 1}).json()
        top = r["ranking"][0]
        assert r["point"]["point_id"] == cols["point_id"][i] and abs(top["W"] - cols["W"][i]) < 2e-3
        assert top["species_id"] == cols["best_species_id"][i] or abs(top["W"] - cols["W"][i]) < 2e-3


def test_grid_errors(client):
    r = client.get("/grid", params={"purpose": "fruit"})
    assert r.status_code == 422 and "purpose" in str(r.json()["detail"])
    assert client.get("/grid").status_code == 422
    r = client.get("/grid", params={"purpose": "urban", "species_id": 999})
    assert r.status_code == 404 and "not found" in r.json()["detail"]
    assert client.get("/grid", params={"purpose": "urban", "species_id": "abc"}).status_code == 422


def test_grid_is_cached_in_memory_from_startup(client, data):
    assert all((p, None) in data.grid_cache for p in PURPOSES)                  # the three purposes were built at startup
    first = client.get("/grid", params={"purpose": "planting"}).content
    t0 = time.perf_counter()
    second = client.get("/grid", params={"purpose": "planting"}).content
    assert first == second == data.grid_cache[("planting", None)] and time.perf_counter() - t0 < 0.5
    client.get("/grid", params={"purpose": "planting", "species_id": 5})
    assert ("planting", 5) in data.grid_cache                                    # species variants are cached after the first request


def test_cors_applies_to_the_new_endpoints(client):
    for url in ("/geo/boundaries", "/grid?purpose=urban"):
        r = client.get(url, headers={"Origin": "http://localhost:5173"})
        assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "access-control-allow-origin" not in client.get(url, headers={"Origin": "http://evil.example"}).headers
