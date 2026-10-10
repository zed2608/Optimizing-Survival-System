"""Round 21: wording and small fixes after the round 20 audit.
 - the block estimate of the plan form equals what the plan really makes (three purposes, several tree counts and areas);
 - invalid API input answers 422 with a short plain message and the field names (no raw validation list);
 - the Known limits of the API and of a plan name the real source of S (the Random Forest by default, the rules only in rules mode);
 - the wetness wording of the Help, the tour and the user guide says the creek / river distance IS used (soft factor, 50 m) and that the waterways map is not validated;
 - the fallback notice and the rules version of the Help answer exist (the browser part is in the round 21 browser check).
Run from the repo root: python -m pytest tests/test_round21.py"""
import re, sys
from pathlib import Path
import pytest

BLOCKS_DEFAULT = True          # tests/conftest.py: keep the real defaults (blocks) in this module
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(__import__("os").environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
pytestmark = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.db").exists() or not (PROCESSED / "purpose_scores.csv").exists(),
                                reason="run score_sites.py and score_purposes.py first")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import api_v2  # noqa: E402
import field_verify as fv  # noqa: E402
import run_plan as rp  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

WINDOW = {"start": "2027-05-10", "end": "2027-06-30"}


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


# ---------------------------------------------------------------- 3. the block estimate equals the real plan
@pytest.mark.parametrize("purpose", ["urban", "planting", "watershed"])
@pytest.mark.parametrize("n", [10, 50, 300, 1000])
def test_the_estimate_equals_the_blocks_of_the_real_plan(client, purpose, n):
    body = {"purpose": purpose, "n_saplings": n, "barangay": "GUINAYANG"}
    prev = client.post("/plan-event/preview", params=WINDOW, json=body).json()
    est = prev["blocks_estimate"]
    real = client.post("/plan-event", params=WINDOW, json={**body, "campaign": {"name": f"est {purpose} {n}", "unit": "t"}}).json()
    blocks = real["blocks"]["blocks"]
    assert est["exact"] is True and est["blocks_about"] == blocks == est["blocks_low"] == est["blocks_high"], (purpose, n, est, blocks)
    assert est["hectares_about"] == pytest.approx(real["blocks"]["hectares"])
    assert real["blocks"]["trees"] == sum(x["trees_planned"] for x in real["plan"])
    if real["blocks"]["trees"] == n:
        assert abs(est["typical_trees_per_block"] * blocks - n) <= blocks               # "N blocks of X trees" multiplies back to about the trees asked


def test_the_form_line_multiplies_back_to_the_trees(client):
    """The round 20 finding: 'About 5 blocks of 64 trees' for 300 trees while the plans had 12 to 16 blocks. Now 'N blocks of X trees' is what the plan makes."""
    for purpose in ("urban", "planting", "watershed"):
        e = client.post("/plan-event/preview", params=WINDOW, json={"purpose": purpose, "n_saplings": 300, "barangay": "GUINAYANG"}).json()["blocks_estimate"]
        assert e["blocks_about"] * e["typical_trees_per_block"] == pytest.approx(300, abs=e["blocks_about"]) and e["blocks_about"] >= 8, e


def test_the_estimate_of_other_areas_and_chosen_species(client):
    for body in ({"purpose": "urban", "n_saplings": 120, "barangay": "STA ANA"}, {"purpose": "planting", "n_saplings": 80, "barangay": "MALY"},
                 {"purpose": "urban", "n_saplings": 200, "species_ids": [8, 1, 3, 42]}):
        est = client.post("/plan-event/preview", params=WINDOW, json=body).json()["blocks_estimate"]
        real = client.post("/plan-event", params=WINDOW, json={**body, "campaign": {"name": "est", "unit": "t"}}).json()
        assert est["blocks_about"] == real["blocks"]["blocks"], (body, est)


def test_exact_counts_keep_their_own_exact_estimate(client):
    r = client.post("/plan-event/preview", params=WINDOW, json={"purpose": "urban", "species_counts": {"8": 30, "7": 20}, "barangay": "STA ANA"}).json()
    assert r["blocks_estimate"]["blocks_about"] == len(r["blocks_estimate"]["per_species"]) or r["blocks_estimate"]["blocks_about"] >= 2


