#!/usr/bin/env python3
"""
train_rf.py - rounds 19 and 19b: the Random Forest step of the hybrid "expert rules -> Random Forest -> Hungarian matching".

Round 19b: s_prob is now the out-of-fold prediction of a Random Forest REGRESSOR that learns the rule score S itself (0 to 1), so it keeps the gradation of the rules. The round 19
CLASSIFIER (yes/no, S >= 0.50) is still trained and reported; its out-of-fold probabilities are saved in scores/rf_classifier_oof.csv.gz and it is not used for s_prob.

    python pipeline/score_sites.py  --out data/processed        # 1. the expert rules: s_rule for every square x species pair
    python pipeline/make_pair_table.py --out data/processed     # 2. the pair table (raw features + the rule label S >= 0.50, NO label noise: noise 0 is used here)
    python pipeline/train_rf.py --out data/processed            # 3. this script: out-of-fold probabilities -> s_prob, and the final model file

What it does
  * Trains a Random Forest REGRESSOR (target: the rule score S, 0 to 1) and a Random Forest CLASSIFIER (target: S >= 0.50) on the pair table. Features: the raw site values (elevation, slope, distance to water, soil texture yes/no columns) and the raw species traits
    (elevation range, slope limit, waterlogging tolerance, accepted soil textures) = make_pair_table.feature_columns. Label: the expert rule (S >= 0.50). The zone is a hard
    gate of the rules, not a feature (it is applied again after the model, see below).
  * SPATIAL out-of-fold: the squares are cut into blocks of 10 x 10 grid cells (about 1 km); a block is never split between the training and the test part of a fold
    (GroupKFold, 5 folds, the same blocks and seed as compare_models.py). Every pair gets its probability from the model of the fold in which its block was the test part,
    so no pair is scored by a model that trained on its neighbourhood.
  * HARD GATES stay: where the rule says S == 0 (outside the zone, outside the elevation range, beyond the slope hard stop) s_prob is set to 0 and the pair stays rejected.
  * s_prob = the regressor's out-of-fold prediction, clipped to 0..1, then 0 where the rule S is 0. Writes s_prob (4 decimals) into scores/site_scores.csv and the table site_scores of scores/site_scores.db (s_rule and everything else are not touched).
  * Trains the final model on ALL pairs and saves it: <out>/models/rf_site_suitability.joblib (git-ignored) and rf_site_suitability_meta.json (training date, dataset hash,
    features, settings, out-of-fold accuracy).
  * Compares the Random Forest with a Decision Tree in the SAME out-of-fold procedure and writes <out>/rf_vs_dt_oof.csv.

HONESTY: the label comes from the expert rules, so the forest generalises those rules (it smooths the edges where the rules have steps); it is NOT an independent
measurement of survival. Re-running score_sites.py resets s_prob to empty: run this script again afterwards.
"""
import argparse, hashlib, json, re, sqlite3, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_models as cm  # noqa: E402  (the spatial blocks and folds are the ones of the model comparison)
import make_pair_table as mpt  # noqa: E402

RF_CFG = {
    "seed": 42,
    "n_estimators": 200,
    "max_depth": None,
    "min_samples_leaf": 5,          # one of the candidates the model comparison tuned over; it keeps the probabilities from being only 0 or 1
    "outer_folds": 5,
    "spatial_block_cells": 10,      # about 1 km blocks, as in compare_models.py
    "threshold": 0.5,
    "n_jobs": -1,
    "dt_max_depth": 16,             # the decision tree of the comparison (one of its tuning candidates)
}
REG_CFG = {                         # the regressor that makes s_prob (round 19b); chosen by out-of-fold MAE only
    "n_estimators": 200,
    "max_depth": None,
    "min_samples_leaf": 2,
    "dt_max_depth": None,           # the decision-tree regressor of the comparison: grown fully
}
MODEL_FILE = "rf_site_suitability.joblib"                    # the REGRESSOR (it makes s_prob)
CLASSIFIER_FILE = "rf_site_suitability_classifier.joblib"    # the round 19 yes/no classifier, kept
META_FILE = "rf_site_suitability_meta.json"
CLASSIFIER_OOF = "rf_classifier_oof.csv.gz"


