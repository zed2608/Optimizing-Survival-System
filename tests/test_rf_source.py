"""Rounds 19, 19b and 19c: the Random Forest (since 19b a REGRESSOR that learns the rule score S) as the source of S (S_SOURCE "rf" | "rules"). Since 19c the DEFAULT is "rf";
"rules" stays available (OS_S_SOURCE / API_CFG) and is the automatic fallback when s_prob is missing. The other test files are pinned to "rules" by tests/conftest.py (their numbers are the rules').
Run from the repo root: python -m pytest tests/test_rf_source.py"""
import json, os, re, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BLOCKS_DEFAULT = True
ROOT = Path(__file__).resolve().parents[1]
PROCESSED = Path(os.environ.get("OS_DATA_DIR") or ROOT / "data" / "processed")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))
import matching as mt  # noqa: E402
import run_plan as rp  # noqa: E402
import train_rf as trf  # noqa: E402
import field_verify as fv  # noqa: E402

RULES_ELIGIBLE = 257_869            # eligible pairs (S >= 0.50), graded slope mode, 8,010 squares x 45 species
RF_ELIGIBLE = 257_929
RULES_ONLY, RF_ONLY = 54, 114       # pairs eligible by only one of the two sources (168 changed)
needs = pytest.mark.skipif(not (PROCESSED / "scores" / "site_scores.csv").exists(), reason="run the pipeline first")


@pytest.fixture(scope="module")
def ctxs():
    return rp.load_context(PROCESSED, include_unzoned=True, s_source="rules"), rp.load_context(PROCESSED, include_unzoned=True, s_source="rf")


# ---- the default is "rf" since round 19c; "rules" stays available ----------------------------------------------------------------------------------
def test_the_default_source_is_rf_and_rules_stays_available(monkeypatch):
    monkeypatch.delenv("OS_S_SOURCE", raising=False)
    assert mt.S_SOURCE == "rf" and mt.resolve_s_source() == "rf" and mt.S_COLUMN == {"rules": "s_rule", "rf": "s_prob"}
    with pytest.raises(ValueError):
        mt.resolve_s_source("forest")
    monkeypatch.setenv("OS_S_SOURCE", "rules")
    assert mt.resolve_s_source() == "rules" and mt.resolve_s_source("rf") == "rf"       # the environment variable switches without editing code; an explicit argument wins


@needs
def test_with_rules_explicitly_the_eligible_pairs_are_the_257869(ctxs):
    rules, _ = ctxs                                                                  # explicit s_source="rules"
    assert rules.s_source == "rules" and rules.s_requested == "rules" and rules.s_warning == ""
    W, feas = mt.weights(rules.S, rules.P["urban"])
    assert int(feas.sum()) == RULES_ELIGIBLE == 257_869
    sc = pd.read_csv(PROCESSED / "scores" / "site_scores.csv", usecols=["s_rule"])
    assert int((sc.s_rule >= 0.5).sum()) == RULES_ELIGIBLE                           # the rule column itself was not touched by the forest step
    assert rules.S.shape == (8010, 45)


@needs
def test_without_any_setting_the_context_uses_the_forest(monkeypatch):
    monkeypatch.delenv("OS_S_SOURCE", raising=False)
    default = rp.load_context(PROCESSED, include_unzoned=True)                      # no source given, no environment variable: the default
    assert default.s_source == "rf" and default.s_requested == "rf" and default.s_warning == ""
    assert int((default.S >= 0.5).sum()) == RF_ELIGIBLE == 257_929


def small_scores(tmp_path, mutate):
    """A copy of the saved scores with only the columns the loader reads (small), after mutate(df)."""
    df = pd.read_csv(PROCESSED / "scores" / "site_scores.csv", usecols=["point_id", "species_id", "s_rule", "s_prob"])
    df = mutate(df)
    f = tmp_path / "site_scores.csv"
    df.to_csv(f, index=False)
    return f