# ---------------------------------------------------------------- 5. plain validation messages
def test_invalid_input_gives_a_short_plain_message_with_the_field_names(client):
    r = client.post("/plan-event", json={"purpose": "urban", "n_saplings": 5000, "barangay": "STA ANA"})
    j = r.json()
    assert r.status_code == 422 and set(j) == {"message", "detail", "fields"}
    assert "n_saplings must be less than or equal to 2000" in j["message"] and j["fields"] == ["n_saplings"] and j["detail"] == j["message"]
    assert not any(w in r.text for w in ("\"loc\"", "\"type\"", "\"input\"", "\"ctx\"", "less_than_equal"))


@pytest.mark.parametrize("path,method,body,field", [
    ("/plan-event", "post", {}, "purpose"),
    ("/plan-event", "post", {"n_saplings": 10}, "purpose"),
    ("/plan-event", "post", {"purpose": "fun", "n_saplings": 10}, "purpose"),
    ("/plan-event", "post", {"purpose": "urban", "n_saplings": 0}, "n_saplings"),
    ("/plan-event", "post", {"purpose": "urban", "n_saplings": "many"}, "n_saplings"),
    ("/plan-event", "post", {"purpose": "urban", "n_saplings": 10, "species_ids": []}, "species_ids"),
    ("/plan-event", "post", {"purpose": "urban", "n_saplings": 10, "campaign": {"name": "", "unit": ""}}, "campaign.name"),
    ("/field-checks", "post", {}, "point_id"),
    ("/rank", "get", None, "purpose"),
    ("/search/all?q=a", "get", None, "q"),
])
def test_every_kind_of_invalid_input_is_plain(client, path, method, body, field):
    r = client.post(path, json=body) if method == "post" else client.get(path)
    j = r.json()
    assert r.status_code == 422 and isinstance(j["message"], str) and j["message"].startswith("The request could not be used: ")
    assert field in j["fields"] and field in j["message"] and isinstance(j["fields"], list)
    assert "[" not in j["message"] and "{" not in j["message"] and "_" not in j["message"].replace("n_saplings", "").replace("species_ids", "").replace("point_id", "")


def test_a_model_level_error_keeps_its_own_sentence(client):
    r = client.post("/plan-event", json={"purpose": "urban", "species_counts": {"8": 10}, "n_saplings": 99, "barangay": "STA ANA"})
    assert r.status_code == 422 and "n_saplings (99) is not the total of species_counts (10)" in r.json()["message"]


def test_the_own_messages_of_the_service_are_unchanged(client):
    r = client.get("/species/9999")
    assert r.status_code == 404 and "not found" in r.json()["detail"] and "message" not in r.json()
    r = client.post("/plan-event", params={"start": "2027-06-30", "end": "2027-05-10"}, json={"purpose": "urban", "n_saplings": 10, "barangay": "STA ANA"})
    assert r.status_code == 422 and "before the start date" in r.json()["detail"]


def test_the_plain_message_function_limits_its_length():
    errs = [{"loc": ("body", f"f{i}"), "msg": "Field required", "type": "missing"} for i in range(9)]
    m, fields = api_v2.plain_validation_message(errs)
    assert fields[0] == "f0" and len(fields) == 9 and "(and 5 more)" in m and m.count(";") == 3


# ---------------------------------------------------------------- 4. the Known limits name the real source of S
def test_known_limits_describe_the_default_source(client):
    limits = client.get("/health").json()["limits"]
    s = [t for t in limits if t.startswith("S comes from")]
    assert client.app.state.data.ctx.s_source in ("rf", "rules")
    if client.app.state.data.ctx.s_source == "rf":
        assert s == [rp.S_LIMIT_RF] and "Random Forest trained on expert rules" in s[0] and "rule limits" in s[0]
    else:
        assert s == [rp.S_LIMIT_RULES]
    assert not any("Suitability S comes from rules" in t for t in limits)


