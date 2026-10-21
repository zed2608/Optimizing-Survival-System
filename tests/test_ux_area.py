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


def test_area_species_list_carries_a_ph_verdict_and_changes_no_score(client):
    d = client.app.state.data
    sites = d.ctx.sites
    have = sites[[bool(d.soil_ph.get(int(p), {}).get("mean")) for p in sites.point_id]]            # a square that has a SoilGrids value (650 squares have none)
    a = have.iloc[len(have) // 2]
    big = square(float(a.lon), float(a.lat), 400.0)
    r = client.post("/rank/area", json={"purpose": "urban", "polygon": big, "limit": 45}).json()
    ph = r["area"]["ph"]
    assert ph and ph["n_squares"] > 0 and ph["q05"] <= ph["q95"] and "not measured" in ph["note"]
    allowed = {"inside", "outside", "outside_optimal", "uncertain", "no_value", "no_confirmed_range", "no_range"}
    assert r["ranking"] and all(x["ph_verdict"] in allowed for x in r["ranking"])
    # Phase 0 D: the 16 species that had no range in the evidence file now have one in the project species dataset, so nothing says "no confirmed range"; they get a normal verdict
    none_ids = {3, 4, 8, 9, 10, 11, 21, 23, 32, 33, 34, 35, 37, 40, 42, 44}
    assert all(x["ph_verdict"] in ("inside", "outside", "uncertain") for x in r["ranking"] if x["species_id"] in none_ids)
    assert any(x["ph_verdict"] != "no_confirmed_range" for x in r["ranking"])
    # the ranking itself is the same as the scores say: rank order = descending species_score (nothing re-sorted by pH)
    scores = [x["species_score"] for x in r["ranking"]]
    assert scores == sorted(scores, reverse=True)


def test_a_square_covered_half_or_more_counts_even_when_its_centre_is_outside(client):
    """UX round 2 A3: the rule is 'centre inside OR the area covers >= 50% of the square'. A ring-shaped area (a hole around the centre) covers most of the square but not its centre."""
    d = client.app.state.data
    a = d.ctx.sites.iloc[len(d.ctx.sites) // 2]
    lat, lon = float(a.lat), float(a.lon)
    outer = square(lon, lat, 40.0)["coordinates"][0]
    hole = square(lon, lat, 8.0)["coordinates"][0]
    ring = {"type": "Polygon", "coordinates": [outer, hole[::-1]]}
    m, mode = api_v2.polygon_mask(d.ctx.sites, ring, 5000, with_mode=True)
    assert mode == "centres" and m.sum() == 1 and d.ctx.sites.point_id[m].iloc[0] == a.point_id    # selected by coverage (about 94%), not by the centre
    # an area covering less than half of a square and not its centre does not qualify by rule 1; with nothing else it falls back to 'touching'
    sliver = square(lon + 40.0 / (M_DEG * math.cos(math.radians(lat))), lat, 15.0)                   # 25-55 m east of the centre: covers about 10% of the square
    m2, mode2 = api_v2.polygon_mask(d.ctx.sites, sliver, 5000, with_mode=True)
    assert mode2 == "touching"


def test_area_diagnostic_counts_add_up(client):
    d = client.app.state.data
    sites = d.ctx.sites
    a = sites.iloc[len(sites) // 2]
    big = square(float(a.lon), float(a.lat), 320.0)
    j = client.post("/area/diagnostic", json={"polygon": big}).json()
    assert j["touched"] >= j["centres_inside"] >= 1
    assert j["planting"] + j["not_planting"]["total"] == j["touched"]
    assert j["suitable"] + j["low_match"] + j["left_out_by_field_check"] == j["planting"]
    assert sum(j["not_planting"]["by_reason"].values()) == j["not_planting"]["total"]
    assert j["rule_used"] == "centres" and j["selected"] <= j["planting"]
    r = client.post("/rank/area", json={"purpose": "urban", "polygon": big}).json()
    assert r["area"]["legal_points"] <= j["planting"]                       # the ranking uses planting squares not left out by a field check
    far = client.post("/area/diagnostic", json={"polygon": square(120.0, 10.0, 30.0)}).json()
    assert far["touched"] == 0 and far["planting"] == 0 and far["selected"] == 0
    b = client.post("/area/diagnostic", json={"barangay": "Santa Ana"}).json()
    assert b["kind"] == "barangay" and b["touched"] == b["centres_inside"] and b["planting"] + b["not_planting"]["total"] == b["touched"]
    assert client.post("/area/diagnostic", json={"barangay": "Santa Ana", "zone": "Forest Zone"}).status_code == 422


def test_rank_point_carries_the_site_ph_estimate_and_changes_nothing_else(client):
    d = client.app.state.data
    have = d.ctx.sites[[bool(d.soil_ph.get(int(p), {}).get("mean")) for p in d.ctx.sites.point_id]]
    a = have.iloc[len(have) // 3]
    j = client.get("/rank", params={"purpose": "urban", "lat": float(a.lat), "lon": float(a.lon), "limit": 45}).json()
    ph = j["point"]["site_ph"]
    assert ph and ph["q05"] <= ph["mean"] <= ph["q95"] or ph["q05"] <= ph["q95"]
    assert "not measured" in ph["note"] and ph["scope"] == "square"
    r = d.soil_ph[int(a.point_id)]
    assert (ph["mean"], ph["q05"], ph["q95"]) == (round(r["mean"], 2), round(r["q05"], 2), round(r["q95"], 2))
    none = d.ctx.sites[[not d.soil_ph.get(int(p), {}).get("mean") for p in d.ctx.sites.point_id]]
    if len(none):
        b = none.iloc[0]
        k = client.get("/rank", params={"purpose": "urban", "lat": float(b.lat), "lon": float(b.lon)}).json()
        assert k["point"]["site_ph"] is None                                           # never filled in


def test_area_diagnostic_lists_counted_and_partial_squares_for_the_map(client):
    d = client.app.state.data
    a = d.ctx.sites.iloc[len(d.ctx.sites) // 2]
    # a rectangle that holds one centre and only slivers of its neighbours: the neighbours are 'partial' (not counted)
    lat, lon = float(a.lat), float(a.lon)
    big = square(lon, lat, 60.0)
    j = client.post("/area/diagnostic", json={"polygon": big}).json()
    s = j["squares"]
    assert s and j["counted_squares"] == len(s["counted"]) == j["selected"] and j["partial_squares"] == len(s["partial"])
    assert j["counted_squares"] >= 1 and j["partial_squares"] >= 1                      # the centre square counts; the squares only touched at the edge do not
    assert not ({tuple(x) for x in s["counted"]} & {tuple(x) for x in s["partial"]})
    assert s["min_cover_share"] == api_v2.AREA_COVER_MIN == 0.5 and s["half_size_m"] == 50.0
    # an area smaller than half a square: the rule falls back to 'touching': every touched planting square is counted, none is partial
    tiny = client.post("/area/diagnostic", json={"polygon": square(lon + 40.0 / (M_DEG * math.cos(math.radians(lat))), lat, 15.0)}).json()
    assert tiny["rule_used"] == "touching" and tiny["squares"]["partial"] == [] and tiny["counted_squares"] >= 1
    # barangay and zone areas carry no square list
    assert client.post("/area/diagnostic", json={"barangay": "Santa Ana"}).json()["squares"] is None
