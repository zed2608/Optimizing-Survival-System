#!/usr/bin/env python3
"""Task 2, steps 1 to 3: is a satellite-derived "environmental support for woody cover" layer worth building? (comparison, drop rules, decision gate). NO production code.

    python scripts/potential_benchmark.py        # about 10 minutes; writes docs/defense/POTENTIAL_BENCHMARK.md and three CSVs

Step 1/2: a model of the observed tree cover share (ESA WorldCover 2021, `share_tree` of data/processed/site_landcover.csv) from the ENVIRONMENT only (elevation, slope, LGU soil texture),
out of fold on the same 1 km spatial blocks as the other model comparisons, for a Random Forest, a Decision Tree, linear regression and KNN (plus a mean-only baseline).
Step 3 (decision gate): what would the layer change in the benchmark plans? Uses the Hungarian matching of the benchmark (barangay plans and drawn-polygon plans, S source rf), with the potential
as (a) a tie-break and (b) a mild multiplier of W (adjust_w), offline and read-only. Nothing is switched on in the app.

The potential is the model's PREDICTION from the environment, never the observed tree cover, and it never penalises open land by its observed cover (decision of 12 Oct 2026).
Squares without a potential stay neutral. The drop rules below were written BEFORE the first run and are copied unchanged into the first lines of the report.
"""
import dataclasses, json, subprocess, sys, time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "pipeline"))
import compare_models as cm  # noqa: E402  (the spatial blocks and folds of the model comparison)
import matching as mt  # noqa: E402
import scarcity_benchmark as sb  # noqa: E402
import scarcity_benchmark_polygons as sbp  # noqa: E402  (sets OS_FIELD_DB to a temporary file before api_v2 is imported)
from scipy.stats import spearmanr  # noqa: E402
from sklearn.dummy import DummyRegressor  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.linear_model import LinearRegression  # noqa: E402
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, roc_auc_score  # noqa: E402
from sklearn.model_selection import GridSearchCV, GroupKFold  # noqa: E402
from sklearn.neighbors import KNeighborsRegressor  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.tree import DecisionTreeRegressor  # noqa: E402

OUT_DIR = ROOT / "docs" / "defense"