def dataset_hash(out):
    f = Path(out) / "dataset_release.txt"
    m = re.search(r"combined hash \(12 characters\):\s*([0-9a-f]{12})", f.read_text(encoding="utf-8")) if f.is_file() else None
    return m.group(1) if m else None


def spatial_folds(table, y, cfg=None):
    """[(train_idx, test_idx)] with GroupKFold over the 1 km blocks (the same folds as the spatial setting of compare_models.py)."""
    c = {**cm.CFG, "outer_folds": (cfg or RF_CFG)["outer_folds"], "seed": (cfg or RF_CFG)["seed"], "spatial_block_cells": (cfg or RF_CFG)["spatial_block_cells"]}
    return cm.make_folds(table, y, "spatial", c)


def oof_probabilities(X, y, folds, make_model):
    """Out-of-fold P(label = 1) for every row: each row is predicted by the model of the fold where it was in the test part."""
    p = np.full(len(y), np.nan)
    for tr, te in folds:
        m = make_model()
        m.fit(X[tr], y[tr])
        p[te] = m.predict_proba(X[te])[:, 1]
    assert not np.isnan(p).any()
    return p


def oof_predictions(X, y, folds, make_model):
    """Out-of-fold predictions of a regressor (each row predicted by the model of the fold where it was in the test part)."""
    p = np.full(len(y), np.nan)
    for tr, te in folds:
        m = make_model()
        m.fit(X[tr], y[tr])
        p[te] = m.predict(X[te])
    assert not np.isnan(p).any()
    return p


def regression_row(name, y, p, folds, s_rule):
    """MAE, R-squared (all pairs, and only the pairs the rules allow), mean over folds, and the agreement of 'prediction >= 0.50' with the rule label."""
    from sklearn.metrics import mean_absolute_error, r2_score
    allow = s_rule > 0
    lab = y >= 0.5
    per = [(mean_absolute_error(y[te], p[te]), r2_score(y[te], p[te])) for _, te in folds]
    return {"model": name, "mae": round(mean_absolute_error(y, p), 5), "r2": round(r2_score(y, p), 5), "mae_fold_mean": round(float(np.mean([a for a, _ in per])), 5),
            "mae_fold_std": round(float(np.std([a for a, _ in per])), 5), "r2_fold_mean": round(float(np.mean([b for _, b in per])), 5), "r2_fold_std": round(float(np.std([b for _, b in per])), 5),
            "mae_allowed_pairs": round(mean_absolute_error(y[allow], p[allow]), 5), "r2_allowed_pairs": round(r2_score(y[allow], p[allow]), 5),
            "agree_with_rule_label_at_0.5": round(float(((p >= 0.5) == lab).mean()), 5), "n_pairs": len(y), "folds": len(folds)}


