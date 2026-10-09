#!/usr/bin/env python3
"""Do any of the 40 agriculturist sample pairs change verdict between the expert rules and the Random Forest? (round 19c)

    python scripts/check_agri_sample_rf.py

Reads (changes nothing): data/validation/agri_sample_marks_20261007.csv, data/validation/agri_sample_results_20261007.csv (the pairs scored with the hard slope gate, as printed),
data/validation/sample_printed_verdicts.csv, and the saved scores (s_rule of the graded slope rule, s_prob of the Random Forest).
Writes data/validation/agri_sample_rf_check.txt (a new file; the printed sheet and the results csv are NOT touched).

Three verdicts per pair (suitable = S >= 0.50): the rules with the hard slope gate (as printed), the rules with the graded slope rule (today's saved s_rule), and the Random Forest (s_prob).
The difference between the first two is the slope rule of round 18; the difference between the last two is the Random Forest alone.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "data" / "validation"
S_MIN = 0.50


def main():
    marks = pd.read_csv(V / "agri_sample_marks_20261007.csv", comment="#")
    hard = pd.read_csv(V / "agri_sample_results_20261007.csv")[["sample_id", "S_today"]].rename(columns={"S_today": "S_hard"})
    printed = pd.read_csv(V / "sample_printed_verdicts.csv", comment="#")
    sp = pd.read_csv(ROOT / "data" / "processed" / "species_clean.csv", usecols=["species_id", "common_name"])
    sc = pd.read_csv(ROOT / "data" / "processed" / "scores" / "site_scores.csv", usecols=["point_id", "species_id", "s_rule", "s_prob"])
    m = marks.merge(sp, left_on="species", right_on="common_name", how="left")
    m = m.merge(sc, left_on=["grid", "species_id"], right_on=["point_id", "species_id"], how="left").merge(hard, on="sample_id").merge(printed, on="sample_id")
    assert len(m) == 40 and m.s_prob.notna().all(), "the saved scores have no s_prob for the sample pairs: run python scripts/rebuild_scores.py"
    m["v_hard"], m["v_graded"], m["v_rf"] = m.S_hard >= S_MIN, m.s_rule >= S_MIN, m.s_prob >= S_MIN
    L = []
    P = L.append
    P("Agriculturist sample (40 pairs): verdicts of the expert rules (hard slope gate, as printed), the expert rules (graded slope rule, today) and the Random Forest (s_prob). Suitable = S >= 0.50.")
    P("The printed sheet and the results csv are not changed by this check.")
    P("")
    P(f"{'id':<4} {'species':<18} {'grid':>6} {'mark':>4} {'printed':<12} {'S hard':>7} {'S graded':>9} {'S forest':>9}  verdicts hard / graded / forest")
    for r in m.itertuples():
        P(f"{r.sample_id:<4} {r.species:<18} {r.grid:>6} {r.mark:>4} {r.printed_verdict:<12} {r.S_hard:>7.3f} {r.s_rule:>9.3f} {r.s_prob:>9.3f}  {'S' if r.v_hard else 'N'} / {'S' if r.v_graded else 'N'} / {'S' if r.v_rf else 'N'}")
    P("")
    rf_vs_graded = m[m.v_graded != m.v_rf]
    slope_effect = m[m.v_hard != m.v_graded]
    rf_vs_hard = m[m.v_hard != m.v_rf]
    P(f"Verdicts that differ between the rules (graded, today) and the Random Forest: {len(rf_vs_graded)} of 40" + (": " + ", ".join(f"{r.sample_id} {r.species} (rules {r.s_rule:.3f}, forest {r.s_prob:.3f})" for r in rf_vs_graded.itertuples()) if len(rf_vs_graded) else " (none)"))
    P(f"Verdicts that differ between the rules as printed (hard slope gate) and today's rules (graded slope rule; the slope rule of round 18, not the forest): {len(slope_effect)} of 40"
      + (": " + ", ".join(f"{r.sample_id} {r.species} (slope gate, S {r.S_hard:.2f} -> {r.s_rule:.3f})" for r in slope_effect.itertuples()) if len(slope_effect) else " (none)"))
    P(f"Verdicts that differ between the rules as printed and the Random Forest: {len(rf_vs_hard)} of 40" + (": " + ", ".join(r.sample_id for r in rf_vs_hard.itertuples()) if len(rf_vs_hard) else " (none)"))
    judged = m[m.mark != "X"]
    for name, col in (("printed rules (hard)", "v_hard"), ("rules (graded)", "v_graded"), ("Random Forest", "v_rf")):
        for scheme, ex in (("Marginal as Suitable", judged.mark.isin(["S", "M"])), ("Marginal as Not suitable", judged.mark == "S")):
            P(f"   agreement with the agriculturist, {name}, {scheme}: {(ex == judged[col]).mean():.1%} ({int((ex == judged[col]).sum())} of {len(judged)})")
    text = "\n".join(L) + "\n"
    (V / "agri_sample_rf_check.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