# =====================================================================================================================
# PRE-REGISTRATION: WRITTEN BEFORE THE FIRST RUN (12 Oct 2026). Do not change after seeing results; a change means a new, labelled run.
# =====================================================================================================================
DROP = {
    "R1_margin": 0.10,        # the forest's mean R2 must be at least this much above EACH of Decision Tree, linear regression and KNN ...
    "R1_folds": 4,            # ... and the forest must be better than each of them in at least this many of the 5 folds (same folds)
    "R2_min_r2": 0.30,        # the forest's mean R2 of the MAIN model (no latitude / longitude, no nearest_feature_dist_m) must be at least this
    "R3_max_corr": 0.80,      # |Spearman| between the forest's out-of-fold potential and the mean rule score s_rule of the square over the 45 species must be at most this
}
DROP_TEXT = [
    f"R1  The Random Forest is clearly better than each of the Decision Tree, linear regression and KNN: its mean R-squared is at least {DROP['R1_margin']:.2f} above EACH of them and it is better than each of them in at least {DROP['R1_folds']} of the 5 folds (same folds for all models).",
    f"R2  The forest's mean R-squared of the MAIN model (environment only: elevation, slope, soil; no latitude / longitude, no nearest_feature_dist_m) is at least {DROP['R2_min_r2']:.2f}.",
    f"R3  The absolute Spearman correlation between the forest's out-of-fold potential and the mean rule score s_rule of the square (mean over the 45 species) is at most {DROP['R3_max_corr']:.2f}.",
    "RULE  If any of R1, R2, R3 fails, the idea is DROPPED (said plainly in the verdict). The ranking check on the 430 low-tree squares, all sensitivities and the decision-gate analysis are descriptive: they are NOT drop rules.",
]
SET = {
    "seed": 42, "outer_folds": 5, "inner_folds": 3, "block_cells": 10, "block_cells_sensitivity": 20,
    "target": "share_tree (ESA WorldCover 2021, data/processed/site_landcover.csv)",
    "squares": "scored squares (confirmed + outside the zoning map) with lc_coverage >= 0.5 and share_built < 0.2; the 2 squares without a slope value are left out of training (never filled in); all other squares get NO potential and stay neutral",
    "features_main": "elev_m, slope_pct, LGU soil texture (one-hot: Clay, Clay Loam, Loam, Sandy Loam, Silt Loam, plus an indicator 'no soil texture')",
    "variants": "main = the features above | nf = main + nearest_feature_dist_m | latlon = main + longitude + latitude | nosoil = elevation and slope only | blk20 = main, blocks of 20 x 20 cells (about 2 km)",
    "models": "RandomForest (200 trees; tuned: max_depth {12, None} x min_samples_leaf {1, 5}), DecisionTree (tuned: max_depth {4, 8, 16, None}), KNN (standardised; tuned: k {5, 15, 31, 61}), linear regression (standardised, no tuning), mean-only baseline; same 3-fold spatial inner tuning for the tuned ones",
    "folds": "GroupKFold(5, shuffle, seed 42) over blocks of 10 x 10 grid cells, built by compare_models.make_folds (the same block definition and seed as the other model comparisons; the fold assignment differs because the table has one row per square, not per pair)",
    "metrics": "R-squared, MAE, RMSE per fold; mean and standard deviation (n - 1) over the 5 folds",
    "low_tree": "squares with share_tree < 0.5: ranking check (AUROC; precision and recall among the 10% and 20% of squares with the lowest predicted potential), descriptive only",
    "adjust_w_factors": (0.05, 0.10, 0.20),
    "adjust_w_form": "W' = W x (1 - a x (1 - potential)); potential clipped to 0..1; no potential -> factor 1; S and the S >= 0.50 test are untouched",
    "tiebreak_form": "matching cost + 1e-6 x ((1 - potential) + 0.001 x distance to the area centre); no potential -> the area's median potential (neutral); the same 1e-6 weight as the existing distance tie-break (not tuned)",
    "gate_plans": "the plans of scarcity_benchmark.py (blocks layout, species_counts, rf source, 15 barangays) and scarcity_benchmark_polygons.py (100 drawn polygons), same seeds; Hungarian matching",
}
S_MIN = mt.CFG["s_min"]
TIE_EPS = mt.TIEBREAK_EPS
SOIL_CATS = ["Clay", "Clay Loam", "Loam", "Sandy Loam", "Silt Loam"]


# ---------------------------------------------------------------------------------------------------- data
def load_table():
    s = pd.read_csv(ROOT / "data/processed/site_points_clean.csv")
    lc = pd.read_csv(ROOT / "data/processed/site_landcover.csv")
    t = s.merge(lc[["point_id", "lc_coverage", "share_tree", "share_built", "dominant_class"]], on="point_id")
    t = t[t.zoning_status.isin(["confirmed", "unconfirmed"])].reset_index(drop=True)
    ok = (t.lc_coverage >= 0.5) & (t.share_built < 0.2)
    t["train_ok"] = ok
    t["train_use"] = ok & t.slope_pct.notna() & t.elev_m.notna()
    return t


def design(t, variant):
    cols = {"elev_m": t.elev_m.to_numpy(float), "slope_pct": t.slope_pct.to_numpy(float)}
    if variant != "nosoil":
        for c in SOIL_CATS:
            cols["soil_" + c] = (t.soil_texture_lgu == c).to_numpy(float)
        cols["soil_none"] = t.soil_texture_lgu.isna().to_numpy(float)
    if variant == "nf":
        cols["nearest_feature_dist_m"] = t.nearest_feature_dist_m.to_numpy(float)
    if variant == "latlon":
        cols["lon"], cols["lat"] = t.lon.to_numpy(float), t.lat.to_numpy(float)
    return pd.DataFrame(cols)


