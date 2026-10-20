"""Design revamp, Phase 6: GET /analytics/summary counts what exists (scores, pH estimates, plans, field checks), narrows with filters, forecasts nothing and changes no score."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import analytics as an  # noqa: E402
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:
        yield c


def test_helpers_count_exactly():
    h = an.histogram([0, 0, 0.05, 0.5, 0.55, 1.0, np.nan], an.S_EDGES, zero_separate=True)
    assert h["zero"] == 2 and h["n"] == 6 and sum(b["count"] for b in h["bins"]) == 4 and h["bins"][-1]["count"] == 1
    v = an.verdict_counts([5.2, 4.0, 8.0, np.nan], [7.0, 7.9, 9.0, np.nan], 5.0, 7.5)
    assert v == {"inside": 1, "outside": 1, "uncertain": 1, "no_value": 1}
    assert an.verdict_counts([5.0], [6.0], None, None) == {"no_range": 1}
    assert an.week_start("2026-10-21T08:00:00") == "2026-10-19" and an.week_start("junk") is None
    assert an.parse_day("") is None and an.parse_day("2026-02-30") is False and str(an.parse_day("2026-10-21")) == "2026-10-21"


def test_summary_shape_and_forecast_note(client):
    j = client.get("/analytics/summary").json()
    assert {"filters", "kpi", "suitability", "ph", "land", "activity", "planned_vs_planted", "forecast_note"} <= set(j)
    assert j["forecast_note"] == "No forecast is shown: forecasting needs survival records, which do not exist yet."
    d = client.app.state.data
    n, m = d.ctx.S.shape
    assert j["kpi"]["squares_scored"] == n and j["kpi"]["species"] == m
    assert j["suitability"]["histogram"]["n"] == n * m
    assert sum(x["squares"] for x in j["suitability"]["per_barangay"]) <= n
    assert j["ph"]["squares_with_estimate"] + j["ph"]["squares_without_estimate"] == n
    assert sum(j["ph"]["verdicts"].values()) == n * m
    assert j["land"]["total_squares"] == len(d.all_points)
    assert "not measured in San Mateo" in j["ph"]["note"]


def test_filters_narrow_and_bad_input_is_refused(client):
    full = client.get("/analytics/summary").json()
    one = client.get("/analytics/summary", params={"species_id": 1}).json()
    assert one["kpi"]["species"] == 1 and one["suitability"]["histogram"]["n"] == full["kpi"]["squares_scored"]
    b = client.get("/analytics/summary", params={"barangay": "MALY"}).json()
    assert 0 < b["kpi"]["squares_scored"] < full["kpi"]["squares_scored"] and b["filters"]["barangay"]
    assert client.get("/analytics/summary", params={"barangay": "NOWHERE"}).status_code == 400
    assert client.get("/analytics/summary", params={"species_id": 9999}).status_code == 404
    assert client.get("/analytics/summary", params={"from": "2026-13-40"}).status_code == 422
    assert client.get("/analytics/summary", params={"from": "2026-10-10", "to": "2026-10-01"}).status_code == 422
    far = client.get("/analytics/summary", params={"from": "2001-01-01", "to": "2001-01-31"}).json()
    assert far["kpi"]["plans"] == 0 and far["activity"]["by_week"] == []


def test_it_changes_no_score(client):
    d = client.app.state.data
    before = d.ctx.S.copy()
    client.get("/analytics/summary")
    assert np.array_equal(before, d.ctx.S)
