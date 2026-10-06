"""GET /rank?include_left_out=true: a point marked not plantable in the field can still be shown (greyed out by the dashboard); the default is unchanged.
Run from the repo root: python -m pytest tests/test_api_rank_left_out.py"""
import sys
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
    api_v2.fv.connect(data.field_db).close()
    api_v2.refresh_field(data)


def spot(data):
    r = data.ctx.sites.iloc[200]
    return int(r.point_id), {"purpose": "urban", "lat": float(r.lat), "lon": float(r.lon), "limit": 45}


def test_a_not_plantable_point_is_404_by_default_and_shown_only_when_asked(client, data):
    pid, p = spot(data)
    before = client.get("/rank", params=p).json()
    assert "left_out_by_field_check" not in before
    r = client.post("/field-checks", json={"point_id": pid, "status": "not_plantable", "reason": "paved", "observer": "Ana"})
    assert r.status_code == 201
    assert client.get("/rank", params=p).status_code == 404                     # unchanged default
    shown = client.get("/rank", params={**p, "include_left_out": "true"})
    assert shown.status_code == 200
    j = shown.json()
    assert j["left_out_by_field_check"] is True and j["field_check"]["status"] == "not_plantable" and j["field_check"]["left_out_of_rankings"] is True
    assert [(x["species_id"], x["S"], x["P"], x["W"]) for x in j["ranking"]] == [(x["species_id"], x["S"], x["P"], x["W"]) for x in before["ranking"]]   # scores untouched
    assert pid not in {client.get("/nearest-viable", params={k: p[k] for k in ("purpose", "lat", "lon")}).json()["point"]["point_id"]}      # still never offered


def test_the_flag_is_absent_for_a_normal_point_even_with_the_parameter(client, data):
    pid, p = spot(data)
    j = client.get("/rank", params={**p, "include_left_out": "true"}).json()
    assert "left_out_by_field_check" not in j
