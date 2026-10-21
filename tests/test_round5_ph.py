"""UX round 5 (A): the soil pH is shown with every place, area and species row. The estimate comes from data/reference/soilgrids_ph.csv; each species row of /rank carries a verdict against the estimate of the square
(display only: S, P, W and the order do not depend on it); the area diagnostic carries the estimate over the counted squares; a square without an estimate says so (None), it is never filled in."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
import soilgrids_ph as sgph  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CODES = {"inside", "outside", "outside_optimal", "uncertain", "no_value", "no_confirmed_range", "no_range"}


@pytest.fixture(scope="module")
def client():
    with TestClient(api_v2.app) as c:
        yield c


def rank(client, pid, **extra):
    sites = client.app.state.data.ctx.sites
    row = sites[sites.point_id.astype(int) == pid].iloc[0]
    r = client.get("/rank", params={"purpose": "urban", "lat": float(row.lat), "lon": float(row.lon), "limit": 45, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_square_with_an_estimate_shows_it_and_each_species_has_a_verdict(client):
    d = client.app.state.data
    pid = next(int(p) for p in d.ctx.sites.point_id.astype(int) if d.soil_ph.get(p) and d.soil_ph[p]["mean"] is not None)
    out = rank(client, pid)
    assert out["point"]["site_ph"]["mean"] == round(d.soil_ph[pid]["mean"], 2)
    assert "not measured in San Mateo" in out["point"]["site_ph"]["note"]
    verdicts = {it["ph_verdict"] for it in out["ranking"]}
    assert verdicts <= CODES and "no_value" not in verdicts
    # Phase 0 D: every species has a range in the project species dataset, so no row says "no confirmed range" any more (before: 16 species)
    assert sum(1 for it in out["ranking"] if it["ph_verdict"] in ("no_confirmed_range", "no_range")) == 0


def test_square_without_an_estimate_says_so_and_nothing_is_invented(client):
    d = client.app.state.data
    pid = next((int(p) for p in d.ctx.sites.point_id.astype(int) if not d.soil_ph.get(p) or d.soil_ph[p]["mean"] is None), None)
    assert pid is not None
    out = rank(client, pid)
    assert out["point"]["site_ph"] is None
    assert {it["ph_verdict"] for it in out["ranking"]} == {"no_value"}


def test_the_verdict_never_changes_the_order_or_the_scores(client):
    d = client.app.state.data
    pid = next(int(p) for p in d.ctx.sites.point_id.astype(int) if d.soil_ph.get(p) and d.soil_ph[p]["mean"] is not None)
    out = rank(client, pid)
    keys = [(it["species_id"], it["S"], it["P"], it["W"]) for it in out["ranking"]]
    assert keys == sorted(keys, key=lambda k: (-k[3], -k[1], k[0])) or [it["rank"] for it in out["ranking"]] == list(range(1, len(keys) + 1))
    saved = d.soil_ph
    try:
        d.soil_ph = {}
        again = rank(client, pid)
    finally:
        d.soil_ph = saved
    assert [(it["species_id"], it["S"], it["P"], it["W"]) for it in again["ranking"]] == keys


def test_area_diagnostic_carries_the_estimate_of_the_counted_squares(client):
    r = client.post("/area/diagnostic", json={"barangay": "MALY"})
    assert r.status_code == 200, r.text
    ph = r.json()["ph"]
    assert ph is None or (ph["q05"] <= ph["mean"] <= ph["q95"] and "not measured in San Mateo" in ph["note"])
    assert sgph.ATTRIBUTION in (ph["source"] if ph else sgph.ATTRIBUTION)
