#!/usr/bin/env python3
"""Rebuilds the saved site scores in the right order and says which source of S the app will use (round 19c).

    python scripts/rebuild_scores.py                  # runs the three steps, then prints the S_SOURCE it ends with
    python scripts/rebuild_scores.py --dry-run        # only prints the three commands
    python scripts/rebuild_scores.py --out data/processed --slope-mode graded

The order matters:
  1. pipeline/score_sites.py     the expert rules: s_rule for every square x species pair (s_prob is left empty)
  2. pipeline/make_pair_table.py the pair table the Random Forest learns from (raw features and the rule labels)
  3. pipeline/train_rf.py        the spatial out-of-fold Random Forest: fills s_prob, saves the model file

Running step 1 again empties s_prob; the app then falls back to the expert rules and /health shows a warning until step 3 has run. Restart the API afterwards.
The scores folder (data/processed/scores/) and the model folder are git-ignored (the files are 100 MB or more), so a fresh clone must run this script once.
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commands(out, slope_mode=None):
    py = sys.executable
    sc = [py, str(ROOT / "pipeline" / "score_sites.py"), "--out", out]
    if slope_mode:
        sc += ["--slope-mode", slope_mode]
    return [("1. expert rules (score_sites.py)", sc),
            ("2. pair table (make_pair_table.py)", [py, str(ROOT / "pipeline" / "make_pair_table.py"), "--out", out]),
            ("3. Random Forest (train_rf.py)", [py, str(ROOT / "pipeline" / "train_rf.py"), "--out", out])]


def final_source(out):
    """The S_SOURCE the app will really use with the saved scores (honours OS_S_SOURCE), the warning if it fell back, and the number of eligible pairs."""
    sys.path.insert(0, str(ROOT / "pipeline"))
    import matching as mt
    import run_plan as rp
    ctx = rp.load_context(out, include_unzoned=True)
    return ctx.s_source, ctx.s_requested, ctx.s_warning, int((ctx.S >= mt.CFG["s_min"]).sum())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--slope-mode", choices=("graded", "hard"), default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    steps = commands(a.out, a.slope_mode)
    for title, cmd in steps:
        print(f"== {title}\n   {' '.join(cmd)}")
        if not a.dry_run:
            t0 = time.time()
            r = subprocess.run(cmd, cwd=ROOT)
            print(f"   step took {time.time() - t0:.0f} s")
            if r.returncode != 0:
                raise SystemExit(f"step failed ({title}); the scores may be incomplete: the app will use the expert rules until all three steps have run")
    if a.dry_run:
        return steps
    src, req, warn, n = final_source(a.out)
    print(f"\nS_SOURCE it ends with: {src} (asked for: {req}); eligible pairs (S >= 0.50): {n:,}")
    if warn:
        print("WARNING:", warn)
    print("Restart the API: python -m uvicorn api_v2:app --port 8001")
    return steps


if __name__ == "__main__":
    main()
