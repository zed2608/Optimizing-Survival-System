"""Task 2, steps 1 to 3 (scripts/potential_benchmark.py): the pre-registered drop rules, their thresholds and the reported numbers are pinned, so that they cannot drift silently.
 - the three rules R1, R2, R3 and their thresholds (0.10 and 4 of 5 folds; 0.30; 0.80) are the ones written before the first run (12 Oct 2026), in the code and in the first lines of the report;
 - the rule logic behaves at the boundaries (a threshold exactly met passes, just below fails);
 - the committed results give the registered verdict DROP: R1 fails (forest +0.040 over the Decision Tree, +0.084 over KNN, +0.158 over linear), R2 fails at 0.29999, R3 passes (-0.221);
 - the 430-square finding and the decision-gate numbers recomputed from the committed CSVs equal the report.
Do NOT change a threshold or a number to change the verdict: that needs a new, labelled run and a decision of the project team.
Run from the repo root: python -m pytest tests/test_potential_benchmark.py"""
import importlib.util, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("potential_benchmark", ROOT / "scripts" / "potential_benchmark.py")
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)
D = ROOT / "docs" / "defense"


# ---------------------------------------------------------------- the registered rules
def test_the_registered_thresholds_are_unchanged():
    assert pb.DROP == {"R1_margin": 0.10, "R1_folds": 4, "R2_min_r2": 0.30, "R3_max_corr": 0.80}


def test_the_registered_rule_texts_carry_the_thresholds():
    t = "\n".join(pb.DROP_TEXT)
    assert len(pb.DROP_TEXT) == 4
    assert "0.10 above EACH" in t and "at least 4 of the 5 folds" in t and "at least 0.30" in t and "at most 0.80" in t
    assert "If any of R1, R2, R3 fails, the idea is DROPPED" in t and "NOT drop rules" in t
    assert "no latitude / longitude, no nearest_feature_dist_m" in t


def test_the_settings_fixed_before_the_first_run():
    s = pb.SET
    assert s["seed"] == 42 and s["outer_folds"] == 5 and s["inner_folds"] == 3 and s["block_cells"] == 10 and s["block_cells_sensitivity"] == 20
    assert s["adjust_w_factors"] == (0.05, 0.10, 0.20)
    assert "W' = W x (1 - a x (1 - potential))" in s["adjust_w_form"] and "S and the S >= 0.50 test are untouched" in s["adjust_w_form"]
    assert "1e-6" in s["tiebreak_form"] and "not tuned" in s["tiebreak_form"]
    assert "elev_m, slope_pct" in s["features_main"] and "nearest_feature_dist_m" not in s["features_main"]
    assert pb.TIE_EPS == 1e-6


def folds(rf, dt, lin, knn):
    rows = []
    for k in range(5):
        for name, v in (("RandomForest", rf), ("DecisionTree", dt), ("Linear", lin), ("KNN", knn), ("MeanOnly", [0.0] * 5)):
            rows.append({"variant": "main", "model": name, "fold": k + 1, "r2": v[k]})
    return pd.DataFrame(rows)


def test_rule_logic_at_the_boundaries():
    better = [0.5] * 5
    # R1: a margin of at least 0.10 over EACH model (binary-exact numbers, 0.75 - 0.625 = 0.125) and better in all folds passes; a margin just below 0.10 fails
    ok = pb.evaluate_drop(folds([0.75] * 5, [0.625] * 5, [0.5] * 5, [0.625] * 5), 0.1)
    assert ok["R1"]["ok"] and ok["R2"]["ok"] and ok["R3"]["ok"] and not ok["drop"]
    assert not pb.evaluate_drop(folds([0.75] * 5, [0.6501] * 5, [0.5] * 5, [0.625] * 5), 0.1)["R1"]["ok"]
    assert not pb.evaluate_drop(folds([0.75] * 5, [0.625] * 5, [0.5] * 5, [0.6501] * 5), 0.1)["R1"]["ok"]
    # R1: better in only 3 of 5 folds fails even with a large mean margin; in 4 of 5 folds it passes
    three = pb.evaluate_drop(folds([0.9, 0.9, 0.9, 0.0, 0.0], [0.1, 0.1, 0.1, 0.2, 0.2], [0.0] * 5, [0.0] * 5), 0.1)["R1"]["detail"]["DecisionTree"]
    assert three["folds_better"] == 3 and three["margin"] > 0.10 and not three["ok"]
    four = pb.evaluate_drop(folds([0.9, 0.9, 0.9, 0.9, 0.0], [0.1, 0.1, 0.1, 0.1, 0.2], [0.0] * 5, [0.0] * 5), 0.1)
    assert four["R1"]["detail"]["DecisionTree"]["folds_better"] == 4 and four["R1"]["detail"]["DecisionTree"]["ok"] and four["R1"]["ok"]
    # R2: exactly 0.30 passes, just below fails
    assert pb.evaluate_drop(folds([0.3] * 5, [0.0] * 5, [0.0] * 5, [0.0] * 5), 0.0)["R2"]["ok"]
    assert not pb.evaluate_drop(folds([0.2999] * 5, [0.0] * 5, [0.0] * 5, [0.0] * 5), 0.0)["R2"]["ok"]
    # R3: |rho| = 0.80 passes, above fails, the sign does not matter
    assert pb.evaluate_drop(folds(better, [0.2] * 5, [0.2] * 5, [0.2] * 5), 0.80)["R3"]["ok"]
    assert not pb.evaluate_drop(folds(better, [0.2] * 5, [0.2] * 5, [0.2] * 5), 0.8001)["R3"]["ok"]
    assert not pb.evaluate_drop(folds(better, [0.2] * 5, [0.2] * 5, [0.2] * 5), -0.85)["R3"]["ok"]
    # any single failure drops the idea
    assert pb.evaluate_drop(folds(better, [0.2] * 5, [0.2] * 5, [0.2] * 5), 0.9)["drop"]


