#!/usr/bin/env python3
"""Expert rules against the Random Forest as the source of S (round 19). Reads the saved scores (s_rule and s_prob), changes nothing.

    python scripts/rf_vs_rules_report.py --processed data/processed

Reports, for the slope mode the scores were made with:
  1. how many pairs change eligibility (S >= 0.50) between rules and rf, in both directions;
  2. how much the top-20 squares of each species overlap (squares ranked by S; ties are broken by point id, and the size of the tie at the top is reported);
  3. the matching benchmark (Hungarian, greedy, random) of the three purposes with S from the rules and with S from the Random Forest (300 trees, whole municipality; points and blocks);
  4. the out-of-fold accuracy of the Random Forest against a Decision Tree (from rf_vs_dt_oof.csv, written by train_rf.py).
Writes <processed>/rf_vs_rules_report.txt and rf_vs_rules_benchmark.csv (the matching_benchmark.csv of the app is not touched).
"""
import argparse, json, sys, tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import run_plan as rp  # noqa: E402

S_MIN = 0.50
TOP = 20


def top_sets(S, point_ids, k):
    """{species column: set of the k point ids with the highest S (ties broken by the lower point id)}."""
    order_key = np.argsort(point_ids, kind="stable")
    out, ties = [], []
    for j in range(S.shape[1]):
        col = S[:, j]
        idx = np.lexsort((point_ids, -col))[:k]
        out.append(set(point_ids[idx].tolist()))
        ties.append(int((col >= col[idx[0]] - 1e-12).sum()))
    return out, ties


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", default="data/processed")
    a = ap.parse_args()
    out = Path(a.processed)
    run = json.loads((out / "scores" / "score_run.json").read_text(encoding="utf-8"))
    ctx_r = rp.load_context(out, include_unzoned=True, s_source="rules")
    ctx_f = rp.load_context(out, include_unzoned=True, s_source="rf")
    S_r, S_f = ctx_r.S, ctx_f.S
    names = ctx_r.species.common_name.to_numpy()
    L = []
    P = L.append
    P(f"Expert rules against the Random Forest as the source of S. Slope mode of the saved scores: {run['slope_mode']}. {S_r.shape[0]:,} squares x {S_r.shape[1]} species = {S_r.size:,} pairs.")
    P("The forest was trained on the expert-rule labels (S >= 0.50): it generalises the rules, it is not an independent measurement of survival.")
    P("")
    er, ef = S_r >= S_MIN, S_f >= S_MIN
    P(f"1. ELIGIBILITY (S >= {S_MIN:.2f})")
    P(f"   rules {int(er.sum()):,}   rf {int(ef.sum()):,}   changed pairs {int((er != ef).sum()):,} ({(er != ef).mean():.3%} of all pairs)")
    P(f"   eligible by the rules but NOT by the forest: {int((er & ~ef).sum()):,}   eligible by the forest but NOT by the rules: {int((~er & ef).sum()):,}")
    P(f"   hard gates kept: pairs with rule S = 0 and s_prob > 0: {int(((S_r == 0) & (S_f > 0)).sum())}")
    d = np.abs(S_r - S_f)[(S_r > 0)]
    P(f"   where the rules give S > 0: mean |S rules - s_prob| {d.mean():.3f}, 95th percentile {np.percentile(d, 95):.3f}, largest {d.max():.3f}")
    ch = pd.DataFrame({"species": np.tile(names, S_r.shape[0]), "rules_to_rf": (er & ~ef).ravel(), "rf_to_rules": (~er & ef).ravel()}).groupby("species").sum()
    ch["total"] = ch.rules_to_rf + ch.rf_to_rules
    P("   species with the most changed pairs: " + ", ".join(f"{k} {int(v.total)} (rules-only {int(v.rules_to_rf)}, rf-only {int(v.rf_to_rules)})" for k, v in ch.sort_values("total", ascending=False).head(6).iterrows()))
    P("")
    pid = ctx_r.sites.point_id.to_numpy()
    tr, ties_r = top_sets(S_r, pid, TOP)
    tf, ties_f = top_sets(S_f, pid, TOP)
    ov = np.array([len(x & y) for x, y in zip(tr, tf)])
    P(f"2. TOP-{TOP} SQUARES PER SPECIES (ranked by S; ties broken by the lower point id)")
    P(f"   overlap of the two top-{TOP} lists: mean {ov.mean():.1f} of {TOP} (median {np.median(ov):.0f}; lowest {ov.min()} for {names[ov.argmin()]}; highest {ov.max()}); species with the same {TOP} squares: {int((ov == TOP).sum())} of {len(ov)}")
    P(f"   the rules often tie at the top: squares sharing the highest S, median {int(np.median(ties_r))} per species (species with more than {TOP} tied: {int((np.array(ties_r) > TOP).sum())}); the forest: median {int(np.median(ties_f))}")
    P("   so a low overlap mostly reflects how the ties are broken; both lists hold squares with a very high S. Mean S of the rules' top list under the forest and of the forest's top list under the rules:")
    mr = np.mean([S_f[np.isin(pid, list(t)), j].mean() for j, t in enumerate(tr)])
    mf = np.mean([S_r[np.isin(pid, list(t)), j].mean() for j, t in enumerate(tf)])
    P(f"   rules' top-{TOP} under the forest {mr:.3f}; forest's top-{TOP} under the rules {mf:.3f}")
    P("")
    P("3. MATCHING BENCHMARK (300 trees, whole municipality; total W; the app's matching_benchmark.csv is not touched)")
    rows = []
    for name, ctx in (("rules", ctx_r), ("rf", ctx_f)):
        with tempfile.TemporaryDirectory() as td:
            rp.run_benchmark(ctx, td)
            b = pd.read_csv(Path(td) / "matching_benchmark.csv")
        b.insert(0, "s_source", name)
        rows.append(b)
    bm = pd.concat(rows)
    bm.to_csv(out / "rf_vs_rules_benchmark.csv", index=False)
    P(f"   {'purpose':<10} {'layout':<7} {'method':<16} {'W rules':>10} {'W rf':>10} {'placed rules':>13} {'placed rf':>10}")
    pv = bm[bm.method.isin(["hungarian", "greedy", "random_feasible"])].pivot_table(index=["layout_mode", "purpose", "method"], columns="s_source", values=["total_W", "placed"])
    for (lay, pur, meth), r in pv.iterrows():
        P(f"   {pur:<10} {lay:<7} {meth:<16} {r[('total_W', 'rules')]:>10.4f} {r[('total_W', 'rf')]:>10.4f} {r[('placed', 'rules')]:>13.0f} {r[('placed', 'rf')]:>10.0f}")
    for src in ("rules", "rf"):
        t = bm[(bm.s_source == src) & bm.method.isin(["hungarian", "greedy"])].pivot_table(index=["purpose", "layout_mode"], columns="method", values="total_W")
        P(f"   {src}: Hungarian minus greedy total W, largest absolute gap over every purpose and layout: {float((t.hungarian - t.greedy).abs().max()):.6f}"
          + ("; greedy is never better" if bool(((t.hungarian - t.greedy) >= -1e-9).all()) else "; greedy was better somewhere"))
    P("")
    P("3b. THE SAME PLANS JUDGED BY BOTH SCORES (a plan made with one source of S, its total W recomputed with the other: the totals in section 3 use different S, so they are not comparable by themselves)")
    P(f"   {'purpose':<10} {'layout':<7} {'plan made with':<15} {'total W by the rules':>21} {'total W by the forest':>22} {'squares shared with the other plan':>36}")
    sid_idx = {int(s_): k for k, s_ in enumerate(ctx_r.species.species_id)}
    pt_idx = {int(p_): i for i, p_ in enumerate(pid)}
    for lay in ("points", "blocks"):
        for pur in ("urban", "planting", "watershed"):
            plans = {}
            for name, ctx in (("rules", ctx_r), ("rf", ctx_f)):
                plan, _ = rp.make_plan(ctx, pur, rp.CFG["bench_saplings"], seed=rp.CFG["seed"], method="hungarian", layout_mode=lay)
                plans[name] = plan
            Wr, _f = rp.mt.weights(S_r, ctx_r.P[pur])
            Wf, _f = rp.mt.weights(S_f, ctx_f.P[pur])
            def tot(plan, W):
                return float(sum(W[pt_idx[int(p_)], sid_idx[int(s_)]] for p_, s_ in zip(plan.point_id, plan.species_id)))
            shared = len(set(plans["rules"].point_id) & set(plans["rf"].point_id))
            for name in ("rules", "rf"):
                P(f"   {pur:<10} {lay:<7} {name:<15} {tot(plans[name], Wr):>21.4f} {tot(plans[name], Wf):>22.4f} {shared:>20} of {len(plans[name])}")
    P("")
    P("4. OUT-OF-FOLD ACCURACY (same spatial folds, 1 km blocks, label = rules S >= 0.50, no label noise; from rf_vs_dt_oof.csv)")
    f = out / "rf_vs_dt_oof.csv"
    if f.is_file():
        t = pd.read_csv(f)
        for r in t.itertuples():
            P(f"   {r.model:<38} accuracy {r.accuracy:.5f} (folds {r.accuracy_fold_mean:.5f} +/- {r.accuracy_fold_std:.5f}), precision {r.precision:.5f}, recall {r.recall:.5f}, ROC AUC {r.roc_auc:.5f}")
    else:
        P("   rf_vs_dt_oof.csv not found: run pipeline/train_rf.py")
    (out / "rf_vs_rules_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