# ---------------------------------------------------------------------------------------------------- models
def base_models():
    seed = SET["seed"]
    return {
        "RandomForest": (RandomForestRegressor(n_estimators=200, random_state=seed, n_jobs=-1), {"max_depth": [12, None], "min_samples_leaf": [1, 5]}),
        "DecisionTree": (DecisionTreeRegressor(random_state=seed), {"max_depth": [4, 8, 16, None]}),
        "KNN": (Pipeline([("sc", StandardScaler()), ("knn", KNeighborsRegressor())]), {"knn__n_neighbors": [5, 15, 31, 61]}),
        "Linear": (Pipeline([("sc", StandardScaler()), ("lin", LinearRegression())]), None),
        "MeanOnly": (DummyRegressor(strategy="mean"), None),
    }


def run_variant(table, variant, cells, log=print):
    """Out-of-fold predictions and per-fold metrics of every model for one variant."""
    t = table[table.train_use].reset_index(drop=True)
    X = design(t, variant).to_numpy(float)
    y = t.share_tree.to_numpy(float)
    cfg = {**cm.CFG, "outer_folds": SET["outer_folds"], "seed": SET["seed"], "spatial_block_cells": cells}
    folds = cm.make_folds(t, y, "spatial", cfg)
    groups = cm.group_ids(t, "spatial", cfg)
    rows, oof = [], {}
    for name, (est, grid) in base_models().items():
        pred = np.full(len(y), np.nan)
        for k, (tr, te) in enumerate(folds):
            if grid:
                inner = list(GroupKFold(SET["inner_folds"], shuffle=True, random_state=SET["seed"]).split(X[tr], y[tr], groups[tr]))
                gs = GridSearchCV(est, grid, cv=inner, scoring="neg_mean_squared_error", n_jobs=1, refit=True).fit(X[tr], y[tr])
                m, best = gs.best_estimator_, json.dumps(gs.best_params_, default=str)
            else:
                m, best = dataclasses_clone(est).fit(X[tr], y[tr]), ""
            p = m.predict(X[te])
            pred[te] = p
            rows.append({"variant": variant, "model": name, "fold": k + 1, "n_test": len(te), "r2": r2_score(y[te], p), "mae": mean_absolute_error(y[te], p),
                         "rmse": float(np.sqrt(mean_squared_error(y[te], p))), "best_params": best})
        oof[name] = pred
        log(f"    {variant:7} {name:12} mean R2 {np.mean([r['r2'] for r in rows if r['model'] == name]):.3f}")
    return pd.DataFrame(rows), oof, t


def dataclasses_clone(est):
    from sklearn.base import clone
    return clone(est)


def fold_table(df):
    g = df.groupby(["variant", "model"])
    out = g.agg(r2_mean=("r2", "mean"), r2_sd=("r2", lambda x: x.std(ddof=1)), mae_mean=("mae", "mean"), mae_sd=("mae", lambda x: x.std(ddof=1)), rmse_mean=("rmse", "mean")).reset_index()
    return out


# ---------------------------------------------------------------------------------------------------- drop rules
def evaluate_drop(main_folds, corr):
    r2 = main_folds.pivot(index="fold", columns="model", values="r2")
    rf = r2["RandomForest"]
    res = {"r2_by_model": {m: float(r2[m].mean()) for m in r2.columns}}
    r1 = {}
    for other in ("DecisionTree", "Linear", "KNN"):
        diff = float(rf.mean() - r2[other].mean())
        wins = int((rf > r2[other]).sum())
        r1[other] = {"margin": diff, "folds_better": wins, "ok": bool(diff >= DROP["R1_margin"] and wins >= DROP["R1_folds"])}
    res["R1"] = {"detail": r1, "ok": all(v["ok"] for v in r1.values())}
    res["R2"] = {"value": float(rf.mean()), "ok": bool(rf.mean() >= DROP["R2_min_r2"])}
    res["R3"] = {"value": float(corr), "ok": bool(abs(corr) <= DROP["R3_max_corr"])}
    res["drop"] = not (res["R1"]["ok"] and res["R2"]["ok"] and res["R3"]["ok"])
    return res


