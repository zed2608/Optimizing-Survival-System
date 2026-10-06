"""Plan tool, part 1: campaign fields, species_ids, relaxed caps, barangay areas, the capacity preview, and the command line matching the API.
Run from the repo root: python -m pytest tests/test_api_plan_tool.py"""
import itertools, json, shutil, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")      # OS_DATA_DIR = a temporary copy of the processed data
SCORES = PROCESSED / "scores" / "site_scores.db"
pytestmark = pytest.mark.skipif(not SCORES.exists() or not (PROCESSED / "purpose_scores.csv").exists(), reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
import matching as mt  # noqa: E402
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
    api_v2.fv.connect(data.field_db).close()
    api_v2.refresh_field(data)


BASE = {"purpose": "urban", "n_saplings": 60, "seed": 3}
MAY = {"start": "2027-05-01", "end": "2027-06-29"}


def post(client, body, **q):
    return client.post("/plan-event", params=q, json=body)


def pair_set(j):
    return [(x["point_id"], x["species_id"]) for x in j["plan"]]


def top_species(client, barangay="STA ANA", k=3):
    r = client.post("/rank/area", json={"purpose": "urban", "barangay": barangay, "limit": 45}).json()
    return [x["species_id"] for x in r["ranking"][:k]]


# ---- campaign -------------------------------------------------------------------------------------------------------------------------
def test_campaign_name_unit_and_dates_are_saved_and_returned(client, data):
    r = post(client, {**BASE, "campaign": {"name": "  Tree Day 2027  ", "unit": "MENRO field team"}}, **MAY)
    assert r.status_code == 200
    j = r.json()
    assert j["campaign"] == {"status": "saved", "name": "Tree Day 2027", "unit": "MENRO field team", "start": "2027-05-01", "end": "2027-06-29", "missing": []}
    saved = json.loads((Path(data.work) / "plans" / f"{j['plan_id']}_summary.json").read_text(encoding="utf-8"))
    assert saved["campaign"] == {"name": "Tree Day 2027", "unit": "MENRO field team", "start": "2027-05-01", "end": "2027-06-29"}
    lst = [p for p in client.get("/plans").json()["plans"] if p["plan_id"] == j["plan_id"]][0]
    assert lst["campaign"]["name"] == "Tree Day 2027" and lst["n_placed"] == j["summary"]["saplings_placed"] and lst["n_species"] == len(j["palette"])
    assert lst["purpose"] == "urban" and lst["field_kit_built"] is False
    g = client.get(f"/plans/{j['plan_id']}").json()
    assert g["campaign"] == j["campaign"] and g["n_species"] == len(j["palette"]) and g["n_placed"] == j["n_placed"]


@pytest.mark.parametrize("campaign", [{"name": ""}, {"name": "   "}, {"name": "x" * 81}, {"name": "ok", "unit": "u" * 81}, {"name": "bad\nname"}, {"name": "ok", "unit": "bad\tunit"}, {}, {"unit": "no name"}])
def test_invalid_campaign_names_are_rejected_and_nothing_is_saved(client, data, campaign):
    r = post(client, {**BASE, "campaign": campaign})
    assert r.status_code == 422
    assert client.get("/plans").json()["total_saved"] == 0


def test_the_longest_names_are_accepted_and_an_empty_unit_is_fine(client):
    r = post(client, {**BASE, "campaign": {"name": "n" * 80, "unit": ""}})
    assert r.status_code == 200 and r.json()["campaign"]["name"] == "n" * 80 and r.json()["campaign"]["unit"] == ""


def test_a_plan_without_campaign_fields_returns_explicit_missing_markers_never_an_error(client, data):
    j = post(client, BASE).json()
    c = j["campaign"]
    assert c["status"] == "missing" and c["name"] is None and c["unit"] is None and set(c["missing"]) >= {"name", "unit"}
    # an older plan file: remove everything the newer code adds
    sj = Path(data.work) / "plans" / f"{j['plan_id']}_summary.json"
    s = json.loads(sj.read_text(encoding="utf-8"))
    for k in ("campaign", "season", "area_choice", "species_selection", "field_checks"):
        s.pop(k, None)
    sj.write_text(json.dumps(s), encoding="utf-8")
    old = client.get(f"/plans/{j['plan_id']}")
    assert old.status_code == 200 and old.json()["campaign"]["status"] == "missing" and old.json()["campaign"]["missing"] == ["name", "unit", "start", "end"]
    item = [p for p in client.get("/plans").json()["plans"] if p["plan_id"] == j["plan_id"]][0]
    assert item["campaign"]["name"] is None and item["campaign"]["status"] == "missing"


# ---- defaults unchanged -----------------------------------------------------------------------------------------------------------------
def test_without_the_new_options_the_palette_and_items_are_exactly_as_before(client, data):
    j = post(client, BASE).json()
    before, bsum = rp.make_plan(data.ctx, "urban", 60, seed=3)
    assert pair_set(j) == list(zip(before.point_id.astype(int), before.species_id.astype(int)))
    assert [(p["species_id"], p["quota"]) for p in j["palette"]] == [(p["species_id"], p["quota"]) for p in bsum["palette"]]
    assert "species_selection" not in j["summary"]
    with_campaign = post(client, {**BASE, "campaign": {"name": "x"}}).json()
    assert pair_set(with_campaign) == pair_set(j)                                 # a campaign label changes nothing about the plan
    zone = data.zone_names[0]
    jz = post(client, {**BASE, "zone": zone}).json()
    bz, _ = rp.make_plan(data.ctx, "urban", 60, zone=zone, seed=3)
    assert pair_set(jz) == list(zip(bz.point_id.astype(int), bz.species_id.astype(int)))


# ---- species_ids ------------------------------------------------------------------------------------------------------------------------
def test_species_ids_restrict_the_palette_and_relax_the_caps_with_a_plain_warning(client):
    ids = top_species(client, k=2)
    j = post(client, {**BASE, "n_saplings": 100, "barangay": "STA ANA", "species_ids": ids}).json()
    assert {p["species_id"] for p in j["palette"]} <= set(ids) and {x["species_id"] for x in j["plan"]} <= set(ids)
    sel = j["summary"]["species_selection"]
    assert sel["species_ids_requested"] == ids and sel["caps"]["max_species_share"]["default"] == 0.2
    assert sel["caps_relaxed"]["max_species_share"]["used"] >= 0.5 and sel["caps_relaxed"]["max_genus_share"]["used"] >= 0.5 - 1e-9
    assert "Only 2 species: low diversity, higher pest risk" in j["summary"]["palette_warnings"]
    assert any(w.startswith("Caps relaxed:") for w in j["summary"]["palette_warnings"])
    assert j["summary"]["saplings_allocated"] == 100                                # the relaxed caps absorb every sapling
    assert not any(w.startswith("palette_smaller_than_min") for w in j["summary"]["palette_warnings"])


def test_one_species_is_a_single_species_planting(client):
    ids = top_species(client, k=1)
    j = post(client, {**BASE, "n_saplings": 50, "barangay": "STA ANA", "species_ids": ids}).json()
    assert len(j["palette"]) == 1 and j["palette"][0]["share"] == 1.0
    assert "Single species planting: high pest and disease risk" in j["summary"]["palette_warnings"]
    assert j["summary"]["species_selection"]["caps_relaxed"]["max_species_share"]["used"] == 1.0


def test_enough_species_need_no_relaxation(client):
    ids = top_species(client, k=8)
    j = post(client, {**BASE, "n_saplings": 60, "species_ids": ids}).json()
    sel = j["summary"]["species_selection"]
    assert sel["caps_relaxed"] == {} and "default" in sel["caps_note"]


def test_unknown_species_ids_give_a_404_in_plain_words(client):
    r = post(client, {**BASE, "species_ids": [1, 9999]})
    assert r.status_code == 404 and "9999" in r.json()["detail"] and "not found" in r.json()["detail"]
    assert client.get("/plans").json()["total_saved"] == 0
    assert post(client, {**BASE, "species_ids": []}).status_code == 422


def test_chosen_species_that_cannot_be_used_give_a_400_in_plain_words(client, data):
    sp = data.ctx.species
    for b, bname in enumerate(data.barangay_names):                                # a (barangay, species) pair with no suitable square at all
        m = data.point_barangay == b
        el = (data.ctx.S[m] >= mt.CFG["s_min"]).any(axis=0) if m.any() else None
        if el is not None and not el.all():
            sid = int(sp.species_id.iloc[int(np.where(~el)[0][0])])
            r = post(client, {**BASE, "barangay": bname, "species_ids": [sid]})
            assert r.status_code == 400 and "None of your chosen species can be planted in this area" in r.json()["detail"]
            return
    pytest.skip("every species has a suitable square in every barangay")


def test_species_ids_follow_the_season_rules(client, data):
    out = [sid for sid, m in zip(data.ctx.species.species_id.astype(int), data.species_months) if m and not (m & {5, 6})]
    ins = [sid for sid, m in zip(data.ctx.species.species_id.astype(int), data.species_months) if m and {5, 6} <= m]
    assert out and len(ins) >= 3
    r = post(client, {**BASE, "species_ids": out[:2]}, start="2027-05-01", end="2027-06-30", season_filter="only")
    assert r.status_code == 400 and "outside their best months" in r.json()["detail"]
    ok = post(client, {**BASE, "species_ids": ins[:3] + out[:1]}, start="2027-05-01", end="2027-06-30", season_filter="only").json()
    assert {p["species_id"] for p in ok["palette"]} <= set(ins[:3]) and ok["summary"]["species_selection"]["species_ids_removed_by_season"] == out[:1]
    assert set(ok["summary"]["season"]["palette_common_months"]) <= {5, 6}


# ---- area by barangay, field checks -------------------------------------------------------------------------------------------------------
def test_a_plan_by_barangay_stays_inside_it_and_says_which(client, data):
    j = post(client, {**BASE, "barangay": "Santa Ana"}).json()                      # the display name works
    b = data.barangay_names.index("STA ANA")
    assert j["summary"]["area_choice"]["name"] == "STA ANA" and j["summary"]["area_choice"]["display_name"] == "Santa Ana"
    for x in j["plan"]:
        assert data.point_barangay[data.legal_index[x["point_id"]]] == b and x["barangay"] == "STA ANA"
    assert post(client, {**BASE, "barangay": "Nowhere"}).status_code == 400


def test_a_point_marked_not_plantable_is_not_used_in_a_new_plan(client, data):
    j = post(client, {**BASE, "barangay": "STA ANA"}).json()
    pid = j["plan"][0]["point_id"]
    assert client.post("/field-checks", json={"point_id": pid, "status": "not_plantable", "reason": "paved", "observer": "Ana"}).status_code == 201
    j2 = post(client, {**BASE, "barangay": "STA ANA"}).json()
    assert pid not in {x["point_id"] for x in j2["plan"]} and j2["summary"]["field_checks"]["excluded_points"] == 1


# ---- preview ----------------------------------------------------------------------------------------------------------------------------------
def test_the_preview_reports_capacity_without_saving_anything(client):
    j = client.post("/plan-event/preview", json={**BASE, "n_saplings": 2000, "barangay": "STA ANA"}).json()
    assert j["can_create"] is True and j["area"]["display_name"] == "Santa Ana" and 0 < j["area"]["suitable_squares"] <= j["area"]["candidate_squares"]
    assert j["capacity"]["short"] is True and j["capacity"]["message"] == f"Only {j['area']['suitable_squares']} suitable squares: at most {j['area']['suitable_squares']} trees can be placed"
    ok = client.post("/plan-event/preview", json={**BASE, "n_saplings": 10, "barangay": "STA ANA"}).json()
    assert ok["capacity"]["short"] is False and ok["capacity"]["message"] == "" and ok["species"]["mode"] == "auto"
    chosen = client.post("/plan-event/preview", json={**BASE, "barangay": "STA ANA", "species_ids": top_species(client, k=2)}).json()
    assert chosen["species"]["mode"] == "chosen" and chosen["species"]["available"] == 2
    assert client.get("/plans").json()["total_saved"] == 0


def test_the_preview_says_when_the_dates_leave_no_species(client):
    j = client.post("/plan-event/preview", params={"start": "2026-10-05", "end": "2026-11-04", "season_filter": "only"}, json=BASE)
    assert j.status_code == 200 and j.json()["can_create"] is False and j.json()["reason"] == "no_species_in_season" and "out of season" in j.json()["message"]
    assert j.json()["season"]["removed"] == 45
    assert post(client, BASE, start="2026-10-05", end="2026-11-04", season_filter="only").status_code == 400      # and a plan is never created
    assert client.get("/plans").json()["total_saved"] == 0
    assert client.post("/plan-event/preview", json={**BASE, "species_ids": [9999]}).status_code == 404


def test_plan_ids_are_still_validated_strictly(client):
    for bad in ("..%2Fx", "a b", "plan%00x"):
        assert client.get(f"/plans/{bad}").status_code in (400, 404, 422)


# ---- the command line matches the API ---------------------------------------------------------------------------------------------------
def test_the_command_line_makes_the_same_plan_as_the_api(client, data, tmp_path, monkeypatch, capsys):
    out = tmp_path / "processed"
    out.mkdir()
    for n in ("site_points_clean.csv", "species_clean.csv", "purpose_scores.csv", "species_sources.csv"):
        shutil.copy(PROCESSED / n, out / n)
    counter, written = itertools.count(), []
    orig = rp.write_plan

    def write_plan(out_dir, purpose, plan, summary, stamp=None):
        f, sj = orig(out_dir, purpose, plan, summary, f"c{next(counter)}")
        written.append((f, sj))
        return f, sj

    monkeypatch.setattr(rp, "write_plan", write_plan)
    ids = top_species(client, k=2)

    def cli(*extra):
        rp.main(["--out", str(out), "--scores", str(SCORES), "--field-db", str(tmp_path / "none.db"), "--purpose", "urban", "--n-saplings", "100", "--seed", "3", *extra])
        f, sj = written[-1]
        return pd.read_csv(f), json.loads(sj.read_text(encoding="utf-8"))

    plan, s = cli("--species-ids", ",".join(map(str, ids)), "--campaign-name", "Tree Day", "--campaign-unit", "MENRO")
    api = post(client, {**BASE, "n_saplings": 100, "species_ids": ids, "campaign": {"name": "Tree Day", "unit": "MENRO"}}).json()
    assert list(zip(plan.point_id, plan.species_id)) == pair_set(api)
    assert s["campaign"] == {"name": "Tree Day", "unit": "MENRO"}
    assert s["species_selection"]["caps"] == api["summary"]["species_selection"]["caps"] and s["palette_warnings"] == api["summary"]["palette_warnings"]
    plain, ps = cli()                                                                # without the new options: no campaign, no species_selection
    assert "campaign" not in ps and "species_selection" not in ps
    with pytest.raises(SystemExit):
        cli("--species-ids", "1,9999")
    with pytest.raises(SystemExit):
        cli("--campaign-unit", "no name")
    with pytest.raises(SystemExit):
        cli("--campaign-name", "x" * 81)
