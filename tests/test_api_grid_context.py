"""GET /grid/context: the grid squares that are not planting zones (a faint second map layer).
Run from the repo root: python -m pytest tests/test_api_grid_context.py"""
import json, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


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


def test_1837_rows_the_other_squares_and_they_add_up_with_the_planting_squares(client, data):
    r = client.get("/grid/context")
    assert r.status_code == 200
    j = r.json()
    c = j["columns"]
    assert j["n"] == 1357 and all(len(v) == 1357 for v in c.values())
    assert j["legal_points"] == 6731 and j["total_points"] == 8088 and j["legal_points"] + j["n"] == len(data.all_points) == 8088
    legal = {int(p) for p in data.ctx.sites.point_id}
    assert not legal & set(c["point_id"]) and len(set(c["point_id"])) == 1357          # none of them is a planting square, none twice
    assert sum(j["reason_counts"].values()) == 1357
    assert j["reason_counts"] == {"outside_zoning": 1279, "special_reserved": 0, "industrial": 0, "commercial": 0, "quarry": 55, "landfill": 0, "cemetery": 23, "other": 0}      # round 15a: the MPDC re-opened the rest
    assert set(c["reason"]) <= set(range(len(j["reasons"]))) and j["reasons"][:7] == ["outside_zoning", "special_reserved", "industrial", "commercial", "quarry", "landfill", "cemetery"]
    assert all(l for l in j["reason_labels"].values())
    # the counts of the table agree with the column
    for i, name in enumerate(j["reasons"]):
        assert c["reason"].count(i) == j["reason_counts"][name]


def test_zone_names_are_a_table_and_the_marker_means_outside_the_zoning_map(client):
    j = client.get("/grid/context").json()
    c = j["columns"]
    assert j["missing"]["marker"] == -1 and set(j["zones"]) == {"Cemetery Zone", "Quarry Sub-Zone"}
    for z, rs in zip(c["zone"], c["reason"]):
        assert (z == -1) == (j["reasons"][rs] == "outside_zoning")
        assert z == -1 or 0 <= z < len(j["zones"])
    assert all(b == -1 or 0 <= b < len(j["barangays"]) for b in c["barangay"])
    assert all(119 < lo < 122 and 14 < la < 15 for lo, la in zip(c["lon"], c["lat"]))


def test_the_body_is_small_has_no_nulls_and_is_cached_at_startup(client, data):
    r = client.get("/grid/context")
    assert len(r.content) < 120_000 and len(r.content) <= api_v2.API_CFG["context_max_bytes"]
    assert None not in list(walk(r.json()))
    assert r.content == data.context_body                                          # the same bytes every time: built once at startup
    assert "max-age" in r.headers["cache-control"]


def test_the_known_limits_say_how_the_8088_squares_split(client):
    assert "6,731 planting squares + 1,357 other squares = 8,088 map squares." in client.get("/health").json()["limits"]
    assert "Land that is not covered by our zoning map (the CLUP 2021-2031 shows it as Forest Reserve, Watershed) is left out until MENRO and DENR confirm it is plantable." in client.get("/health").json()["limits"]
    assert api_v2.FIELD_LIMITS[0].startswith("Field checks")                        # the last two limits (field checks) are still the last two