def ranking_check(t, oof):
    y_low = (t.share_tree.to_numpy(float) < 0.5)
    rows = []
    for name, p in oof.items():
        if name == "MeanOnly":
            continue
        order = np.argsort(p, kind="stable")
        r = {"model": name, "low_squares": int(y_low.sum()), "base_rate": float(y_low.mean()), "auroc": float(roc_auc_score(y_low, -p)),
             "mean_potential_low": float(p[y_low].mean()), "mean_potential_other": float(p[~y_low].mean())}
        for q in (0.10, 0.20):
            k = int(round(q * len(p)))
            bottom = order[:k]
            r[f"precision_bottom_{int(q * 100)}"] = float(y_low[bottom].mean())
            r[f"recall_bottom_{int(q * 100)}"] = float(y_low[bottom].sum() / y_low.sum())
        rows.append(r)
    return pd.DataFrame(rows)


def rule_correlation(t, potential):
    sc = pd.read_csv(ROOT / "data/processed/scores/site_scores.csv", usecols=["point_id", "s_rule", "s_prob"])
    g = sc.groupby("point_id").agg(mean_s_rule=("s_rule", "mean"), mean_s_prob=("s_prob", "mean"), n_eligible_rf=("s_prob", lambda x: int((x >= S_MIN).sum()))).reset_index()
    m = pd.DataFrame({"point_id": t.point_id, "potential": potential}).merge(g, on="point_id")
    out = {c: float(spearmanr(m.potential, m[c]).statistic) for c in ("mean_s_rule", "mean_s_prob", "n_eligible_rf")}
    return out


# ---------------------------------------------------------------------------------------------------- decision gate
def potential_vector(sub, pot):
    return sub.sites.point_id.map(pot).to_numpy(float)


def variant_results(sub, purpose, case, p, seed):
    """Hungarian on the matrix of one plan, with the current tie-break (baseline), the potential as tie-break, and W adjusted by the potential (3 factors)."""
    cols = case["cols"]
    P = np.asarray(sub.P[purpose], float)
    W, feas = mt.weights(sub.S[:, cols], P[cols])
    blocks_q, trees_q, cap = np.array(case["blocks_q"]), np.array(case["trees_q"]), np.array(case["caps"])
    xy = sub.sites[["utm_e", "utm_n"]].to_numpy(float)
    dist = np.hypot(xy[:, 0] - xy[:, 0].mean(), xy[:, 1] - xy[:, 1].mean())
    tb_d = dist / dist.max() if dist.max() > 0 else np.zeros(len(dist))
    have = np.isfinite(p)
    pf = np.where(have, p, np.nanmedian(p) if have.any() else 1.0)
    pc = np.clip(np.where(have, p, 1.0), 0.0, 1.0)
    variants = {"baseline": (W, tb_d), "tiebreak": (W, (1.0 - np.clip(pf, 0, 1)) + 0.001 * tb_d)}
    for a in SET["adjust_w_factors"]:
        variants[f"adjust_w_{a:.2f}"] = (W * (1.0 - a * (1.0 - pc))[:, None], tb_d)
    out, base_sq = {}, None
    for name, (Wm, tb) in variants.items():
        res = mt.assign_hungarian(Wm, feas, blocks_q, seed, tiebreak=tb)
        pi, si = res["point_idx"], res["species_idx"]
        sq = set(int(i) for i in pi)
        if name == "baseline":
            base_sq = sq
            # how many chosen blocks have another feasible square of the same species within the tie-break width (the room a tie-break has)
            tied = 0
            for i, j in zip(pi, si):
                alt = feas[:, j] & (np.abs(W[:, j] - W[i, j]) <= TIE_EPS)
                alt[i] = False
                alt[list(sq)] = False
                tied += int(alt.any())
        out[name] = {"placed_blocks": int(len(pi)), "placed_trees": sb.trees_formula(res["placed"], blocks_q, trees_q, cap), "total_W": float(W[pi, si].sum()),
                     "total_W_adjusted": float(Wm[pi, si].sum()), "squares": sq, "mean_potential": float(np.nanmean(p[pi])) if have[pi].any() else np.nan,
                     "mean_dist_m": float(dist[pi].mean()) if len(pi) else np.nan}
    for name, r in out.items():
        r["squares_changed"] = len(base_sq - r["squares"])
        r["tied_blocks_baseline"] = tied
        del r["squares"]
    return out


