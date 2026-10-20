"""UX fix 5: a drawn area smaller than a square (no square centre inside) selects the squares it touches; an area with centres inside is unchanged; an area outside the map selects nothing.
The score of a square (S, P, W) does not depend on which rule picked it."""
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

M_DEG = 111320.0


@pytest.fixture(scope="module")
def client():
    api_v2.API_CFG["include_unzoned"] = False
    try:
        with TestClient(api_v2.app) as c:
            yield c
    finally:
        api_v2.API_CFG["include_unzoned"] = True


def square(lon, lat, half_m):
    dlat = half_m / M_DEG
    dlon = half_m / (M_DEG * math.cos(math.radians(lat)))
    return {"type": "Polygon", "coordinates": [[[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat], [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]]}


def test_small_area_between_centres_selects_the_square_it_touches(client):
    sites = client.app.state.data.ctx.sites
    a = sites.iloc[len(sites) // 2]
    lat, lon = float(a.lat), float(a.lon)
    east35 = lon + 35.0 / (M_DEG * math.cos(math.radians(lat)))
    tiny = square(east35, lat, 8.0)                                              # 16 m x 16 m, 27 to 43 m east of the centre: no centre inside, inside the square of `a`
    around = square(lon, lat, 8.0)                                               # the same size, with the centre inside
    r_tiny = client.post("/rank/area", json={"purpose": "urban", "polygon": tiny, "limit": 45})
    r_cent = client.post("/rank/area", json={"purpose": "urban", "polygon": around, "limit": 45})
    assert r_tiny.status_code == 200 and r_cent.status_code == 200, (r_tiny.text[:200], r_cent.text[:200])
    t, c = r_tiny.json(), r_cent.json()
    assert t["area"]["selection"] == "touching" and c["area"]["selection"] == "centres"
    assert t["area"]["legal_points"] == 1 and c["area"]["legal_points"] == 1
    # the scores are the same: S, P and W do not depend on how the square was picked
    assert [(x["species_id"], x["P"], x["species_score"], x["mean_W_where_suitable"], x["suitable_points"]) for x in t["ranking"]] == \
           [(x["species_id"], x["P"], x["species_score"], x["mean_W_where_suitable"], x["suitable_points"]) for x in c["ranking"]]


def test_area_with_centres_inside_is_unchanged(client):
    sites = client.app.state.data.ctx.sites
    a = sites.iloc[len(sites) // 2]
    big = square(float(a.lon), float(a.lat), 250.0)
    r = client.post("/rank/area", json={"purpose": "urban", "polygon": big}).json()
    assert r["area"]["selection"] == "centres" and r["area"]["legal_points"] >= 9


def test_area_that_touches_no_square_is_still_refused_with_the_plain_message(client):
    far = square(120.0, 10.0, 30.0)                                              # nowhere near San Mateo
    r = client.post("/rank/area", json={"purpose": "urban", "polygon": far})
    assert r.status_code == 400 and "no legal-zone grid points" in r.json()["detail"]
    p = client.post("/plan-event/preview", json={"purpose": "urban", "n_saplings": 10, "polygon": far})
    assert p.status_code in (200, 400)
