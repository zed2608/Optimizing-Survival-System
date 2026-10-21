"""Design v2 (Task C) through the API: a plan in blocks carries spaced points (the same numbers as the field kit), a drawn area keeps the trees inside it, and the planter link is built from the spaced kit."""
import csv, io, json, sys, zipfile
from pathlib import Path
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(), reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
import field_kit as fk  # noqa: E402
import field_verify as fv  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(scope="module")
def data(client):
    return client.app.state.data


@pytest.fixture(autouse=True)
def fresh(data, tmp_path, monkeypatch):
    monkeypatch.setattr(data, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(data, "work", tmp_path)
    monkeypatch.setitem(data.cfg, "field_exclude_not_plantable", True)
    monkeypatch.setitem(fk.CFG, "point_layout", "spaced")
    fv.connect(data.field_db).close()
    api_v2.refresh_field(data)


BASE = {"purpose": "urban", "n_saplings": 200, "seed": 4, "campaign": {"name": "Tree Day", "unit": "Team A"}}


def test_plan_items_carry_spaced_points_and_the_kit_has_the_same_trees(client):
    j = client.post("/plan-event", json=BASE).json()
    items = j["plan"]
    assert items and all(it["layout"] == "spaced" for it in items)
    assert sum(len(it["points_m"]) for it in items) == sum(it["trees_fit"] for it in items) > 50
    for it in items:
        assert all(0 <= x <= 100 and 0 <= y <= 100 for x, y in it["points_m"]) and it["min_distance_m"] > 0 and it["fits"] in (True, False)
        assert it["fits"] or "fit at the required spacing" in it["fit_note"]
    pid = j["plan_id"]
    r = client.post(f"/plans/{pid}/field-kit")
    assert r.status_code == 200, r.text
    z = zipfile.ZipFile(io.BytesIO(client.get(r.json()["download_url"]).content))
    trees = list(csv.DictReader(io.StringIO(z.read([n for n in z.namelist() if n.endswith("trees.csv")][0]).decode("utf-8"))))
    by_ref = {}
    for t in trees:
        by_ref.setdefault(t["point_ref"], []).append((float(t["x_m"]), float(t["y_m"])))
    for it in items:
        got = by_ref.get(it["block_ref"], [])
        assert len(got) == len(it["points_m"])
        assert all(abs(a[0] - b[0]) < 0.01 and abs(a[1] - b[1]) < 0.01 for a, b in zip(got, it["points_m"]))          # the dashboard and the kit show the same points


def test_a_drawn_area_keeps_the_trees_inside_it(client):
    j0 = client.post("/plan-event", json=BASE).json()
    lon, lat = j0["plan"][0]["lon"], j0["plan"][0]["lat"]
    d = 0.0007
    poly = {"type": "Polygon", "coordinates": [[[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]]}
    j = client.post("/plan-event", json={**BASE, "n_saplings": 40, "polygon": poly})
    assert j.status_code == 200, j.text
    items = j.json()["plan"]
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:32651", "EPSG:4326", always_xy=True)
    for it in items:
        for x, y in it["points_m"]:
            plon, plat = tr.transform(it["utm_e"] - 50 + x, it["utm_n"] - 50 + y)
            assert lon - d - 1e-7 <= plon <= lon + d + 1e-7 and lat - d - 1e-7 <= plat <= lat + d + 1e-7


def test_the_planter_link_is_built_from_the_spaced_kit(client):
    pid = client.post("/plan-event", json=BASE).json()["plan_id"]
    r = client.post(f"/plans/{pid}/field-pack")
    assert r.status_code == 200, r.text
    page = client.get(r.json()["url"])
    assert page.status_code == 200 and '"layout":"spaced"' in page.text