def gate_plans(pot, log=print):
    """All benchmark plans (barangays and polygons, rf source) under every variant. Returns the plan-level table and the reproduction check against the saved benchmark CSVs."""
    S = sb.SETTINGS
    d = sb.load_world("rf")
    d.field_ex_ids = set()
    rows = []
    saved_b = pd.read_csv(OUT_DIR / "scarcity_benchmark.csv")
    saved_b = saved_b[(saved_b.s_source == "rf") & (saved_b.layout == "blocks") & (saved_b.method == "hungarian") & (saved_b.status == "ok")].set_index(["barangay", "purpose", "tightness_target", "replicate"])
    saved_p = pd.read_csv(OUT_DIR / "scarcity_benchmark_polygons.csv")
    saved_p = saved_p[(saved_p.s_source == "rf") & (saved_p.method == "hungarian")].set_index(["polygon", "purpose", "tightness_target"])
    t0 = time.time()
    for b, bname in enumerate(d.barangay_names):
        sub = sb.area_context(d, b)
        if sub is None:
            continue
        p = potential_vector(sub, pot)
        for pi_, purpose in enumerate(S["purposes"]):
            for ti, tau in enumerate(S["tightness_targets"]):
                for r in range(S["replicates"]):
                    rng = np.random.default_rng([S["master_seed"], b, pi_, ti, r])
                    case, why = sb.make_case(sub, purpose, tau, 2 + r, rng, "blocks")
                    if case is None:
                        continue
                    res = variant_results(sub, purpose, case, p, S["solver_seed"])
                    key = (d.barangay_display[b], purpose, tau, r)
                    ref = saved_b.loc[key] if key in saved_b.index else None
                    chk = bool(ref is not None and int(ref.placed_blocks) == res["baseline"]["placed_blocks"] and abs(float(ref.total_W) - res["baseline"]["total_W"]) < 1e-5)
                    for v, x in res.items():
                        rows.append({"set": "barangay", "plan": "|".join(map(str, key)), "squares_in_area": len(sub.sites), "blocks_asked": case["blocks_asked"], "variant": v, "baseline_matches_saved": chk, **x})
    log(f"  barangay plans done in {time.time() - t0:.0f} s")
    polygons, _ = sbp.make_polygons(d.ctx.sites, log=lambda *_: None)
    for poly in polygons:
        si = sbp.POLY["sizes"].index(poly["size"])
        pn = int(poly["id"].split("-")[1])
        sc, _ = sbp.scope_of(d, poly["geojson"])
        sub = sc.sub
        if len(sub.sites) != poly["size"]:
            continue
        p = potential_vector(sub, pot)
        for pu, purpose in enumerate(S["purposes"]):
            for ti, tau in enumerate(S["tightness_targets"]):
                rng = np.random.default_rng([sbp.POLY["polygon_master_seed"], si, pn, pu, ti])
                case, why = sb.make_case(sub, purpose, tau, 2 + ((pn + pu + ti) % 4), rng, "blocks")
                if case is None:
                    continue
                res = variant_results(sub, purpose, case, p, S["solver_seed"])
                key = (poly["id"], purpose, tau)
                ref = saved_p.loc[key] if key in saved_p.index else None
                chk = bool(ref is not None and int(ref.placed_blocks) == res["baseline"]["placed_blocks"] and abs(float(ref.total_W) - res["baseline"]["total_W"]) < 1e-5)
                for v, x in res.items():
                    rows.append({"set": "polygon", "plan": "|".join(map(str, key)), "squares_in_area": poly["size"], "blocks_asked": case["blocks_asked"], "variant": v, "baseline_matches_saved": chk, **x})
    log(f"  all plans done in {time.time() - t0:.0f} s")
    return pd.DataFrame(rows)