def apply_hard_gates(p, s_rule):
    """Where the expert rules say S == 0 the probability is 0: the hard gates are kept after the model."""
    return np.where(np.asarray(s_rule) <= 0.0, 0.0, p)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--reg-leaf", type=int, default=None, help=f"min_samples_leaf of the regressor ({REG_CFG['min_samples_leaf']})")
    ap.add_argument("--no-write", action="store_true", help="train and report only; do not touch site_scores or the model file")
    a = ap.parse_args(argv)
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
    from sklearn.metrics import accuracy_score, roc_auc_score, precision_score, recall_score, f1_score
    import joblib
    out = Path(a.out)
    c = RF_CFG
    t0 = time.time()
    table = pd.read_csv(out / "scores" / "pair_table.csv.gz")
    sc = pd.read_csv(out / "scores" / "site_scores.csv", usecols=["point_id", "species_id", "s_rule"])
    chk = table[["point_id", "species_id", "suitable_clean"]].merge(sc, on=["point_id", "species_id"], how="left", validate="1:1")
    if chk.s_rule.isna().any() or not np.array_equal((chk.s_rule >= c["threshold"]).astype(int).to_numpy(), chk.suitable_clean.to_numpy()):
        raise SystemExit("the pair table does not match scores/site_scores.csv (older rules or slope mode): run make_pair_table.py again, then this script")
    s_rule = chk.s_rule.to_numpy()
    y = table.suitable_clean.to_numpy().astype(int)                              # the clean rule label: no noise
    feats = mpt.feature_columns(table)
    X = table[feats].to_numpy(dtype=float)
    X = np.where(np.isnan(X), -1.0, X)                                          # a missing water distance or trait: a value outside every range (trees split on it; the rules never evaluate it)
    folds = spatial_folds(table, y)
    print(f"pairs: {len(y):,} | features: {len(feats)} | label S >= {c['threshold']} (positive {y.mean():.1%}) | spatial folds: {len(folds)} (blocks of {c['spatial_block_cells']} cells)")
    mk_rf = lambda: RandomForestClassifier(n_estimators=c["n_estimators"], max_depth=c["max_depth"], min_samples_leaf=c["min_samples_leaf"], random_state=c["seed"], n_jobs=c["n_jobs"])  # noqa: E731
    mk_dt = lambda: DecisionTreeClassifier(max_depth=c["dt_max_depth"], random_state=c["seed"])  # noqa: E731
    p_rf = oof_probabilities(X, y, folds, mk_rf)
    p_dt = oof_probabilities(X, y, folds, mk_dt)
    p_clf = apply_hard_gates(p_rf, s_rule)                                      # the round 19 classifier probability after the hard gates (kept, not used for s_prob)
    rc = dict(REG_CFG)
    if a.reg_leaf is not None:
        rc["min_samples_leaf"] = a.reg_leaf
    mk_rfr = lambda: RandomForestRegressor(n_estimators=rc["n_estimators"], max_depth=rc["max_depth"], min_samples_leaf=rc["min_samples_leaf"], random_state=c["seed"], n_jobs=c["n_jobs"])  # noqa: E731
    mk_dtr = lambda: DecisionTreeRegressor(max_depth=rc["dt_max_depth"], random_state=c["seed"])  # noqa: E731
    y_reg = s_rule.astype(float)                                                # the target of the regressor: the rule score S itself
    pr_rf = oof_predictions(X, y_reg, folds, mk_rfr)
    pr_dt = oof_predictions(X, y_reg, folds, mk_dtr)
    s_prob = apply_hard_gates(np.clip(pr_rf, 0.0, 1.0), s_rule)                 # s_prob = the regressor's out-of-fold prediction, clipped to 0..1; 0 where the rule S is 0
    reg = pd.DataFrame([regression_row("RandomForest regressor (raw out-of-fold, clipped)", y_reg, np.clip(pr_rf, 0, 1), folds, s_rule),
                        regression_row("RandomForest regressor (after the hard gates) = s_prob", y_reg, s_prob, folds, s_rule),
                        regression_row("DecisionTree regressor (clipped)", y_reg, np.clip(pr_dt, 0, 1), folds, s_rule)])
    print(reg.to_string(index=False))
    rows = []
    for name, p in (("RandomForest (raw out-of-fold)", p_rf), ("RandomForest (after the hard gates)", p_clf), ("DecisionTree", p_dt)):
        yh = (p >= c["threshold"]).astype(int)
        per_fold = [accuracy_score(y[te], yh[te]) for _, te in folds]
        rows.append({"model": name, "accuracy": round(accuracy_score(y, yh), 5), "accuracy_fold_mean": round(float(np.mean(per_fold)), 5), "accuracy_fold_std": round(float(np.std(per_fold)), 5),
                     "precision": round(precision_score(y, yh), 5), "recall": round(recall_score(y, yh), 5), "f1": round(f1_score(y, yh), 5), "roc_auc": round(roc_auc_score(y, p), 5),
                     "n_pairs": len(y), "folds": len(folds)})
    cmp_ = pd.DataFrame(rows)
    print(cmp_.to_string(index=False))
    print(f"fold sizes: {[len(te) for _, te in folds]}")
    if a.no_write:
        return cmp_, reg
    cmp_.to_csv(out / "rf_vs_dt_oof.csv", index=False)
    reg.to_csv(out / "rf_vs_dt_regression_oof.csv", index=False)
    pd.DataFrame({"point_id": table.point_id.to_numpy(), "species_id": table.species_id.to_numpy(), "p_classifier": np.round(p_clf, 4)}).to_csv(out / "scores" / CLASSIFIER_OOF, index=False, compression="gzip")
    # ---- s_prob into the saved scores (csv and db): only that column
    prob = pd.DataFrame({"point_id": table.point_id.to_numpy(), "species_id": table.species_id.to_numpy(), "s_prob": np.round(s_prob, 4)})
    full = pd.read_csv(out / "scores" / "site_scores.csv")
    full = full.drop(columns=["s_prob"]).merge(prob, on=["point_id", "species_id"], how="left", validate="1:1")
    assert full.s_prob.notna().all() and len(full) == len(prob)
    full = full[["point_id", "species_id", "s_rule", "s_prob", "breakdown_json", "confidence"]]
    full.to_csv(out / "scores" / "site_scores.csv", index=False)
    con = sqlite3.connect(out / "scores" / "site_scores.db")
    con.executemany("UPDATE site_scores SET s_prob=? WHERE point_id=? AND species_id=?", ((float(r.s_prob), int(r.point_id), int(r.species_id)) for r in prob.itertuples(index=False)))
    con.commit()
    n_db = con.execute("SELECT COUNT(*) FROM site_scores WHERE s_prob IS NOT NULL").fetchone()[0]
    con.close()
    # ---- the final model (all pairs) and what it was trained on
    final_reg = mk_rfr()
    final_reg.fit(X, y_reg)
    final_clf = mk_rf()
    final_clf.fit(X, y)
    (out / "models").mkdir(exist_ok=True)
    joblib.dump({"model": final_reg, "features": feats, "kind": "regressor (target: the rule score S)"}, out / "models" / MODEL_FILE, compress=3)
    joblib.dump({"model": final_clf, "features": feats, "kind": "classifier (target: S >= 0.50)"}, out / "models" / CLASSIFIER_FILE, compress=3)
    run = json.loads((out / "scores" / "score_run.json").read_text(encoding="utf-8")) if (out / "scores" / "score_run.json").is_file() else {}
    meta = {"trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "dataset_hash": dataset_hash(out), "slope_mode": run.get("slope_mode"),
            "s_prob_comes_from": "regressor", "target": "the expert rule score S (0 to 1)", "label": "expert rule S >= 0.50 (no label noise) for the classifier",
            "features": feats, "settings": {k: v for k, v in c.items()}, "regressor_settings": rc,
            "n_pairs": int(len(y)), "positive_share": round(float(y.mean()), 4),
            "regressor_oof_mae": reg.iloc[1]["mae"], "regressor_oof_r2": reg.iloc[1]["r2"], "regressor_oof_mae_decision_tree": reg.iloc[2]["mae"], "regressor_oof_r2_decision_tree": reg.iloc[2]["r2"],
            "oof_accuracy": rows[1]["accuracy"], "oof_accuracy_raw": rows[0]["accuracy"], "oof_accuracy_decision_tree": rows[2]["accuracy"], "classifier_file": CLASSIFIER_FILE,
            "site_scores_sha256_of_s_rule_pairs": hashlib.sha256(np.round(s_rule, 4).tobytes()).hexdigest()[:16],
            "model_file": MODEL_FILE, "note": "Trained on expert-rule scores: it generalises the rules; it is not an independent measurement of survival."}
    (out / "models" / META_FILE).write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"s_prob written for {len(prob):,} pairs (csv) and {n_db:,} rows (db); model saved to {out / 'models' / MODEL_FILE}; {time.time() - t0:.0f} s")
    return cmp_, reg


if __name__ == "__main__":
    main()
