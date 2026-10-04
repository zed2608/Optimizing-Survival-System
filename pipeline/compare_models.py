#!/usr/bin/env python3
"""
compare_models.py - Day 2 task 3b: RandomForest vs LogisticRegression, KNN, DecisionTree on the same rows and folds.

    python pipeline/make_pair_table.py --out data/processed
    python pipeline/compare_models.py --out data/processed

Reads  <out>/scores/pair_table.csv.gz (make_pair_table.py). Writes <out>/model_comparison.csv
(one row per model, setting, noise and metric: mean and standard deviation over the outer folds).

Design (all numbers in CFG below):
  * ONE shared stratified subsample of the pairs (CFG["subsample_n"]), drawn once and used by every model and every setting.
  * Three test settings, each with fixed folds computed ONCE and handed to every model:
      random   stratified 5-fold random split;
      spatial  GroupKFold on blocks of spatial_block_cells x spatial_block_cells grid cells (nearby points share a fold);
      species  GroupKFold on species_id: test species are never seen in training (leave-species-out, 5 folds).
  * Every model gets the SAME tuning budget: the same inner cross-validation splits (group-aware in the spatial / species
    settings) and the same number of grid candidates (checked by check_equal_budget).
  * RandomForest is reported twice: raw and with probability calibration (isotonic or Platt) fitted on out-of-fold
    predictions from the training fold only.
  * Label noise: the same random flips (same seed) at each rate in noise_levels, applied to the subsample. Folds are built from
    the CLEAN label so they are identical across noise levels. Train and test labels are both noisy.
Labels come from the s_rule rules, and the features are the raw inputs of those rules, so very high scores are expected.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import GridSearchCV, GroupKFold, StratifiedKFold, cross_val_predict, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_pair_table as mpt  # noqa: E402

# =====================================================================================================================
# CONFIG - every tunable number lives here (tests override copies of this dict).
# =====================================================================================================================
CFG = {
    "seed": 42,                       # every random choice: subsample, folds, noise flips, models
    "noise_levels": (0.0, 0.05),      # fraction of labels flipped; 0.0 = clean labels
    "subsample_n": 30000,             # shared stratified subsample size (None = all pairs)
    "outer_folds": 5,                 # test folds in every setting
    "inner_folds": 3,                 # inner cross-validation folds used for tuning (same for every model)
    "spatial_block_cells": 10,        # block edge in grid cells (~100 m each, so ~1 km blocks)
    "tune_scoring": "roc_auc",        # metric the inner cross-validation maximises
    "threshold": 0.5,                 # probability cut for accuracy / precision / recall / F1
    "rf_trees": 100,
    "lr_max_iter": 2000,
    "n_jobs": -1,
    "calibration": "isotonic",        # "isotonic" or "platt"
    "settings": ("random", "spatial", "species"),
    # 4 candidates per model = identical tuning budget (4 x inner_folds fits each)
    "grids": {
        "RandomForest": {"clf__max_depth": [12, None], "clf__min_samples_leaf": [1, 5]},
        "LogisticRegression": {"clf__C": [0.01, 0.1, 1.0, 10.0]},
        "KNN": {"clf__n_neighbors": [5, 15, 31, 61]},
        "DecisionTree": {"clf__max_depth": [4, 8, 16, None]},
    },
}
# =====================================================================================================================

MODELS = ["RandomForest", "LogisticRegression", "KNN", "DecisionTree"]
CAL_NAME = "RandomForest (calibrated)"
METRICS = ["accuracy", "precision", "recall", "f1", "roc_auc", "brier"]


def check_equal_budget(cfg):
    sizes = {m: int(np.prod([len(v) for v in cfg["grids"][m].values()])) for m in MODELS}
    if len(set(sizes.values())) != 1:
        raise ValueError(f"unequal tuning budget (candidates per model): {sizes}")
    return sizes[MODELS[0]]


def make_pipeline(name, cfg):
    s = cfg["seed"]
    clf = {"RandomForest": lambda: RandomForestClassifier(n_estimators=cfg["rf_trees"], random_state=s, n_jobs=cfg["n_jobs"]),
           "LogisticRegression": lambda: LogisticRegression(max_iter=cfg["lr_max_iter"], random_state=s),
           "KNN": lambda: KNeighborsClassifier(n_jobs=cfg["n_jobs"]),
           "DecisionTree": lambda: DecisionTreeClassifier(random_state=s)}[name]()
    steps = [("imp", SimpleImputer(strategy="median", add_indicator=True))]     # missing slope: median of the TRAIN fold
    if name in ("LogisticRegression", "KNN"):
        steps.append(("scale", StandardScaler()))
    return Pipeline(steps + [("clf", clf)])


def group_ids(table, setting, cfg):
    if setting == "species":
        return table.species_id.to_numpy()
    if setting == "spatial":
        b = cfg["spatial_block_cells"]
        return ((table.cell_row // b) * 10_000 + (table.cell_col // b)).to_numpy()
    return None


def make_folds(table, y_clean, setting, cfg):
    """The outer folds for one setting: a list of (train_idx, test_idx), computed once and shared by every model."""
    n, seed = cfg["outer_folds"], cfg["seed"]
    X = np.zeros(len(table))
    if setting == "random":
        return [(tr, te) for tr, te in StratifiedKFold(n, shuffle=True, random_state=seed).split(X, y_clean)]
    return [(tr, te) for tr, te in GroupKFold(n, shuffle=True, random_state=seed).split(X, y_clean, group_ids(table, setting, cfg))]


def inner_splits(setting, tr, y_clean, groups, cfg):
    """Inner CV splits (local indices into the training fold). Built once per fold and reused by every model."""
    k, seed = cfg["inner_folds"], cfg["seed"]
    X = np.zeros(len(tr))
    if setting == "random":
        return list(StratifiedKFold(k, shuffle=True, random_state=seed).split(X, y_clean[tr]))
    return list(GroupKFold(k, shuffle=True, random_state=seed).split(X, y_clean[tr], groups[tr]))


def fingerprint(idx):
    return hashlib.md5(np.sort(np.asarray(idx)).tobytes()).hexdigest()[:10]


def calibrator(p_oof, y_oof, method):
    if method == "isotonic":
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(p_oof, y_oof)
        return iso.predict
    if method == "platt":
        logit = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))[:, None]
        lr = LogisticRegression(C=1e6, max_iter=1000).fit(logit(p_oof), y_oof)
        return lambda p: lr.predict_proba(logit(p))[:, 1]
    raise ValueError(method)


def metrics(y, p, threshold):
    pred = (p >= threshold).astype(int)
    return {"accuracy": accuracy_score(y, pred), "precision": precision_score(y, pred, zero_division=0),
            "recall": recall_score(y, pred, zero_division=0), "f1": f1_score(y, pred, zero_division=0),
            "roc_auc": roc_auc_score(y, p) if len(np.unique(y)) == 2 else np.nan, "brier": brier_score_loss(y, p)}


def evaluate(X, y_noisy, y_clean, table, setting, noise, folds, cfg, verbose=False):
    """Fit and score every model (plus calibrated RF) on the given folds. Returns a per-fold DataFrame."""
    groups = group_ids(table, setting, cfg)
    rows = []
    for fi, (tr, te) in enumerate(folds):
        inner = inner_splits(setting, tr, y_clean, groups, cfg)          # identical inner CV for every model
        fp = fingerprint(te)
        for name in MODELS:
            t0 = time.time()
            gs = GridSearchCV(make_pipeline(name, cfg), cfg["grids"][name], cv=inner, scoring=cfg["tune_scoring"],
                              refit=True, n_jobs=1, error_score=np.nan)
            gs.fit(X[tr], y_noisy[tr])
            p = gs.predict_proba(X[te])[:, 1]
            rows.append({"model": name, "setting": setting, "noise": noise, "fold": fi, "test_fingerprint": fp,
                         "best_params": json.dumps(gs.best_params_, default=str), "n_train": len(tr), "n_test": len(te),
                         **metrics(y_noisy[te], p, cfg["threshold"])})
            if name == "RandomForest":
                oof = cross_val_predict(clone(gs.best_estimator_), X[tr], y_noisy[tr], cv=inner, method="predict_proba",
                                        n_jobs=1)[:, 1]
                pc = np.clip(calibrator(oof, y_noisy[tr], cfg["calibration"])(p), 0.0, 1.0)
                rows.append({"model": CAL_NAME, "setting": setting, "noise": noise, "fold": fi, "test_fingerprint": fp,
                             "best_params": rows[-1]["best_params"], "n_train": len(tr), "n_test": len(te),
                             **metrics(y_noisy[te], pc, cfg["threshold"])})
            if verbose:
                print(f"  noise {noise} {setting} fold {fi + 1}/{len(folds)} {name}: auc {rows[-1]['roc_auc']:.3f} "
                      f"({time.time() - t0:.1f}s)", flush=True)
    return pd.DataFrame(rows)


def run_comparison(table, cfg=None, verbose=False):
    """Returns (summary, per_fold). summary: model, setting, noise, metric, mean, std (sample std over folds), n_folds, n_rows."""
    cfg = CFG if cfg is None else cfg
    check_equal_budget(cfg)
    feats = mpt.feature_columns(table)
    n = cfg["subsample_n"]
    if n is not None and n < len(table):
        idx, _ = train_test_split(np.arange(len(table)), train_size=n, stratify=table.suitable_clean, random_state=cfg["seed"])
        table = table.iloc[np.sort(idx)]
    table = table.reset_index(drop=True)
    X = table[feats].to_numpy(dtype=float)
    y_clean = table.suitable_clean.to_numpy().astype(int)
    all_folds = {s: make_folds(table, y_clean, s, cfg) for s in cfg["settings"]}      # once; shared by models AND noise levels
    parts = []
    for noise in cfg["noise_levels"]:
        y_noisy, _ = mpt.apply_noise(y_clean, noise, cfg["seed"])
        for setting in cfg["settings"]:
            parts.append(evaluate(X, y_noisy, y_clean, table, setting, noise, all_folds[setting], cfg, verbose))
    per_fold = pd.concat(parts, ignore_index=True)
    long = per_fold.melt(id_vars=["model", "setting", "noise", "fold"], value_vars=METRICS, var_name="metric", value_name="v")
    g = long.groupby(["model", "setting", "noise", "metric"], sort=False).v
    summary = pd.DataFrame({"mean": g.mean(), "std": g.std(ddof=1), "n_folds": g.count()}).reset_index()
    summary["n_rows"] = len(table)
    order = {m: i for i, m in enumerate(METRICS)}
    mo = {m: i for i, m in enumerate(MODELS + [CAL_NAME])}
    summary = summary.sort_values(["setting", "noise", "model", "metric"],
                                  key=lambda s: s.map(mo) if s.name == "model" else s.map(order) if s.name == "metric" else s)
    summary[["mean", "std"]] = summary[["mean", "std"]].round(4)
    return summary.reset_index(drop=True), per_fold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/processed")
    a = ap.parse_args()
    out = Path(a.out)
    table = pd.read_csv(out / mpt.TABLE_FILE)
    t0 = time.time()
    summary, per_fold = run_comparison(table, CFG, verbose=True)
    summary.to_csv(out / "model_comparison.csv", index=False)
    print(f"\npairs in table: {len(table)} | shared subsample: {summary.n_rows.iloc[0]} | {time.time() - t0:.0f}s")
    wide = summary.pivot_table(index=["setting", "noise", "model"], columns="metric", values="mean", sort=False)[METRICS]
    print(wide.round(3).to_string())
    print(f"written to {out / 'model_comparison.csv'}")


if __name__ == "__main__":
    main()
