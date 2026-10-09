"""Round 18: the graded slope rule (SLOPE_MODE "graded" | "hard"). PROVISIONAL: a team decision, the adviser confirms.
Run from the repo root: python -m pytest tests/test_slope_mode.py"""
import os, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import score_sites as ss  # noqa: E402
import field_verify as fv  # noqa: E402

HARD_ELIGIBLE = 249_389                  # the eligible pairs (S >= 0.50) of the hard gate, scored squares 8,010 x 45 species (before round 18)
HARD_S_SUM = 225_260.5659                # sum of S (4 decimals) of the hard gate: every S, not only the count
GRADED_ELIGIBLE = 257_869
NEWLY = 8_480


def species(**kw):
    base = dict(species_id=1, elev_min_m=0.0, elev_max_m=600.0, max_slope_pct=30.0, soil_textures="Clay Loam;Clay", soil_any_texture=False, waterlog_tol="High")
    base.update(kw)
    return pd.DataFrame([base])


def site(**kw):
    base = dict(point_id=1, elev_m=200.0, slope_pct=5.0, soil_texture_legacy="Clay Loam", is_legal_zone=1, water_dist_m=500.0)
    base.update(kw)
    return pd.DataFrame([base])


def score(slope, **kw):
    return ss.score_pairs(species(), site(slope_pct=slope), **kw).iloc[0]


# ---- the config -----------------------------------------------------------------------------------------------------------------------------------
def test_config_default_is_graded_and_the_margin_is_a_quarter_of_the_limit():
    assert ss.SLOPE_MODE == "graded" and ss.SLOPE_GRADED_MARGIN_FRACTION == 0.25 and ss.ELIGIBLE_S == 0.50
    with pytest.raises(ValueError):
        ss.score_pairs(species(), site(), slope_mode="soft")


# ---- the rule on one pair -------------------------------------------------------------------------------------------------------------------------
def test_inside_the_limit_nothing_changes():
    for slope in (0.0, 10.0, 27.0, 29.9, 30.0):
        g, h = score(slope, slope_mode="graded"), score(slope, slope_mode="hard")
        assert g.s_rule == h.s_rule and not g.slope_graded, slope


def test_above_the_limit_s_falls_linearly_to_zero_over_a_margin_of_a_quarter_of_the_limit():
    base = score(30.0, slope_mode="graded").s_rule                         # S at the limit: the slope term is already 0 there, so the rule is continuous
    assert score(30.0001, slope_mode="graded").s_rule == pytest.approx(base, abs=1e-3)
    margin = 0.25 * 30.0                                                     # 7.5 points of slope
    for over in (1.5, 3.75, 6.0):
        r = score(30.0 + over, slope_mode="graded")
        assert r.s_rule == pytest.approx(base * (1 - over / margin), abs=1e-6), over
        assert not r.gate_fail_slope
    assert score(37.5, slope_mode="graded").s_rule == pytest.approx(0.0, abs=1e-9)
    beyond = score(37.6, slope_mode="graded")                               # the hard stop: beyond the margin the pair is still rejected
    assert beyond.s_rule == 0.0 and beyond.gate_fail_slope
    assert score(60.0, slope_mode="graded").s_rule == 0.0


def test_hard_mode_is_the_old_gate():
    h = score(30.5, slope_mode="hard")
    assert h.s_rule == 0.0 and h.gate_fail_slope and not h.slope_graded


def test_the_eligibility_check_still_decides_and_the_flag_marks_only_pairs_eligible_because_of_the_rule():
    r_ok = score(31.0, slope_mode="graded")                                 # 1 point over: S about 0.6, eligible only because of the rule
    assert r_ok.s_rule >= 0.5 and r_ok.slope_graded
    r_low = score(34.0, slope_mode="graded")                                # over the limit but S below 0.50: not eligible, so no flag (no caution is shown for it)
    assert 0 < r_low.s_rule < 0.5 and not r_low.slope_graded
    row = ss.build_breakdown(ss.score_pairs(species(), site(slope_pct=31.0), slope_mode="graded"), species(), site(slope_pct=31.0), {})[0]
    assert "slope_graded" in row and '"gate_failed":[]' in row
    row_hard = ss.build_breakdown(ss.score_pairs(species(), site(slope_pct=31.0), slope_mode="hard"), species(), site(slope_pct=31.0), {})[0]
    assert "slope_graded" not in row_hard and '"gate_failed":["slope"]' in row_hard


