#!/usr/bin/env python3
"""Compares the two slope modes (round 18): how many pairs are eligible with the hard gate and with the graded rule, which pairs are newly eligible,
which species gain most, and whether any newly eligible pair stands on a steep square (slope above STEEP_SQUARE_SLOPE_PCT percent, 57.7 percent = about 30 degrees).

    python scripts/slope_mode_report.py --hard <folder with scores/site_scores.csv made with --slope-mode hard> --graded <same, graded> --processed data/processed --out data/processed

Writes <out>/slope_mode_report.txt and <out>/slope_graded_newly_eligible.csv (one row per newly eligible pair). Nothing is changed in the inputs.
"""
import argparse
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import score_sites as ss  # noqa: E402

S_MIN = 0.50
STEEP_PCT = ss.STEEP_SQUARE_SLOPE_PCT      # the named setting: slope in PERCENT (the unit of the data and of the species limits)


def load(folder):
    t = pd.read_csv(Path(folder) / "scores" / "site_scores.csv", usecols=["point_id", "species_id", "s_rule", "breakdown_json"])
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hard", required=True)
    ap.add_argument("--graded", required=True)
    ap.add_argument("--processed", default="data/processed")
    ap.add_argument("--out", default="data/processed")
    a = ap.parse_args()
    h, g = load(a.hard), load(a.graded)
    sp = pd.read_csv(Path(a.processed) / "species_clean.csv")[["species_id", "common_name", "max_slope_pct"]]
    st = pd.read_csv(Path(a.processed) / "site_points_clean.csv")[["point_id", "slope_pct", "zoning_status", "zone_desc"]]
    m = h.merge(g, on=["point_id", "species_id"], suffixes=("_hard", "_graded"))
    assert len(m) == len(h) == len(g)
    m["elig_hard"] = m.s_rule_hard >= S_MIN
    m["elig_graded"] = m.s_rule_graded >= S_MIN
    changed = m[(m.s_rule_hard != m.s_rule_graded)]
    new = m[m.elig_graded & ~m.elig_hard].merge(sp, on="species_id").merge(st, on="point_id")
    new["over_limit_points"] = (new.slope_pct - new.max_slope_pct).round(2)       # percentage points of slope above the species limit
    new["over_limit_share"] = (new.over_limit_points / new.max_slope_pct).round(3)
    lost = int((m.elig_hard & ~m.elig_graded).sum())
    unchanged_where_eligible = bool((m[m.elig_hard].s_rule_hard == m[m.elig_hard].s_rule_graded).all())
    steep = new[new.slope_pct > STEEP_PCT]
    by_sp = new.groupby("common_name").size().sort_values(ascending=False)
    elig_hard_by_sp = m[m.elig_hard].groupby("species_id").size()
    gain = new.groupby(["species_id", "common_name"]).size().rename("newly_eligible").reset_index()
    gain["eligible_hard"] = gain.species_id.map(elig_hard_by_sp).fillna(0).astype(int)
    gain["gain_share"] = (gain.newly_eligible / gain.eligible_hard.replace(0, math.nan)).round(3)
    L = []
    P = L.append
    P("Slope rule: hard gate against the graded rule (round 18). PROVISIONAL: a team decision, the adviser confirms.")
    P("Slope unit: percent (site slope_pct against species max_slope_pct). The graded margin is 25% of the species limit.")
    P(f"Pairs scored: {len(m):,} (8,010 squares x 45 species)")
    P(f"Eligible pairs (S >= {S_MIN:.2f}): hard {int(m.elig_hard.sum()):,}   graded {int(m.elig_graded.sum()):,}   newly eligible {len(new):,}   lost {lost}")
    P(f"Pairs whose S changed: {len(changed):,}; every pair that was eligible under the hard gate keeps exactly the same S: {unchanged_where_eligible}")
    P(f"Newly eligible pairs on squares: {new.point_id.nunique():,} different squares, {new.species_id.nunique()} different species")
    P("")
    P("How far over the limit the newly eligible pairs are (percentage points of slope, and as a share of the limit):")
    P(f"  median {new.over_limit_points.median():.1f} points ({new.over_limit_share.median():.1%}); largest {new.over_limit_points.max():.1f} points ({new.over_limit_share.max():.1%})")
    P("")
    P("Species that gain the most (newly eligible pairs; share of their eligible pairs under the hard gate):")
    for r in gain.sort_values("newly_eligible", ascending=False).head(10).itertuples():
        P(f"  {r.common_name:<28} +{r.newly_eligible:>4}  (hard {r.eligible_hard:>5}, +{r.gain_share:.1%})")
    P(f"  species with no gain: {45 - len(gain)}")
    P("")
    P(f"Newly eligible pairs on a steep square (slope above {STEEP_PCT:g} percent, the setting STEEP_SQUARE_SLOPE_PCT; about 30 degrees): {len(steep)}")
    P("  by species: " + ", ".join(f"{k} {v}" for k, v in steep.groupby("common_name").size().sort_values(ascending=False).items()) + f"; steepest square {steep.slope_pct.max():.1f} percent" if len(steep) else "  none")
    for r in steep.sort_values(["slope_pct", "common_name"], ascending=[False, True]).itertuples():
        P(f"  point {int(r.point_id)}  {r.common_name}  slope {r.slope_pct:.1f} percent, species limit {r.max_slope_pct:g} percent, over by {r.over_limit_points:.1f} points, S {r.s_rule_graded:.3f}, zone {r.zone_desc if isinstance(r.zone_desc, str) else "outside the zoning map"}, zoning {r.zoning_status}")
    out = Path(a.out)
    (out / "slope_mode_report.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    new[["point_id", "species_id", "common_name", "slope_pct", "max_slope_pct", "over_limit_points", "over_limit_share", "s_rule_graded", "zoning_status", "zone_desc"]].rename(columns={"s_rule_graded": "S_graded"}).sort_values(["species_id", "point_id"]).to_csv(out / "slope_graded_newly_eligible.csv", index=False)
    print("\n".join(L))


if __name__ == "__main__":
    main()
