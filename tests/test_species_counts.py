"""Round 14 A: tree counts per species (POST /plan-event species_counts, run_plan.py --species-counts).
Run from the repo root: python -m pytest tests/test_species_counts.py"""
import math, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
import field_verify as fv  # noqa: E402
import palettes as pal  # noqa: E402
import run_plan as rp  # noqa: E402
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
    fv.connect(data.field_db).close()
    api_v2.refresh_field(data)


BASE = {"purpose": "urban", "seed": 4, "campaign": {"name": "Counts", "unit": "Team"}, "barangay": "Santa Ana"}
CAP = lambda sid: int(pal.block_table(pd.read_csv(PROCESSED / "species_clean.csv")).set_index("species_id").capacity[sid])


def post(client, body, **q):
    return client.post("/plan-event", params=q, json={**BASE, **body})


def per(j):
    return {r["species_id"]: r for r in j["summary"]["species_counts"]["per_species"]}


def test_exact_counts_per_species_and_remainder_blocks(client):
    r = post(client, {"species_counts": {"8": 30, "7": 20}})
    assert r.status_code == 200, r.text
    j = r.json()
    for sid, want in ((8, 30), (7, 20)):
        mine = [i for i in j["plan"] if i["species_id"] == sid]
        assert sum(i["trees_planned"] for i in mine) == want
        assert len(mine) == math.ceil(want / CAP(sid))                                  # blocks per species = ceil(count / capacity)
    assert j["n_placed"] == 50 == j["summary"]["species_counts"]["total_placed"]
    assert all(v["unplaced"] == 0 and v["reason"] == "" for v in per(j).values())
    # the remainder: 90 trees of a species with capacity c -> full blocks plus one block holding the rest
    j2 = post(client, {"species_counts": {"8": 90, "7": 10}}).json()
    k = sorted([i["trees_planned"] for i in j2["plan"] if i["species_id"] == 8])
    c = CAP(8)
    assert k == sorted([c] * (90 // c) + ([90 % c] if 90 % c else []))


def test_no_caps_on_explicit_counts_and_plain_warnings(client):
    one = post(client, {"species_counts": {"8": 5}}).json()
    assert one["summary"]["palette_warnings"] == ["Single species planting: higher pest and disease risk"] and one["n_placed"] == 5
    mostly = post(client, {"species_counts": {"8": 90, "7": 10}}).json()                  # 90% of the trees: the 20% cap would have refused this
    assert mostly["summary"]["palette_warnings"] == ["Mostly one species: higher pest risk"] and per(mostly)[8]["placed"] == 90
    balanced = post(client, {"species_counts": {"8": 30, "7": 20}}).json()
    assert balanced["summary"]["palette_warnings"] == []
    assert "do not apply" in balanced["summary"]["species_selection"]["caps_note"]
    edge = post(client, {"species_counts": {"8": 80, "7": 20}}).json()                    # exactly 80% counts as "mostly one species"
    assert edge["summary"]["palette_warnings"] == ["Mostly one species: higher pest risk"]


def test_old_path_is_unchanged(client):
    a = client.post("/plan-event", json={**BASE, "n_saplings": 120}).json()
    b = client.post("/plan-event", json={**BASE, "n_saplings": 120}).json()
    assert [(i["point_id"], i["species_id"], i["trees_planned"]) for i in a["plan"]] == [(i["point_id"], i["species_id"], i["trees_planned"]) for i in b["plan"]]
    assert "species_counts" not in a["summary"] and a["n_placed"] == 120
    assert any(p["share"] <= 0.2 + 1e-9 for p in a["palette"]) and max(p["share"] for p in a["palette"]) <= 0.2 + 1e-9    # the caps still apply
    ids = client.post("/plan-event", json={**BASE, "n_saplings": 50, "species_ids": [8, 7]}).json()
    assert "caps_relaxed" in ids["summary"]["species_selection"] and "species_counts" not in ids["summary"]


def test_partial_placement_is_reported_per_species_with_the_reason(client):
    j = post(client, {"species_counts": {"8": 2000}, "barangay": "Santo Nino"}).json()
    row = per(j)[8]
    assert row["requested"] == 2000 and row["placed"] < 2000 and row["unplaced"] == 2000 - row["placed"] and row["reason"].startswith("Only ")
    assert "suit Kamagong" in row["reason"] and j["n_placed"] == row["placed"]
    assert j["summary"]["species_counts"]["total_requested"] == 2000


def test_totals_and_values_are_validated(client):
    assert post(client, {"species_counts": {"8": 0}}).status_code == 422
    assert post(client, {"species_counts": {"8": -3}}).status_code == 422
    assert post(client, {"species_counts": {"8": 1500, "7": 600}}).status_code == 422                 # 2100 > 2000
    assert post(client, {"species_counts": {"8": 2000}}).status_code in (200, 400)                    # 2000 is allowed
    assert post(client, {"species_counts": {"8": 30}, "n_saplings": 40}).status_code == 422
    assert post(client, {"species_counts": {}}).status_code == 422
    pts = post(client, {"species_counts": {"8": 12, "7": 8}, "layout_mode": "points"})                  # points mode: every tree has its own square
    assert pts.status_code == 200, pts.text
    assert pts.json()["n_placed"] == 20 and {r["species_id"]: r["placed"] for r in pts.json()["summary"]["species_counts"]["per_species"]} == {8: 12, 7: 8}
    r = post(client, {})
    assert r.status_code == 422 and "species_counts" in r.text
    assert post(client, {"species_counts": {"8": 1}}).status_code == 200                              # the smallest valid plan
    assert post(client, {"species_counts": {"abc": 3}}).status_code == 422


def test_unknown_and_ineligible_species_get_a_plain_error_naming_them(client, data):
    assert post(client, {"species_counts": {"999": 5}}).status_code == 404
    sp = data.ctx.species.reset_index(drop=True)
    b = api_v2.find_barangay(data, "Santo Nino")
    sub = data.ctx.S[data.point_barangay == b]
    never = [int(sp.species_id[k]) for k in range(len(sp)) if not (sub[:, k] >= 0.5).any()]
    assert never, "the test needs a species with no suitable square in the area"
    sid = never[0]
    r = post(client, {"species_counts": {str(sid): 10, "8": 10}, "barangay": "Santo Nino"})
    assert r.status_code == 400
    name = str(sp.common_name[sp.species_id == sid].iloc[0])
    assert name in r.json()["detail"] and "cannot be planted here" in r.json()["detail"]


def test_season_filter_names_the_species_that_are_out_of_season(client, data):
    sm = {int(s): m for s, m in zip(data.ctx.species.species_id, data.species_months)}
    inn = [s for s, m in sm.items() if m and 8 in m]
    out = [s for s, m in sm.items() if m and 8 not in m]
    assert inn and out
    r = post(client, {"species_counts": {str(inn[0]): 10, str(out[0]): 10}, "barangay": None}, start="2027-08-01", end="2027-08-31", season_filter="only")
    assert r.status_code == 400
    nm = dict(zip(data.ctx.species.species_id.astype(int), data.ctx.species.common_name))
    assert nm[out[0]] in r.json()["detail"] and "best months" in r.json()["detail"]
    ok = post(client, {"species_counts": {str(inn[0]): 10}, "barangay": None}, start="2027-08-01", end="2027-08-31", season_filter="only")
    assert ok.status_code in (200, 400)


def test_field_checks_and_zoning_still_apply(client, data):
    j = post(client, {"species_counts": {"8": 36, "7": 49}}).json()
    first = j["plan"][0]
    r = client.post("/field-checks", json={"point_id": first["point_id"], "status": "not_plantable", "reason": "rock_or_ledge", "observer": "Ana"})
    assert r.status_code == 201
    j2 = post(client, {"species_counts": {"8": 36, "7": 49}}).json()
    assert first["point_id"] not in {i["point_id"] for i in j2["plan"]}
    assert j2["summary"]["field_checks"]["excluded_points"] >= 1
    assert j2["summary"]["zoning"]["include_unzoned"] is True and "ground_cover" in j2["summary"]                 # zoning and ground flags are still worked out


def test_preview_counts_blocks_per_species(client):
    r = client.post("/plan-event/preview", json={**BASE, "species_counts": {"8": 30, "7": 20}})
    assert r.status_code == 200
    est = r.json()["blocks_estimate"]
    assert est["blocks_about"] == 2 and [x["blocks"] for x in est["per_species"]] == [math.ceil(30 / CAP(8)), math.ceil(20 / CAP(7))]


def test_command_line_gives_the_same_plan_as_the_api(client, tmp_path, monkeypatch):
    got = {}
    monkeypatch.setattr(rp, "write_plan", lambda out, purpose, plan, summary, stamp=None: (got.update(plan=plan, summary=summary) or (tmp_path / "a.csv", tmp_path / "a.json")))
    rp.main(["--purpose", "urban", "--species-counts", "8:30,7:20", "--seed", "4", "--out", str(PROCESSED), "--field-db", str(tmp_path / "none.db")])
    api = client.post("/plan-event", json={"purpose": "urban", "seed": 4, "species_counts": {"8": 30, "7": 20}}).json()
    cli = got["plan"]
    key = lambda rows: sorted((int(a), int(b), int(c)) for a, b, c in rows)
    assert key(zip(cli.point_id, cli.species_id, cli.trees_planned)) == key((i["point_id"], i["species_id"], i["trees_planned"]) for i in api["plan"])
    assert got["summary"]["species_counts"]["total_placed"] == 50


def test_command_line_input_checks(capsys):
    for bad in (["--species-counts", "8"], ["--species-counts", "8:0"], ["--species-counts", "8:30,8:5"], ["--species-counts", "8:3000"],
                ["--species-counts", "8:30", "--n-saplings", "30"]):
        with pytest.raises(SystemExit):
            rp.main(["--purpose", "urban", "--out", str(PROCESSED), *bad])
    assert rp.parse_species_counts("8:30, 7:20") == {8: 30, 7: 20}