# ---------------------------------------------------------------- the reported numbers (committed CSVs)
def main_folds():
    return pd.read_csv(D / "potential_model_comparison.csv").query("variant == 'main'")


def test_the_committed_comparison_gives_the_registered_verdict_drop():
    mf = main_folds()
    r2 = mf.pivot(index="fold", columns="model", values="r2")
    assert len(mf) == 25 and sorted(r2.columns) == ["DecisionTree", "KNN", "Linear", "MeanOnly", "RandomForest"] and list(r2.index) == [1, 2, 3, 4, 5]
    rf = r2.RandomForest
    assert rf.mean() == pytest.approx(0.29999, abs=2e-5) and rf.mean() < 0.30                        # R2 fails by about 0.00001
    for other, margin in (("DecisionTree", 0.040), ("KNN", 0.084), ("Linear", 0.158)):
        assert rf.mean() - r2[other].mean() == pytest.approx(margin, abs=0.0006)
        assert int((rf > r2[other]).sum()) == 5
    v = pb.evaluate_drop(mf, -0.221)
    assert v["drop"] is True and v["R1"]["ok"] is False and v["R2"]["ok"] is False and v["R3"]["ok"] is True
    assert v["R1"]["detail"]["DecisionTree"]["ok"] is False and v["R1"]["detail"]["KNN"]["ok"] is False and v["R1"]["detail"]["Linear"]["ok"] is True


def test_the_correlation_with_the_rules_is_minus_0_221():
    if not (ROOT / "data/processed/scores/site_scores.csv").exists():
        pytest.skip("the saved scores are git-ignored: run scripts/rebuild_scores.py")
    o = pd.read_csv(D / "potential_oof_main.csv")
    c = pb.rule_correlation(pd.DataFrame({"point_id": o.point_id}), o.potential_oof.to_numpy())
    assert c["mean_s_rule"] == pytest.approx(-0.221, abs=0.002) and abs(c["mean_s_rule"]) <= pb.DROP["R3_max_corr"]
    assert c["n_eligible_rf"] == pytest.approx(-0.315, abs=0.003)


def test_the_430_square_finding():
    from sklearn.metrics import roc_auc_score
    o = pd.read_csv(D / "potential_oof_main.csv")
    low = (o.share_tree_observed < 0.5).to_numpy()
    p = o.potential_oof.to_numpy()
    assert len(o) == 7322 and int(low.sum()) == 430
    assert roc_auc_score(low, -p) == pytest.approx(0.865, abs=0.002)
    assert p[low].mean() == pytest.approx(0.66, abs=0.005) and p[~low].mean() == pytest.approx(0.947, abs=0.005)
    bottom = np.argsort(p, kind="stable")[:round(0.10 * len(p))]
    assert low[bottom].mean() == pytest.approx(0.388, abs=0.002) and low[bottom].sum() / low.sum() == pytest.approx(0.660, abs=0.003)


def test_the_decision_gate_numbers():
    gs = pb.gate_summary(pd.read_csv(D / "potential_gate_plans.csv")).set_index(["set", "variant"])
    assert (gs.plans_blocks_or_trees_changed == 0).all()                                                  # no plan places other blocks or trees, in any variant
    assert gs.loc[("barangay", "baseline"), "plans"] == 534 and gs.loc[("polygon", "baseline"), "plans"] == 893
    assert gs.loc[("barangay", "baseline"), "baseline_matches_saved"] == "534 of 534" and gs.loc[("polygon", "baseline"), "baseline_matches_saved"] == "893 of 893"
    t = gs.loc[("barangay", "tiebreak")]
    assert (t.squares_changed_total, t.blocks_total) == (5519, 10167) and abs(t.delta_W_pct) < 1e-3 and t.mean_dist_ratio == pytest.approx(1.666, abs=0.005)
    t = gs.loc[("polygon", "tiebreak")]
    assert (t.squares_changed_total, t.blocks_total) == (3698, 9247) and abs(t.delta_W_pct) < 1e-3 and t.mean_dist_ratio == pytest.approx(1.500, abs=0.005)
    for a, b_pct, p_pct in (("0.05", -0.0086, -0.0021), ("0.10", -0.0241, -0.0031), ("0.20", -0.0341, -0.0052)):
        assert gs.loc[("barangay", f"adjust_w_{a}"), "delta_W_pct"] == pytest.approx(b_pct, abs=0.0002)
        assert gs.loc[("polygon", f"adjust_w_{a}"), "delta_W_pct"] == pytest.approx(p_pct, abs=0.0002)
    assert gs.loc[("barangay", "adjust_w_0.20"), "delta_W_pct_worst_plan"] == pytest.approx(-1.524, abs=0.01)


def test_the_report_starts_with_the_registered_rules_and_states_the_verdict():
    txt = (D / "POTENTIAL_BENCHMARK.md").read_text(encoding="utf-8")
    head = txt.split("## Verdict on the drop rules")[0]
    assert "Pre-registration (written before the first run, 12 Oct 2026, and not changed)" in head
    for line in pb.DROP_TEXT:
        assert line in head
    assert "**DROP: at least one rule failed.**" in txt and "0.29999" in txt and "-0.221" in txt
    assert txt.index("## Pre-registration") < txt.index("## Verdict on the drop rules") < txt.index("## Settings")