def test_the_other_gates_still_hold_in_graded_mode():
    assert ss.score_pairs(species(), site(slope_pct=31.0, is_legal_zone=0), slope_mode="graded").iloc[0].s_rule == 0.0
    assert ss.score_pairs(species(), site(slope_pct=31.0, elev_m=900.0), slope_mode="graded").iloc[0].s_rule == 0.0


# ---- the numbers of the real data --------------------------------------------------------------------------------------------------------------------
def real_scores(mode):
    sp = pd.read_csv(PROCESSED / "species_clean.csv")
    st = pd.read_csv(PROCESSED / "site_points_clean.csv")
    st = st[st.zoning_status.isin(["confirmed", "unconfirmed"])].copy()
    st["water_dist_m"] = ss.distance_to_water(st, str(ROOT / "data" / "SMR_WATERBODIES_POLY.shp"))
    return ss.score_pairs(sp, st, slope_mode=mode)


@pytest.fixture(scope="module")
def both():
    if not (PROCESSED / "site_points_clean.csv").exists():
        pytest.skip("run the pipeline first")
    return real_scores("hard"), real_scores("graded")


def test_hard_mode_reproduces_todays_numbers_exactly(both):
    h, _ = both
    assert len(h) == 360_450
    assert int((h.s_rule >= 0.5).sum()) == HARD_ELIGIBLE == 249_389
    assert round(float(h.s_rule.round(4).sum()), 4) == HARD_S_SUM
    assert not h.slope_graded.any()


def test_graded_mode_only_adds_eligible_pairs_and_changes_no_other_score(both):
    h, g = both
    assert int((g.s_rule >= 0.5).sum()) == GRADED_ELIGIBLE
    new = (g.s_rule >= 0.5) & ~(h.s_rule >= 0.5)
    assert int(new.sum()) == NEWLY and int(g.slope_graded.sum()) == NEWLY
    assert bool(((h.s_rule >= 0.5) <= (g.s_rule >= 0.5)).all())              # nothing eligible before is lost
    keep = h.s_rule > 0
    assert np.array_equal(h.s_rule[keep].to_numpy(), g.s_rule[keep].to_numpy())  # every pair that scored before keeps exactly the same S
    changed = h.s_rule != g.s_rule
    assert bool((h.s_rule[changed] == 0).all())                               # only pairs that were S = 0 (over the limit) change


def test_the_saved_scores_are_graded_and_the_api_says_so(both):
    run = PROCESSED / "scores" / "score_run.json"
    if not run.exists():
        pytest.skip("scores not made")
    import json
    j = json.loads(run.read_text(encoding="utf-8"))
    assert j["slope_mode"] == "graded" and j["eligible_pairs"] == GRADED_ELIGIBLE and j["slope_graded_pairs"] == NEWLY


