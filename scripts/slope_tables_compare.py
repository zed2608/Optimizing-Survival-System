#!/usr/bin/env python3
"""Hard slope gate against the graded slope rule (round 18b): the model comparison (accuracy, RF against DT and the others) and the matching benchmark (Hungarian against greedy).

    python scripts/slope_tables_compare.py --processed data/processed

Reads model_comparison_hard.csv / model_comparison.csv and matching_benchmark_hard.csv / matching_benchmark.csv; writes slope_tables_hard_vs_graded.txt and
slope_tables_hard_vs_graded.csv in the same folder. Nothing is overwritten except those two files.
"""
import argparse
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", default="data/processed")
    p = Path(ap.parse_args().processed)
    mh, mg = pd.read_csv(p / "model_comparison_hard.csv"), pd.read_csv(p / "model_comparison.csv")
    key = ["model", "setting", "noise", "metric"]
    m = mh.merge(mg, on=key, suffixes=("_hard", "_graded"))
    acc = m[m.metric == "accuracy"].copy()
    acc["change"] = (acc.mean_graded - acc.mean_hard).round(4)
    L = []
    P = L.append
    P("Slope rule: hard gate against graded (round 18b). Tables re-run with SLOPE_MODE graded; the hard results are kept in the files with the suffix _hard.")
    P("")
    P("MODEL COMPARISON: accuracy (mean over 5 folds; std in brackets), the label is S >= 0.50")
    P(f"  {'setting':<12} {'noise':>5}  {'model':<27} {'hard':>16} {'graded':>16} {'change':>8}")
    for r in acc.sort_values(["setting", "noise", "model"]).itertuples():
        P(f"  {r.setting:<12} {r.noise:>5}  {r.model:<27} {r.mean_hard:>7.4f} ({r.std_hard:.4f}) {r.mean_graded:>7.4f} ({r.std_graded:.4f}) {r.change:>+8.4f}")
    P("")
    for s, nz in (("random", 0.0), ("random", 0.05)):
        t = acc[(acc.setting == s) & (acc.noise == nz)].set_index("model")
        if {"RandomForest", "DecisionTree"} <= set(t.index):
            P(f"  {s} folds, noise {nz}: RF - DT accuracy: hard {t.loc['RandomForest', 'mean_hard'] - t.loc['DecisionTree', 'mean_hard']:+.4f}, graded {t.loc['RandomForest', 'mean_graded'] - t.loc['DecisionTree', 'mean_graded']:+.4f}")
    others = acc[~acc.setting.isin(["random"])]
    if len(others):
        for s in sorted(others.setting.unique()):
            t = others[others.setting == s]
            for nz in sorted(t.noise.unique()):
                u = t[t.noise == nz].set_index("model")
                if {"RandomForest", "DecisionTree"} <= set(u.index):
                    P(f"  {s}, noise {nz}: RF - DT accuracy: hard {u.loc['RandomForest', 'mean_hard'] - u.loc['DecisionTree', 'mean_hard']:+.4f}, graded {u.loc['RandomForest', 'mean_graded'] - u.loc['DecisionTree', 'mean_graded']:+.4f}")
    bh, bg = pd.read_csv(p / "matching_benchmark_hard.csv"), pd.read_csv(p / "matching_benchmark.csv")
    k2 = ["purpose", "layout_mode", "method"]
    b = bh.merge(bg, on=k2, suffixes=("_hard", "_graded"))
    P("")
    P("MATCHING BENCHMARK: total W of 300 trees (whole municipality), Hungarian against greedy")
    P(f"  {'purpose':<10} {'layout':<7} {'method':<16} {'total W hard':>13} {'total W graded':>15} {'placed hard':>12} {'placed graded':>14}")
    for r in b[b.method.isin(["hungarian", "greedy", "random_feasible"])].sort_values(["layout_mode", "purpose", "method"]).itertuples():
        P(f"  {r.purpose:<10} {r.layout_mode:<7} {r.method:<16} {r.total_W_hard:>13.4f} {r.total_W_graded:>15.4f} {r.placed_hard:>12.0f} {r.placed_graded:>14.0f}")
    P("")
    for mode in ("hard", "graded"):
        t = b[b.method.isin(["hungarian", "greedy"])].pivot_table(index=["purpose", "layout_mode"], columns="method", values=f"total_W_{mode}")
        same = bool(((t.hungarian - t.greedy).abs() < 1e-9).all())
        P(f"  {mode}: Hungarian total = greedy total in every purpose and layout: {same} (largest gap {float((t.hungarian - t.greedy).abs().max()):.6f})")
    pd.concat([acc.assign(table="model_comparison_accuracy").rename(columns={"mean_hard": "hard", "mean_graded": "graded"})[["table", "setting", "noise", "model", "hard", "graded", "change"]]]).to_csv(p / "slope_tables_hard_vs_graded.csv", index=False)
    (p / "slope_tables_hard_vs_graded.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