def gate_summary(g):
    out = []
    for st in ("barangay", "polygon"):
        x = g[g["set"] == st]
        base = x[x.variant == "baseline"].set_index("plan")
        for v in x.variant.unique():
            y = x[x.variant == v].set_index("plan")
            dW = (y.total_W - base.total_W)
            r = {"set": st, "variant": v, "plans": len(y), "plans_blocks_or_trees_changed": int(((y.placed_blocks != base.placed_blocks) | (y.placed_trees != base.placed_trees)).sum()),
                 "plans_squares_changed": int((y.squares_changed > 0).sum()), "blocks_total": int(base.placed_blocks.sum()), "squares_changed_total": int(y.squares_changed.sum()),
                 "share_blocks_on_other_squares": float(y.squares_changed.sum() / base.placed_blocks.sum()),
                 "total_W_baseline": float(base.total_W.sum()), "total_W_variant": float(y.total_W.sum()), "delta_W_total": float(dW.sum()),
                 "delta_W_pct": float(dW.sum() / base.total_W.sum() * 100), "delta_W_pct_worst_plan": float((dW / base.total_W.where(base.total_W > 0) * 100).min()),
                 "mean_potential_baseline": float(np.nanmean(base.mean_potential)), "mean_potential_variant": float(np.nanmean(y.mean_potential)),
                 "mean_dist_ratio": float(y.mean_dist_m.sum() / base.mean_dist_m.sum()), "adjusted_W_variant": float(y.total_W_adjusted.sum()),
                 "tied_blocks_share": float(base.tied_blocks_baseline.sum() / base.placed_blocks.sum()), "baseline_matches_saved": f"{int(base.baseline_matches_saved.sum())} of {len(base)}"}
            out.append(r)
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------------------------------- report
def pct(x):
    return f"{x:.1f}%"