def test_the_plan_limits_name_the_source_of_s(client):
    plan = client.post("/plan-event", params=WINDOW, json={"purpose": "urban", "n_saplings": 20, "barangay": "STA ANA", "campaign": {"name": "x", "unit": "t"}}).json()
    mine = [t for t in plan["limits"] if t.startswith("S comes from")]
    assert len(mine) == 1 and "{S_LIMIT}" not in " ".join(plan["limits"])
    ctx = client.app.state.data.ctx
    assert mine[0] == rp.s_limit_text(ctx)


def test_s_limit_text_for_both_sources():
    class C:
        s_source = "rules"
    assert rp.s_limit_text(C()) == rp.S_LIMIT_RULES and "expert rules" in rp.S_LIMIT_RULES and "Random Forest" not in rp.S_LIMIT_RULES
    C.s_source = "rf"
    assert rp.s_limit_text(C()) == rp.S_LIMIT_RF and "Random Forest" in rp.S_LIMIT_RF and "apply first" in rp.S_LIMIT_RF


# ---------------------------------------------------------------- 1. the wetness wording is consistent everywhere
WET_TEXT = ["frontend/src/new/tutorial/tutorialContent.js", "docs/USER_GUIDE.md", "README.md", "docs/INTERVIEW_FINDINGS.md",
            "docs/defense/LIMITATIONS.md", "docs/defense/PANEL_QA.md", "docs/defense/ALGORITHMS.md"]


def test_no_text_says_the_creek_rule_is_not_used():
    bad = re.compile(r"(creeks?|waterways?)[^.\n]{0,60}(50 ?m(etre)?s? )?(wetness )?(rule )?(are|is) not used|50 metre wetness rule are not used", re.I)
    for f in WET_TEXT:
        text = (ROOT / f).read_text(encoding="utf-8")
        for line in text.splitlines():
            if "wrongly say" in line or "wrong for the scoring" in line or "audit" in line.lower():
                continue                                                               # the audit notes quote the old sentence on purpose
            assert not bad.search(line), (f, line[:160])


def test_the_help_says_how_the_wetness_factor_is_used():
    t = (ROOT / "frontend/src/new/tutorial/tutorialContent.js").read_text(encoding="utf-8")
    assert t.count("soft wetness factor (50 metres)") >= 2 and t.count("has not been validated by MENRO") >= 2
    g = (ROOT / "docs/USER_GUIDE.md").read_text(encoding="utf-8")
    assert g.count("soft wetness factor (50 metres)") >= 2 and "slope, height, soil, zone and rain" not in g and "zone and rain" not in t


def test_the_wetness_term_is_really_in_the_scores():
    import score_sites as ss
    assert ss.TERM_WEIGHTS["wetness"] == 0.25 and ss.WETNESS_RISK_DISTANCE_M == 50.0 and "CREEK" in ss.WATER_CLASSES and "RIVER" in ss.WATER_CLASSES


# ---------------------------------------------------------------- 2. the fallback notice and the Help text (source level; the browser check shows them)
def test_the_notice_and_the_rules_answer_exist_in_the_source():
    n = (ROOT / "frontend/src/new/ScoreSourceNotice.jsx").read_text(encoding="utf-8")
    assert "Random Forest scores are not loaded. The app is using the rule scores. Run scripts/rebuild_scores.py." in n
    assert "s_source === 'rules' && health.s_source_requested === 'rf'" in (ROOT / "frontend/src/new/scoreSource.js").read_text(encoding="utf-8")
    app = (ROOT / "frontend/src/new/AppNew.jsx").read_text(encoding="utf-8")
    assert "<ScoreSourceNotice" in app and "usingRules={usingRules}" in app
    c = (ROOT / "frontend/src/new/tutorial/tutorialContent.js").read_text(encoding="utf-8")
    assert "aRules:" in c and "Right now the Random Forest scores are not loaded" in c and "export function faqAnswer" in c


def test_health_gives_the_two_fields_the_notice_reads(client):
    h = client.get("/health").json()
    assert {"s_source", "s_source_requested"} <= set(h)
