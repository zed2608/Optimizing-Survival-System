"""Round 17: "Ways to improve survival" (advice only). The advice never changes S, P or W; every rule has a text and a source; the API returns the advice.
Run from the repo root: python -m pytest tests/test_advice.py"""
import hashlib, os, re, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import advice as sva  # noqa: E402
import field_verify as fv  # noqa: E402

needs = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.csv").exists(), reason="run the pipeline first")


@pytest.fixture(scope="module")
def client():
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh(client, tmp_path, monkeypatch):
    import api_v2
    d = client.app.state.data
    monkeypatch.setattr(d, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(d, "work", tmp_path)
    fv.connect(d.field_db).close()
    api_v2.refresh_field(d)


def sha_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---- the rules file ---------------------------------------------------------------------------------------------------------------------------
def test_every_rule_has_a_text_a_source_and_is_provisional():
    rules = sva.load_rules(PROCESSED)
    assert set(rules) >= {"habagat", "rehab_site", "spacing_multi", "low_drought", "low_wind", "shade_partner", "shade_tolerant", "shade_cacao", "fruit_grafted"}
    for rid, r in rules.items():
        assert r["text"].strip() and r["source"].strip() and r["trigger"].strip(), rid
        assert r["provisional"].lower() == "true", rid
        assert r["source"].startswith(("MAO interview", "General practice")), rid        # no source invented: only the interview or "to be confirmed"
    assert "General practice" in rules["low_drought"]["source"] and "to be confirmed" in rules["low_wind"]["source"]
    assert "MAO interview" in rules["habagat"]["source"] and "MAO interview" in rules["fruit_grafted"]["source"]


def test_no_visible_advice_text_has_an_underscore_an_equals_sign_or_a_percentage_except_cacao():
    rules = sva.load_rules(PROCESSED)
    for rid, r in rules.items():
        for field in ("text", "source"):
            assert "_" not in r[field] and "=" not in r[field], (rid, field)
        if rid != "shade_cacao":
            assert "%" not in r["text"], rid
    assert "60%" in rules["shade_cacao"]["text"]
    assert "_" not in sva.NOTE and "%" not in sva.NOTE


def test_rule_wording_is_exactly_the_one_of_the_request():
    r = sva.load_rules(PROCESSED)
    assert r["habagat"]["text"] == "Heavy rain and flooding can wash out young trees here in July to September. Plant on higher ground or wait until the rains ease."
    assert r["low_drought"]["text"] == "Mulch around the base and water young trees during the dry months (December to May). A shade companion also helps."
    assert r["low_wind"]["text"] == "Plant a windbreak row on the exposed side and stake young trees before typhoon season."
    assert r["fruit_grafted"]["text"] == "Ask the nursery for grafted or marcotted stock if it is available. Such trees often fruit earlier."
    assert r["rehab_site"]["text"] == "Prefer bamboo or non-edible trees here. Do not eat or sell fruit from this site without testing."
    assert r["spacing_multi"]["text"] == "Keep proper distance between trees so their shade and roots do not compete."
    assert sva.NOTE == "Advice from the agriculturist, not yet confirmed. It does not change the scores."


# ---- each rule fires only when its trigger is true -------------------------------------------------------------------------------------------------
def test_rules_fire_only_on_their_trigger():
    rules = sva.load_rules(PROCESSED)
    base = {"common_name": "Test", "drought_tol": "High", "typhoon_res": "High", "shade_tol": "Low", "light_preference": "Full Sun"}
    assert sva.species_advice(rules, base, [], []) == []
    ids = lambda **k: [i["rule_id"] for i in sva.species_advice(rules, {**base, **k.pop("row", {})}, k.pop("tags", []), k.pop("partners", []), **k)]  # noqa: E731
    assert ids(row={"drought_tol": "Low"}) == ["low_drought"]
    assert ids(row={"typhoon_res": "Low"}) == ["low_wind"]
    assert ids(tags=["fruit-bearing"]) == ["fruit_grafted"]
    assert ids(habagat=True) == ["habagat"] and ids(rehab=True) == ["rehab_site"]
    shade = {"shade_tol": "High", "light_preference": "Partial Shade"}
    assert ids(row=shade) == []                                                    # needs a listed partner
    assert ids(row=shade, partners=["Banana", "Coconut"]) == ["shade_tolerant"]                  # tolerates shade: not one of the two that need it
    assert ids(row={**shade, "common_name": "Robusta (Coffee)"}, partners=["Banana"]) == ["shade_partner"]
    assert ids(row={**shade, "common_name": "Cacao"}, partners=["Banana"]) == ["shade_partner"]
    assert ids(row={"shade_tol": "High", "light_preference": "Full Sun"}, partners=["Banana"]) == []
    only = sva.species_advice(rules, {**base, **shade}, [], ["Banana", "Coconut"])[0]["text"]
    assert only == "This tree tolerates shade, so it can grow under taller trees. Pair it with Banana and Coconut." and "60%" not in only and "needs" not in only
    robusta = sva.species_advice(rules, {**base, **shade, "common_name": "Robusta (Coffee)"}, [], ["Banana"])[0]["text"]
    assert robusta == "This tree grows better with shade. Pair it with Banana."
    cacao = sva.species_advice(rules, {**base, **shade, "common_name": "Cacao"}, [], ["Banana"])[0]
    assert cacao["text"].endswith("Cacao needs about 60% shade.") and "MAO interview" in cacao["source"]
    assert all(i["provisional"] is True for i in sva.species_advice(rules, {**base, "drought_tol": "Low", "typhoon_res": "Low"}, ["fruit-bearing"], []))
    # a plan: every rule once, with its species; two or more species add the spacing rule; flags on the plan add the place rules
    sp = lambda n, **row: {"row": {**base, "common_name": n, **row}, "tags": [], "partners": [], "name": n}  # noqa: E731
    plan = sva.plan_advice(rules, [sp("A", drought_tol="Low"), sp("B", drought_tol="Low")], habagat_trees=0, rehab_trees=0)
    assert [i["rule_id"] for i in plan] == ["spacing_multi", "low_drought"] and plan[1]["species"] == ["A", "B"]
    assert [i["rule_id"] for i in sva.plan_advice(rules, [sp("A")], 0, 0)] == []
    assert [i["rule_id"] for i in sva.plan_advice(rules, [sp("A")], 5, 3)] == ["habagat", "rehab_site"]
    assert sva.LIMIT_SPECIES_SIMPLE == 4 and sva.LIMIT_PLAN_SIMPLE == 5


# ---- the scores never change -----------------------------------------------------------------------------------------------------------------------
@needs
def test_scores_are_identical_before_and_after_for_200_fixed_pairs(client):
    d = client.app.state.data
    sites = d.ctx.sites
    rng = np.random.default_rng(17)
    S, P = d.ctx.S, d.ctx.P["urban"]
    n_sites, n_sp = S.shape
    pairs = sorted({(int(a), int(b)) for a, b in zip(rng.integers(0, n_sites, 400), rng.integers(0, n_sp, 400))})[:200]
    assert len(pairs) == 200

    def snapshot():
        rows = []
        for i, k in pairs:
            w = float(S[i, k]) * float(P[k]) if S[i, k] >= 0.5 else 0.0
            row = [int(sites.point_id.iloc[i]), int(d.ctx.species.species_id.iloc[k]), round(float(S[i, k]), 6), round(float(P[k]), 6), round(w, 6)]
            rows.append(row)
        return pd.DataFrame(rows, columns=["point_id", "species_id", "S", "P", "W"])

    files = [PROCESSED / "scores" / "site_scores.csv", PROCESSED / "purpose_scores.csv"]
    h_before = [sha_of(f) for f in files]
    before = snapshot()
    # the same pairs through the API (rank gives S, P and W)
    def api_scores():
        out = []
        for pid in sorted(set(before.point_id)):
            r = client.get("/rank", params={"purpose": "urban", "lat": float(sites.lat[sites.point_id == pid].iloc[0]), "lon": float(sites.lon[sites.point_id == pid].iloc[0]), "limit": 45})
            assert r.status_code == 200
            for it in r.json()["ranking"]:
                out.append((pid, int(it["species_id"]), round(float(it["S"]), 6), round(float(it["P"]), 6), round(float(it["W"]), 6)))
        return sorted(out)

    api_before = api_scores()
    # use the advice everywhere: every species, every sample point, and two plans
    for sid in sorted(set(before.species_id)):
        assert client.get(f"/species/{sid}/advice").status_code == 200
    for pid, sid in list(zip(before.point_id, before.species_id))[:60]:
        assert client.get(f"/species/{sid}/advice", params={"point_id": int(pid), "start": "2027-07-01", "end": "2027-07-31"}).status_code == 200
    assert client.post("/plan-event", json={"purpose": "urban", "n_saplings": 60, "barangay": "Santa Ana", "campaign": {"name": "Advice scores", "unit": ""}}).status_code == 200
    assert client.post("/plan-event", json={"purpose": "watershed", "species_counts": {17: 10, 30: 10}, "zone": "Sanitary Landfill", "campaign": {"name": "Advice scores 2", "unit": ""}}).status_code == 200
    after = snapshot()
    pd.testing.assert_frame_equal(before, after)                                  # S of the 200 pairs: identical
    assert api_scores() == api_before                                             # S, P and W as the API shows them: identical
    assert [sha_of(f) for f in files] == h_before                                 # the score files were not written
    # fixed sample, pinned: it only changes if the scores themselves change (then update it on purpose)
    digest = hashlib.sha256(before.to_csv(index=False).encode()).hexdigest()[:16]
    assert digest == SAMPLE_PIN, digest


SAMPLE_PIN = "59ebdb3e2a18c601"   # pinned again in round 18 (the graded slope rule changed the S of some sample pairs); the advice itself still changes nothing


# ---- the API ---------------------------------------------------------------------------------------------------------------------------------------
@needs
def test_api_returns_advice_for_a_low_drought_species(client):
    sp = client.app.state.data.ctx.species
    sid = int(sp[sp.drought_tol == "Low"].species_id.iloc[0])
    j = client.get(f"/species/{sid}/advice").json()
    assert j["provisional"] is True and "does not change the scores" in j["note"]
    ids = [a["rule_id"] for a in j["advice"]]
    assert "low_drought" in ids and len(ids) == len(set(ids))                   # each piece of advice once
    a = next(x for x in j["advice"] if x["rule_id"] == "low_drought")
    assert a["provisional"] is True and a["source"].startswith("General practice") and "Mulch" in a["text"]
    assert client.get("/species/9999/advice").status_code == 404


@needs
def test_api_returns_advice_for_a_landfill_square(client):
    d = client.app.state.data
    pts = d.all_points
    pid = int(pts[pts.zone_desc == "Sanitary Landfill"].point_id.iloc[0])
    food = [int(s) for s in sorted(__import__("site_rules").food_bearing_ids(d.ctx.species))][0]
    j = client.get(f"/species/{food}/advice", params={"point_id": pid}).json()
    assert "rehab_site" in [a["rule_id"] for a in j["advice"]] and j["point"]["rehab_site"] is True
    assert "Do not eat or sell fruit" in next(a for a in j["advice"] if a["rule_id"] == "rehab_site")["text"]
    # a square that is not a rehabilitation site has no such advice
    other = int(pts[pts.zone_desc == "Forest Zone"].point_id.iloc[0])
    assert "rehab_site" not in [a["rule_id"] for a in client.get(f"/species/{food}/advice", params={"point_id": other}).json()["advice"]]


@needs
def test_habagat_advice_needs_the_barangay_and_july_to_september_dates(client):
    sid = 7
    j = client.get(f"/species/{sid}/advice", params={"point_id": 832, "start": "2027-07-01", "end": "2027-07-31"}).json()
    assert "habagat" in [a["rule_id"] for a in j["advice"]] and j["point"]["habagat"] is True
    for q in ({}, {"start": "2027-01-10", "end": "2027-01-31"}):
        assert "habagat" not in [a["rule_id"] for a in client.get(f"/species/{sid}/advice", params={"point_id": 832, **q}).json()["advice"]]


@needs
def test_cacao_advice_pairs_it_with_listed_partners_and_mentions_the_shade(client):
    j = client.get("/species/17/advice").json()
    sh = next(a for a in j["advice"] if a["rule_id"] == "shade_partner")
    assert sh["text"].startswith("This tree grows better with shade. Pair it with ") and sh["text"].endswith("Cacao needs about 60% shade.")
    assert "MAO interview" in sh["source"]


@needs
def test_plan_event_and_saved_plan_carry_an_advice_list(client):
    r = client.post("/plan-event", json={"purpose": "urban", "species_counts": {17: 20, 30: 20}, "campaign": {"name": "Advice", "unit": ""}, "barangay": "Santa Ana"}).json()
    adv = r["advice"]
    assert adv["provisional"] is True and adv["limit_simple_plan"] == 5 and "does not change the scores" in adv["note"]
    ids = [i["rule_id"] for i in adv["items"]]
    assert len(ids) == len(set(ids))
    assert "spacing_multi" in ids                                                  # two species in the plan
    assert all(i["provisional"] and i["source"] and i["text"] for i in adv["items"])
    saved = client.get(f"/plans/{r['plan_id']}").json()
    assert [i["rule_id"] for i in saved["advice"]["items"]] == ids
    # a plan with food-bearing trees on a landfill carries the rehabilitation advice
    rr = client.post("/plan-event", json={"purpose": "urban", "zone": "Sanitary Landfill", "species_counts": {30: 20, 39: 20}, "campaign": {"name": "Advice rehab", "unit": ""}}).json()
    assert "rehab_site" in [i["rule_id"] for i in rr["advice"]["items"]]


@needs
def test_no_visible_advice_in_the_api_has_an_underscore_equals_or_percentage_except_cacao(client):
    sp = client.app.state.data.ctx.species
    for sid in map(int, sp.species_id):
        j = client.get(f"/species/{sid}/advice").json()
        for a in j["advice"]:
            for t in (a["text"], a["source"]):
                assert "_" not in t and "=" not in t, (sid, a["rule_id"])
            if sid != 17:
                assert "%" not in a["text"], (sid, a["rule_id"])


# ---- round 16 fix b: the example point of the tour --------------------------------------------------------------------------------------------------
@needs
def test_the_example_point_of_the_tour_exists_and_is_in_santa_ana(client):
    j = client.get("/search/point", params={"q": "832"}).json()
    assert j["point_id"] == 832 and j["barangay"] == "STA ANA" and j["zoning_status"] in ("confirmed", "unconfirmed"), j
    content = (ROOT / "frontend" / "src" / "new" / "tutorial" / "tutorialContent.js").read_text(encoding="utf-8")
    m = re.search(r"EXAMPLE_POINTS = \[([0-9, ]+)\]", content)
    assert m, "the tour keeps a list of example points (the first is 832, the others are the fallback)"
    ids = [int(x) for x in m.group(1).split(",")]
    assert ids[0] == 832 and len(ids) >= 3
    for pid in ids:                                                                 # every fallback is a scored point of Santa Ana
        r = client.get("/search/point", params={"q": str(pid)})
        assert r.status_code == 200 and r.json()["barangay"] == "STA ANA", pid


@needs
def test_needs_shade_wording_is_only_for_cacao_and_robusta(client):
    sp = client.app.state.data.ctx.species
    wording = {}
    for sid, name in zip(map(int, sp.species_id), sp.common_name):
        for a in client.get(f"/species/{sid}/advice").json()["advice"]:
            if a["rule_id"] in ("shade_partner", "shade_tolerant"):
                wording.setdefault(a["rule_id"], []).append(name)
                if a["rule_id"] == "shade_partner":
                    assert a["text"].startswith("This tree grows better with shade. Pair it with ")
                else:
                    assert a["text"].startswith("This tree tolerates shade, so it can grow under taller trees. Pair it with ") and "needs" not in a["text"]
                assert ("60%" in a["text"]) == (name == "Cacao"), name
    assert set(wording.get("shade_partner", [])) == {"Cacao", "Robusta (Coffee)"}
    assert set(wording.get("shade_tolerant", [])) == {"Kamagong", "Yakal", "White Lauan", "Red Lauan", "Bagtikan", "Apitong"}
