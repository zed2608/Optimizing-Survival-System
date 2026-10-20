"""UX 12: companion species come only from the land (shared suitable squares), never from ecology; same genus and the main species are left out; the rule can be recomputed from the scores."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    api_v2.API_CFG["include_unzoned"] = False
    try:
        with TestClient(api_v2.app) as c:
            yield c
    finally:
        api_v2.API_CFG["include_unzoned"] = True


def test_companions_follow_the_shared_suitable_squares_and_nothing_else(client):
    d = client.app.state.data
    r = client.post("/companions", json={"species_id": 1, "purpose": "urban", "barangay": "Santa Ana"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["provisional"] is True and j["scored"] is False and "Hindi pa kasama ang laki ng canopy, ugat o lilim" in j["note"]
    sp = d.ctx.species
    genus1 = str(sp.genus.iloc[d.species_idx[1]])
    assert j["companions"], "Narra should have companions in Santa Ana"
    mask = d.point_barangay == d.barangay_display.index("Santa Ana") if "Santa Ana" in d.barangay_display else None
    assert mask is not None
    idx = np.where(mask & ~d.ex_mask)[0]
    elig = d.ctx.S[idx] >= 0.5
    e_main = elig[:, d.species_idx[1]]
    assert j["main"]["suitable_squares"] == int(e_main.sum())
    for c in j["companions"]:
        k = d.species_idx[c["species_id"]]
        assert c["species_id"] != 1 and str(sp.genus.iloc[k]) != genus1                       # not itself, not the same genus
        assert c["shared_squares"] == int((e_main & elig[:, k]).sum())                          # recomputed from the scores
        assert c["share_of_main_squares"] >= 0.5
    shares = [c["share_of_main_squares"] for c in j["companions"]]
    assert shares == sorted(shares, reverse=True)
    for c in j["companions"]:
        assert not any(w in str(c).lower() for w in ("ugat", "canopy", "lilim", "ecolog", "tugma sa"))


def test_whole_municipality_when_no_area_and_errors(client):
    r = client.post("/companions", json={"species_id": 1, "purpose": "urban"})
    assert r.status_code == 200 and r.json()["area"]["type"] == "municipality" and r.json()["area"]["squares"] > 1000
    assert client.post("/companions", json={"species_id": 999, "purpose": "urban"}).status_code == 404
    two = client.post("/companions", json={"species_id": 1, "purpose": "urban", "barangay": "Santa Ana", "zone": "Forest Zone"})
    assert two.status_code == 422


def test_scores_are_not_changed_by_asking(client):
    a = client.post("/rank/area", json={"purpose": "urban", "barangay": "Santa Ana", "limit": 45}).json()["ranking"]
    client.post("/companions", json={"species_id": 1, "purpose": "urban", "barangay": "Santa Ana"})
    b = client.post("/rank/area", json={"purpose": "urban", "barangay": "Santa Ana", "limit": 45}).json()["ranking"]
    assert a == b
