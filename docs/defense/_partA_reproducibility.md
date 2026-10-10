# Part A - Reproducibility (round 20, run 2026-10-10)

Method: a scratch COPY (pipeline/, scripts/, data/processed without scores/models/plans/kits/cache, and the three shapefiles) was built outside the repo;
`python scripts/rebuild_scores.py --out data/processed` was run there from nothing (graded slope mode, default). The real `data/processed/scores` was never written.
Compared with the real saved files by a script (scratchpad `cmp20a.py`).

| Check | Result |
|---|---|
| Rows (pairs) real / scratch | 360,450 / 360,450 (8,010 squares x 45 species) |
| s_rule, max / mean absolute difference | 0 / 0 (0 rows differ) |
| s_prob, max / mean absolute difference | 0 / 0 (0 rows differ) |
| Eligible pairs (>= 0.50), rules | 257,869 real = 257,869 scratch |
| Eligible pairs (>= 0.50), rf | 257,929 real = 257,929 scratch |
| `rf_site_suitability.joblib` sha256 | identical (ae7ad258294c928f...) |
| `rf_site_suitability_classifier.joblib` sha256 | identical (6192d35e93b2eb0b...) |
| `scores/site_scores.csv` sha256 | identical (5bc7138aa87be774...) |
| `pair_table.csv.gz` | file bytes differ (gzip header time stamp); UNCOMPRESSED content identical (sha256 3c7c5f41c81e7da5...) |
| Model meta json | every field identical except `trained_at` (2026-10-09 12:53 vs 18:14) |
| Regressor predictions on 20,000 pairs | max difference 3.3e-16 |

Time per step (this PC, Windows, scikit-learn n_jobs=-1): 1 score_sites.py 10 s; 2 make_pair_table.py 5 s; 3 train_rf.py 262 s (spatial 5-fold out-of-fold for the regressor, the classifier and both Decision Trees, then the two final models); total 278 s (about 4.6 min).
(docs/RF_SOURCE.md and CLAUDE.md say "several minutes" / "about 6 minutes": consistent, a little pessimistic.)

Verdict: the score pipeline is fully reproducible from the processed inputs (seed 42): same eligible pairs, same s_prob, same model bytes.
Not covered: the steps before it (ingest_species, rebuild_site_grid, lgu_soil, landcover) were NOT re-run; the scratch copy used the saved site_points_clean.csv / species_clean.csv.

Finding (low risk): after the three steps `scripts/rebuild_scores.py` ends with `final_source()`, which imports `run_plan` -> `field_status.py`, and that reads `frontend/src/new/fieldStatus.json`.
In a copy WITHOUT the `frontend/` folder this last printout fails with FileNotFoundError (the scores are already complete). A normal clone has `frontend/`, so it is not a defect there; noted only.