# ---- API and words ----------------------------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    import api_v2
    from fastapi.testclient import TestClient
    with TestClient(api_v2.app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh(request, tmp_path, monkeypatch):
    if "client" not in request.fixturenames:
        return
    import api_v2
    client = request.getfixturevalue("client")
    d = client.app.state.data
    monkeypatch.setattr(d, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(d, "work", tmp_path)
    fv.connect(d.field_db).close()
    api_v2.refresh_field(d)


CAUTION = "Slope is steeper than this tree's usual limit. Plant on terraces or use contour planting, or choose another tree."


def test_health_reports_the_slope_mode_and_rank_shows_the_caution_flag(client):
    h = client.get("/health").json()
    assert h["slope_mode"] == "graded" and h["slope_graded_margin_fraction"] == 0.25
    n = pd.read_csv(PROCESSED / "slope_graded_newly_eligible.csv")
    r0 = n[n.zoning_status == "confirmed"].sort_values("slope_pct").iloc[len(n[n.zoning_status == "confirmed"]) // 2]
    pts = client.app.state.data.ctx.sites
    row = pts[pts.point_id == int(r0.point_id)].iloc[0]
    j = client.get("/rank", params={"purpose": "urban", "lat": float(row.lat), "lon": float(row.lon), "limit": 45}).json()
    item = next(i for i in j["ranking"] if i["species_id"] == int(r0.species_id))
    assert item["eligible"] and "slope_graded" in item["flags"] and item["S"] >= 0.5


def test_the_caution_is_in_the_words_of_the_dashboard_and_the_kit():
    import subprocess
    r = subprocess.run(["node", "--test", "src/new/plainWords.test.mjs"], cwd=ROOT / "frontend", capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-1500:]
    import field_kit as fk
    assert fk.FLAG_NOTES["slope_graded"] == CAUTION and fk.PLAIN_WARNINGS["slope_graded"] == CAUTION
    flag = (ROOT / "frontend" / "src" / "new" / "FlagList.jsx").read_text(encoding="utf-8")
    assert CAUTION in flag
    content = (ROOT / "frontend" / "src" / "new" / "tutorial" / "tutorialContent.js").read_text(encoding="utf-8")
    assert "steep slope caution" in content and "slope-caution" in content


# ---- round 18b: the unit, the steep-square setting, the kept hard results, the screens --------------------------------------------------------------
def test_slope_is_percent_and_the_steep_square_setting_is_named():
    assert ss.STEEP_SQUARE_SLOPE_PCT == 57.7                                  # about 30 degrees, in the unit of the data
    sites = pd.read_csv(PROCESSED / "site_points_clean.csv").dropna(subset=["slope_pct", "slope_deg"])
    assert np.allclose(np.degrees(np.arctan(sites.slope_pct / 100)), sites.slope_deg, atol=0.01)     # slope_deg is only derived from slope_pct
    sp = pd.read_csv(PROCESSED / "species_clean.csv")
    assert sp.max_slope_pct.min() == 15 and sp.max_slope_pct.max() == 70                              # percent, the same unit as slope_pct


def test_the_newly_eligible_list_is_in_percent_and_has_72_steep_pairs():
    n = pd.read_csv(PROCESSED / "slope_graded_newly_eligible.csv")
    assert len(n) == NEWLY and "slope_deg" not in n.columns and {"slope_pct", "max_slope_pct", "over_limit_points", "over_limit_share"} <= set(n.columns)
    steep = n[n.slope_pct > ss.STEEP_SQUARE_SLOPE_PCT]
    assert len(steep) == 72 and steep.groupby("common_name").size().to_dict() == {"Clumping Bamboo": 13, "Molave": 59}
    assert (n.over_limit_points > 0).all() and (n.over_limit_share <= 0.25 + 1e-9).all() and (n.S_graded >= 0.5).all()
    report = (PROCESSED / "slope_mode_report.txt").read_text(encoding="utf-8")
    assert "degree" not in report.replace("about 30 degrees", "")


def test_the_results_of_the_hard_gate_are_kept_under_the_suffix_hard_and_the_new_tables_are_graded():
    hard_mc, mc = PROCESSED / "model_comparison_hard.csv", PROCESSED / "model_comparison.csv"
    hard_mb, mb = PROCESSED / "matching_benchmark_hard.csv", PROCESSED / "matching_benchmark.csv"
    assert hard_mc.exists() and hard_mb.exists() and (PROCESSED / "scores" / "pair_table_hard.csv.gz").exists()
    assert hard_mc.read_bytes() != mc.read_bytes() and hard_mb.read_bytes() != mb.read_bytes()
    h = pd.read_csv(hard_mb)
    row = h[(h.purpose == "urban") & (h.layout_mode == "points") & (h.method == "hungarian")].iloc[0]
    assert round(float(row.total_W), 4) == 201.6537                          # the number of the hard gate, kept
    pt = pd.read_csv(PROCESSED / "scores" / "pair_table.csv.gz", usecols=["suitable_clean"])
    assert int(pt.suitable_clean.sum()) == GRADED_ELIGIBLE                    # the new pair table is made with the graded scores
    pth = pd.read_csv(PROCESSED / "scores" / "pair_table_hard.csv.gz", usecols=["suitable_clean"])
    assert int(pth.suitable_clean.sum()) == HARD_ELIGIBLE


def test_the_caution_is_on_the_species_row_the_verdict_and_the_plan_check_first_box():
    src = ROOT / "frontend" / "src" / "new"
    assert "nw-prow-caution" in (src / "PointPanel.jsx").read_text(encoding="utf-8")
    assert "slope_graded" in (src / "PlanResult.jsx").read_text(encoding="utf-8")
    assert "terraces or use contour planting" in (src / "PlanResult.jsx").read_text(encoding="utf-8")