def git_line():
    def run(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return f"branch `{run('branch', '--show-current')}`, HEAD `{run('rev-parse', '--short', 'HEAD')}` plus uncommitted work (this script and its outputs)"


def report(main_tab, sens_tab, folds_main, verdict, rank_main, corr, gate, facts):
    L = ["# Potential benchmark: does a satellite-derived 'environmental support for woody cover' layer earn a place? (task 2, steps 1 to 3)", "",
         "## Pre-registration (written before the first run, 12 Oct 2026, and not changed)", ""]
    L += [f"- {t}" for t in DROP_TEXT]
    L += ["", f"Generated by `scripts/potential_benchmark.py` on {date.today().isoformat()} ({git_line()}). Settings below; one run only.", "", "## Verdict on the drop rules", ""]
    v = verdict
    r1 = v["R1"]["detail"]
    L += [f"**{'DROP: at least one rule failed.' if v['drop'] else 'No drop rule failed: the idea may go on (the adviser and Ayzhiedy still decide).'}**", "",
          "| Rule | Result | Value | Passed |", "|---|---|---|---|"]
    for other, lab in (("DecisionTree", "Decision Tree"), ("Linear", "linear regression"), ("KNN", "KNN")):
        L.append(f"| R1 forest vs {lab} | margin of mean R-squared (needs >= {DROP['R1_margin']:.2f}); better in {r1[other]['folds_better']} of 5 folds (needs >= {DROP['R1_folds']}) | {r1[other]['margin']:+.3f} | {'yes' if r1[other]['ok'] else 'NO'} |")
    L.append(f"| R2 forest R-squared, main model | needs >= {DROP['R2_min_r2']:.2f} | {v['R2']['value']:.3f} | {'yes' if v['R2']['ok'] else 'NO'} |")
    L.append(f"| R3 correlation with the rules (Spearman, mean s_rule over 45 species) | needs |rho| <= {DROP['R3_max_corr']:.2f} | {v['R3']['value']:+.3f} | {'yes' if v['R3']['ok'] else 'NO'} |")
    L += ["", "## Settings (fixed before the first run)", ""] + [f"- **{k}**: {val}" for k, val in SET.items()]
    L += ["", f"Data: {facts['n_train']:,} of {facts['n_scored']:,} scored squares were used (the others stay without a potential: {facts['n_built']} built-up or low-coverage, {facts['n_noslope']} without slope). "
          f"Target: mean tree share {facts['mean_tree']:.3f}, {facts['share_ge95']:.0%} of squares at 0.95 or more, {facts['n_low']} squares below 0.5 (mostly grassland and cropland).", "",
          "## Table 1: the main model, out of fold on 1 km blocks (mean over 5 folds, standard deviation in brackets)", "",
          "| Model | R-squared | MAE | RMSE | R-squared per fold (1 to 5) |", "|---|---|---|---|---|"]
    fm = folds_main.pivot(index="fold", columns="model", values="r2")
    for _, r in main_tab.iterrows():
        L.append(f"| {r.model} | {r.r2_mean:.3f} ({r.r2_sd:.3f}) | {r.mae_mean:.3f} ({r.mae_sd:.3f}) | {r.rmse_mean:.3f} | " + " / ".join(f"{x:.2f}" for x in fm[r.model]) + " |")
    L += ["", "## Table 2: sensitivities (mean R-squared over 5 folds; none of these is a drop rule)", "",
          "| Variant | Random Forest | Decision Tree | KNN | Linear | Mean only |", "|---|---|---|---|---|---|"]
    names = {"main": "main (elevation, slope, soil)", "nf": "main + nearest_feature_dist_m", "latlon": "main + longitude + latitude", "nosoil": "elevation and slope only (no soil)", "blk20": "main, 2 km blocks"}
    for var in ("main", "nf", "latlon", "nosoil", "blk20"):
        x = sens_tab[sens_tab.variant == var].set_index("model")
        L.append(f"| {names[var]} | " + " | ".join(f"{x.loc[m].r2_mean:.3f} ({x.loc[m].r2_sd:.3f})" for m in ("RandomForest", "DecisionTree", "KNN", "Linear", "MeanOnly")) + " |")
    L += ["", f"## Ranking check on the {facts['n_low']} squares with tree cover below 0.5 (descriptive; main model; base rate {facts['n_low'] / facts['n_train']:.1%})", "",
          "| Model | AUROC | Mean potential: low squares / others | Lowest 10% of potential: share that are low / share of all low squares caught | Lowest 20%: same |", "|---|---|---|---|---|"]
    for _, r in rank_main.iterrows():
        L.append(f"| {r.model} | {r.auroc:.3f} | {r.mean_potential_low:.2f} / {r.mean_potential_other:.2f} | {r.precision_bottom_10:.1%} / {r.recall_bottom_10:.1%} | {r.precision_bottom_20:.1%} / {r.recall_bottom_20:.1%} |")
    L += ["", "## Correlation of the forest's potential with the rules (Spearman, per square)", "",
          f"- with the mean `s_rule` over the 45 species (R3): **{corr['mean_s_rule']:+.3f}**; with the mean `s_prob`: {corr['mean_s_prob']:+.3f}; with the number of eligible species (S >= 0.50, rf): {corr['n_eligible_rf']:+.3f}", "",
          "## Decision gate: what would the layer change in the benchmark plans? (rf source, Hungarian, no switch built)", "",
          "Plans are the 534 barangay plans and the 893 drawn-polygon plans of the two scarcity benchmarks (same seeds). `baseline` = today's matching (distance tie-break). "
          "Placed blocks and trees can only change if feasibility changes; none of the variants touches S or the 0.50 test, so they are expected to be identical, and are counted to check. "
          "Total W is the ordinary W of the chosen squares (not adjusted), so a negative change is what the potential costs.", ""]
    for st, lab in (("barangay", "Barangay plans"), ("polygon", "Drawn-polygon plans")):
        x = gate[gate["set"] == st]
        L += [f"### {lab}", "", "| Variant | Plans | Plans with other placed blocks or trees | Plans with other squares | Blocks on other squares | Total W change | Worst single plan | Mean potential of chosen squares (baseline to variant) | Mean distance to area centre (variant / baseline) |", "|---|---|---|---|---|---|---|---|---|"]
        for _, r in x.iterrows():
            L.append(f"| {r.variant} | {r.plans} | {r.plans_blocks_or_trees_changed} | {r.plans_squares_changed} | {r.squares_changed_total} of {r.blocks_total} ({r.share_blocks_on_other_squares:.1%}) | "
                     f"{r.delta_W_total:+.4f} ({r.delta_W_pct:+.4f}%) | {r.delta_W_pct_worst_plan:+.3f}% | {r.mean_potential_baseline:.3f} to {r.mean_potential_variant:.3f} | {r.mean_dist_ratio:.3f} |")
        b = x[x.variant == "baseline"].iloc[0]
        L += ["", f"Room for a tie-break: in the baseline plans {b.tied_blocks_share:.1%} of the chosen blocks have another feasible square of the same species within the tie-break width (1e-6 of W). "
              f"The baseline of this script reproduces the saved benchmark in {b.baseline_matches_saved} plans.", ""]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    table = load_table()
    n_scored = len(table)
    used = table[table.train_use]
    facts = {"n_scored": n_scored, "n_train": len(used), "n_built": int((~table.train_ok).sum()), "n_noslope": int((table.train_ok & ~table.train_use).sum()),
             "mean_tree": float(used.share_tree.mean()), "share_ge95": float((used.share_tree >= 0.95).mean()), "n_low": int((used.share_tree < 0.5).sum())}
    print(f"squares: scored {n_scored:,}, used {len(used):,}, low-tree {facts['n_low']}", flush=True)
    all_folds, oofs, tables = [], {}, {}
    for variant, cells in (("main", SET["block_cells"]), ("nf", SET["block_cells"]), ("latlon", SET["block_cells"]), ("nosoil", SET["block_cells"]), ("blk20", SET["block_cells_sensitivity"])):
        print(f"  variant {variant} ...", flush=True)
        f, oof, t = run_variant(table, "main" if variant == "main" else variant, cells)
        all_folds.append(f)
        oofs[variant] = oof
        tables[variant] = t
    folds = pd.concat(all_folds, ignore_index=True)
    ft = fold_table(folds)
    main_folds = folds[folds.variant == "main"]
    main_tab = ft[ft.variant == "main"].set_index("model").loc[["RandomForest", "DecisionTree", "KNN", "Linear", "MeanOnly"]].reset_index()
    t_main = tables["main"]
    pot_oof = np.clip(oofs["main"]["RandomForest"], 0.0, 1.0)
    corr = rule_correlation(t_main, pot_oof)
    verdict = evaluate_drop(main_folds, corr["mean_s_rule"])
    rank_main = ranking_check(t_main, oofs["main"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pot = pd.Series(pot_oof, index=t_main.point_id.to_numpy())
    pd.DataFrame({"point_id": t_main.point_id, "potential_oof": pot_oof.round(4), "share_tree_observed": t_main.share_tree.round(4)}).to_csv(OUT_DIR / "potential_oof_main.csv", index=False)
    folds.round(6).to_csv(OUT_DIR / "potential_model_comparison.csv", index=False)
    print("  decision gate: plans under every variant ...", flush=True)
    gp = gate_plans(pot)
    gp.round(6).to_csv(OUT_DIR / "potential_gate_plans.csv", index=False)
    gate = gate_summary(gp)
    (OUT_DIR / "POTENTIAL_BENCHMARK.md").write_text(report(main_tab, ft, main_folds, verdict, rank_main, corr, gate, facts), encoding="utf-8")
    print(f"done in {time.time() - t0:.0f} s; verdict: {'DROP' if verdict['drop'] else 'no drop rule failed'}; R1 {verdict['R1']['ok']}, R2 {verdict['R2']['ok']} ({verdict['R2']['value']:.3f}), R3 {verdict['R3']['ok']} ({verdict['R3']['value']:+.3f})")


if __name__ == "__main__":
    main()