@needs
@pytest.mark.parametrize("case", ["empty column", "no column", "one gap"])
def test_the_app_falls_back_to_rules_with_a_warning_when_s_prob_is_missing(tmp_path, monkeypatch, ctxs, case):
    monkeypatch.delenv("OS_S_SOURCE", raising=False)
    rules, _ = ctxs

    def mutate(df):
        if case == "empty column":
            df["s_prob"] = np.nan
        elif case == "no column":
            df = df.drop(columns=["s_prob"])
        else:
            df.loc[len(df) // 2, "s_prob"] = np.nan
        return df

    f = small_scores(tmp_path, mutate)
    ctx = mt.load_context(PROCESSED, scores_path=f)                                  # the default source, "rf", was asked for
    assert ctx.s_requested == "rf" and ctx.s_source == "rules"
    assert "expert rules" in ctx.s_warning and "rebuild_scores.py" in ctx.s_warning
    assert not np.isnan(ctx.S).any() and np.array_equal(ctx.S, mt.load_context(PROCESSED, s_source="rules").S[:, :])   # the rules, never empty values used as zeros
    assert int((ctx.S >= 0.5).sum()) > 200_000


@needs
def test_the_fallback_also_covers_squares_outside_the_zoning_map(tmp_path, monkeypatch):
    monkeypatch.delenv("OS_S_SOURCE", raising=False)
    sites = pd.read_csv(PROCESSED / "site_points_clean.csv", usecols=["point_id", "zoning_status"])
    unconf = set(sites[sites.zoning_status == "unconfirmed"].point_id)

    def mutate(df):
        df.loc[df.point_id.isin(unconf), "s_prob"] = np.nan                          # the forest prediction exists for the confirmed squares only
        return df

    ctx = rp.load_context(PROCESSED, scores_path=small_scores(tmp_path, mutate), include_unzoned=True)
    assert ctx.s_source == "rules" and ctx.s_requested == "rf" and ctx.s_warning and not np.isnan(ctx.S).any() and ctx.S.shape == (8010, 45)


@needs
def test_rejected_pairs_stay_rejected_in_the_default_rf_mode(monkeypatch):
    monkeypatch.delenv("OS_S_SOURCE", raising=False)
    default = rp.load_context(PROCESSED, include_unzoned=True)
    rules = rp.load_context(PROCESSED, include_unzoned=True, s_source="rules")
    assert default.s_source == "rf"
    assert bool((default.S[rules.S == 0] == 0).all())                                # outside the zone, outside the elevation range, beyond the slope hard stop: s_prob 0
    W, feas = mt.weights(default.S, default.P["watershed"])
    assert not feas[rules.S == 0].any() and not (W[rules.S == 0] > 0).any()          # and no weight in the matching


# ---- s_prob ----------------------------------------------------------------------------------------------------------------------------------------
@needs
def test_s_prob_is_filled_in_range_and_the_hard_gates_stay():
    sc = pd.read_csv(PROCESSED / "scores" / "site_scores.csv", usecols=["point_id", "species_id", "s_rule", "s_prob"])
    assert sc.s_prob.notna().all() and len(sc) == 360_450
    assert sc.s_prob.between(0, 1).all()
    assert (sc.s_prob[sc.s_rule == 0] == 0).all()                                    # where the rule says S == 0 (zone, elevation, beyond the slope hard stop) s_prob is 0
    assert ((sc.s_prob >= 0.5) & (sc.s_rule == 0)).sum() == 0
    assert (sc.s_prob[(sc.s_rule > 0)] > 0).mean() > 0.9                             # and the forest does give a probability to the squares the rules allow
    import sqlite3
    con = sqlite3.connect(PROCESSED / "scores" / "site_scores.db")
    assert con.execute("SELECT COUNT(*) FROM site_scores WHERE s_prob IS NULL").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM site_scores WHERE s_rule = 0 AND s_prob > 0").fetchone()[0] == 0
    con.close()


@needs
def test_with_rf_the_forest_probability_replaces_s_everywhere_s_is_used(ctxs):
    rules, rf = ctxs
    assert rf.s_source == "rf" and rf.S.shape == rules.S.shape
    sc = pd.read_csv(PROCESSED / "scores" / "site_scores.csv", usecols=["point_id", "species_id", "s_prob"])
    piv = sc.pivot(index="point_id", columns="species_id", values="s_prob").reindex(index=rf.sites.point_id, columns=rf.species.species_id)
    assert np.array_equal(rf.S, piv.to_numpy(dtype=float))
    for purpose in ("urban", "planting", "watershed"):                              # mt.weights: the 0.50 test and W use the probability
        W, feas = mt.weights(rf.S, rf.P[purpose])
        assert int(feas.sum()) == RF_ELIGIBLE and np.array_equal(feas, rf.S >= 0.5)
        assert np.allclose(W[feas], (rf.S * rf.P[purpose][None, :])[feas])
    assert bool((rf.S[rules.S == 0] == 0).all())                                     # the hard gates stay rejected
    er, ef = rules.S >= 0.5, rf.S >= 0.5
    assert int((er & ~ef).sum()) == RULES_ONLY and int((~er & ef).sum()) == RF_ONLY and int((er != ef).sum()) == 168


# ---- spatial out-of-fold ---------------------------------------------------------------------------------------------------------------------
@needs
def test_spatial_folds_never_split_a_one_kilometre_block():
    t = pd.read_csv(PROCESSED / "scores" / "pair_table.csv.gz", usecols=["point_id", "species_id", "cell_row", "cell_col", "suitable_clean"])
    y = t.suitable_clean.to_numpy()
    folds = trf.spatial_folds(t, y)
    assert len(folds) == 5
    b = trf.RF_CFG["spatial_block_cells"]
    block = ((t.cell_row // b) * 10_000 + (t.cell_col // b)).to_numpy()
    seen = np.zeros(len(t), dtype=int)
    for tr, te in folds:
        assert not (set(block[tr]) & set(block[te]))                                 # no block is in the training part and the test part of one fold
        assert not (set(tr) & set(te))
        seen[te] += 1
    assert (seen == 1).all()                                                         # every pair is scored out-of-fold exactly once


def test_hard_gates_function_and_oof_use_only_models_that_did_not_train_on_the_row():
    p = np.array([0.9, 0.8, 0.2, 0.7])
    s = np.array([1.0, 0.0, 0.0, 0.6])
    assert list(trf.apply_hard_gates(p, s)) == [0.9, 0.0, 0.0, 0.7]

    class Memoriser:                                                                  # predicts 1 only for rows it saw in training: an out-of-fold row must come out 0
        def fit(self, X, y):
            self.seen = {float(x[0]) for x in X}
            return self

        def predict_proba(self, X):
            q = np.array([1.0 if float(x[0]) in self.seen else 0.0 for x in X])
            return np.column_stack([1 - q, q])

    X = np.arange(20, dtype=float)[:, None]
    y = np.ones(20, dtype=int)
    folds = [(np.arange(10, 20), np.arange(0, 10)), (np.arange(0, 10), np.arange(10, 20))]
    assert (trf.oof_probabilities(X, y, folds, Memoriser) == 0).all()


@needs
def test_the_model_file_and_its_meta_record_the_training_date_and_the_dataset_hash():
    meta = json.loads((PROCESSED / "models" / trf.META_FILE).read_text(encoding="utf-8"))
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", meta["trained_at"]) and meta["dataset_hash"] == "34964a09fe44"
    assert meta["slope_mode"] == "graded" and len(meta["features"]) == 20 and meta["n_pairs"] == 360_450
    assert "not an independent measurement of survival" in meta["note"] and "no label noise" in meta["label"]
    assert meta["s_prob_comes_from"] == "regressor" and "rule score S" in meta["target"]
    assert meta["oof_accuracy"] > 0.999 and meta["regressor_oof_mae"] < 0.002 and meta["regressor_oof_r2"] > 0.999
    import joblib
    m = joblib.load(PROCESSED / "models" / trf.MODEL_FILE)
    assert m["features"] == meta["features"] and hasattr(m["model"], "predict") and not hasattr(m["model"], "predict_proba") and "regressor" in m["kind"]
    c = joblib.load(PROCESSED / "models" / trf.CLASSIFIER_FILE)                       # the round 19 classifier is kept
    assert hasattr(c["model"], "predict_proba") and "classifier" in c["kind"]
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/processed/models/" in gi                                           # a model file is never committed


@needs
def test_rf_versus_decision_tree_out_of_fold_accuracy_is_recorded():
    t = pd.read_csv(PROCESSED / "rf_vs_dt_oof.csv").set_index("model")
    assert {"RandomForest (raw out-of-fold)", "RandomForest (after the hard gates)", "DecisionTree"} <= set(t.index)
    assert t.loc["DecisionTree", "accuracy"] > 0.998 and t.loc["RandomForest (raw out-of-fold)", "accuracy"] > 0.998


# ---- the app ----------------------------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client_rf():
    import api_v2
    from fastapi.testclient import TestClient
    old = api_v2.API_CFG.get("s_source")
    api_v2.API_CFG["s_source"] = "rf"
    try:
        with TestClient(api_v2.app) as c:
            yield c
    finally:
        api_v2.API_CFG["s_source"] = old


def _client(source, drop_env):
    import api_v2
    from fastapi.testclient import TestClient
    old, old_env = api_v2.API_CFG.get("s_source"), os.environ.get("OS_S_SOURCE")
    api_v2.API_CFG["s_source"] = source
    if drop_env:
        os.environ.pop("OS_S_SOURCE", None)                                          # tests/conftest.py pins the other suites to "rules"; the default test must not
    try:
        with TestClient(api_v2.app) as c:
            yield c
    finally:
        api_v2.API_CFG["s_source"] = old
        if old_env is not None:
            os.environ["OS_S_SOURCE"] = old_env


@pytest.fixture(scope="module")
def client_default():
    yield from _client(None, True)


@pytest.fixture(scope="module")
def client_rules():
    yield from _client("rules", False)


def isolate(client, tmp_path, monkeypatch):
    import api_v2
    d = client.app.state.data
    monkeypatch.setattr(d, "field_db", tmp_path / "field" / "f.db")
    monkeypatch.setattr(d, "work", tmp_path)
    fv.connect(d.field_db).close()
    api_v2.refresh_field(d)
    return d


@needs
def test_the_app_default_is_rf_and_health_says_so(client_default, tmp_path, monkeypatch):
    d = isolate(client_default, tmp_path, monkeypatch)
    h = client_default.get("/health").json()
    assert h["s_source"] == "rf" and h["s_source_requested"] == "rf" and h["s_source_warning"] is None
    assert h["rf_model"]["dataset_hash"] == "34964a09fe44" and h["rf_model"]["trained_at"]
    sites = d.ctx.sites
    row = sites[sites.zone_desc == "Forest Zone"].iloc[10]
    j = client_default.get("/rank", params={"purpose": "urban", "lat": float(row.lat), "lon": float(row.lon), "limit": 45}).json()
    assert any("rf" in it for it in j["ranking"]) and "Suitability from the Random Forest" in j["ranking"][0]["rf"]["text"]
    # rejected pairs stay rejected through the API
    rej = [it for it in j["ranking"] if it["site_breakdown"]["gate_failed"]]
    assert all(it["S"] == 0 and not it["eligible"] and it["rf"]["rules_check"] == "failed" and it["rf"]["s_prob"] == 0 for it in rej)


@needs
def test_with_rules_the_app_shows_no_forest_line_and_health_says_rules(client_rules, tmp_path, monkeypatch):
    d = isolate(client_rules, tmp_path, monkeypatch)
    h = client_rules.get("/health").json()
    assert h["s_source"] == "rules" and h["s_source_requested"] == "rules" and h["s_source_warning"] is None
    sites = d.ctx.sites
    row = sites[sites.zone_desc == "Forest Zone"].iloc[10]
    j = client_rules.get("/rank", params={"purpose": "urban", "lat": float(row.lat), "lon": float(row.lon), "limit": 45}).json()
    assert all("rf" not in it for it in j["ranking"])                                 # no Random Forest line with the rules


@needs
def test_health_shows_the_fallback_warning(client_default, tmp_path, monkeypatch):
    import dataclasses
    d = isolate(client_default, tmp_path, monkeypatch)
    monkeypatch.setattr(d, "ctx", dataclasses.replace(d.ctx, s_source="rules", s_requested="rf", s_warning=mt.FALLBACK_WARNING))
    h = client_default.get("/health").json()
    assert h["s_source"] == "rules" and h["s_source_requested"] == "rf" and "no complete Random Forest prediction" in h["s_source_warning"] and "rebuild_scores.py" in h["s_source_warning"]


@needs
def test_with_rf_the_app_shows_the_forest_line_and_uses_s_prob(client_rf, tmp_path, monkeypatch):
    d = isolate(client_rf, tmp_path, monkeypatch)
    assert client_rf.get("/health").json()["s_source"] == "rf"
    sites = d.ctx.sites
    row = sites[sites.zone_desc == "Forest Zone"].iloc[10]
    j = client_rf.get("/rank", params={"purpose": "urban", "lat": float(row.lat), "lon": float(row.lon), "limit": 45}).json()
    elig = [it for it in j["ranking"] if it["eligible"]]
    assert elig and all(it["S"] >= 0.5 for it in elig)
    it = elig[0]
    assert re.fullmatch(r"Suitability from the Random Forest: \d\.\d\d\. Rules check: passed\.", it["rf"]["text"]), it["rf"]
    assert it["rf"]["s_prob"] == pytest.approx(it["S"], abs=1e-4) and it["rf"]["rules_check"] == "passed" and "not an independent measurement" in it["rf"]["note"]
    failed = [x for x in j["ranking"] if not x["eligible"] and x["rf"]["rules_check"] == "failed"]
    assert all(x["rf"]["s_prob"] == 0 and x["S"] == 0 for x in failed)               # a rejected pair: probability 0, "Rules check: failed"
    assert all("_" not in x["rf"]["text"] and "=" not in x["rf"]["text"] for x in j["ranking"])
    # a grid and a plan work in this mode too
    g = client_rf.get("/grid", params={"purpose": "urban", "include_unzoned": "true"})
    assert g.status_code == 200
    r = client_rf.post("/plan-event", json={"purpose": "urban", "n_saplings": 60, "barangay": "Santa Ana", "campaign": {"name": "RF mode", "unit": ""}})
    assert r.status_code == 200 and all(x["S"] >= 0.5 for x in r.json()["plan"])


# ---- screens and words -------------------------------------------------------------------------------------------------------------------------
def test_the_why_this_score_panel_shows_the_forest_line_only_from_the_api_block():
    src = (ROOT / "frontend" / "src" / "new" / "RowDetails.jsx").read_text(encoding="utf-8")
    assert "item.rf &&" in src and "item.rf.text" in src and "nw-rfline" in src


def test_the_docs_describe_the_forest_honestly():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "S_SOURCE" in readme and "not an independent measurement of survival" in readme
    doc = (ROOT / "docs" / "RF_SOURCE.md").read_text(encoding="utf-8")
    assert "trained on expert-rule scores" in doc.lower().replace("*", "") and "not an independent measurement of survival" in doc.lower().replace("*", "") and "default" in doc.lower() and "rules" in doc


# ---- round 19b: the regressor learns the graded score -----------------------------------------------------------------------------------------------
@needs
def test_s_prob_is_graded_not_yes_no_and_follows_the_rule_score():
    from scipy.stats import spearmanr
    sc = pd.read_csv(PROCESSED / "scores" / "site_scores.csv", usecols=["s_rule", "s_prob"])
    assert sc.s_prob.nunique() > 1000                                                # a graded score, not only 0 and 1
    elig = sc.s_rule >= 0.5
    assert spearmanr(sc.s_rule[elig], sc.s_prob[elig]).statistic > 0.99              # it keeps the order of the rules among the eligible pairs
    assert float((sc.s_rule - sc.s_prob).abs()[sc.s_rule > 0].mean()) < 0.005
    assert (sc.s_prob.between(0, 1)).all() and (sc.s_prob[sc.s_rule == 0] == 0).all()


@needs
def test_regressor_error_is_recorded_against_a_decision_tree_regressor_on_the_same_folds():
    t = pd.read_csv(PROCESSED / "rf_vs_dt_regression_oof.csv").set_index("model")
    rf = t.loc["RandomForest regressor (after the hard gates) = s_prob"]
    dt = t.loc["DecisionTree regressor (clipped)"]
    assert rf.mae < 0.002 and rf.r2 > 0.999 and dt.mae < 0.002 and dt.r2 > 0.999
    assert rf.folds == dt.folds == 5 and rf.n_pairs == dt.n_pairs == 360_450
    assert abs(rf.mae - dt.mae) < 3 * max(rf.mae_fold_std, dt.mae_fold_std)          # equal within the spread between folds: the forest is not clearly better than one tree


@needs
@pytest.mark.parametrize("purpose,layout", [("urban", "blocks"), ("planting", "points")])
def test_success_test_the_forests_plan_judged_by_the_rules_loses_less_than_two_percent(ctxs, purpose, layout):
    rules, rf = ctxs
    plan_r, _ = rp.make_plan(rules, purpose, rp.CFG["bench_saplings"], seed=rp.CFG["seed"], method="hungarian", layout_mode=layout)
    plan_f, _ = rp.make_plan(rf, purpose, rp.CFG["bench_saplings"], seed=rp.CFG["seed"], method="hungarian", layout_mode=layout)
    Wr, _x = mt.weights(rules.S, rules.P[purpose])
    pid = {int(p): i for i, p in enumerate(rules.sites.point_id)}
    sid = {int(s_): k for k, s_ in enumerate(rules.species.species_id)}
    tot = lambda plan: sum(Wr[pid[int(p)], sid[int(s_)]] for p, s_ in zip(plan.point_id, plan.species_id))  # noqa: E731
    assert (tot(plan_r) - tot(plan_f)) / tot(plan_r) < 0.02
    assert (plan_f.S >= 0.5).all()                                                   # every square the forest chose is eligible (S = s_prob >= 0.50)


# ---- round 19c: the rebuild script, the words ---------------------------------------------------------------------------------------------------
def test_the_rebuild_script_runs_the_three_steps_in_the_right_order_and_the_readme_says_so():
    sys.path.insert(0, str(ROOT / "scripts"))
    import rebuild_scores as rb
    names = [Path(cmd[1]).name for _t, cmd in rb.commands("data/processed")]
    assert names == ["score_sites.py", "make_pair_table.py", "train_rf.py"]
    assert rb.commands("x", "hard")[0][1][-2:] == ["--slope-mode", "hard"]
    assert [t for t, _c in rb.main(["--dry-run"])][0].startswith("1.")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "scripts/rebuild_scores.py" in readme and "score_sites.py -> make_pair_table.py -> train_rf.py" in readme


def test_the_help_and_the_guide_carry_the_random_forest_sentence():
    sentence = "Site suitability is predicted by a Random Forest trained on the expert rules. Hard limits (zone, elevation, steep slope) always apply first."
    assert sentence in (ROOT / "frontend" / "src" / "new" / "tutorial" / "tutorialContent.js").read_text(encoding="utf-8")
    assert sentence in (ROOT / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")


def test_the_scores_and_the_model_folders_are_not_tracked_in_git():
    import subprocess
    r = subprocess.run(["git", "ls-files", "data/processed/scores", "data/processed/models"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == ""                               # a fresh clone has no s_prob: scripts/rebuild_scores.py builds it
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/processed/scores/" in gi and "data/processed/models/" in gi
