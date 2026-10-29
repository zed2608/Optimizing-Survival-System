# Testing / Scenario 1 — Result (panel §9, revision defense 3 Nov 2026)

The panel's ask: a documented test run with **actual output**, not a description of the test plan — plus a clear answer on the
train/val/test split used and a "no mock data" confirmation. Every number below is read directly from files already produced by
the pipeline (cited by path), nothing is recomputed or estimated for this document.

## 1. No mock data — what was actually used

- **Species data**: `data/raw/species_directsource.csv` (45 species) and `data/raw/sources_list.csv` (350 lines), collected by hand
  from named, checkable sources (Stuart Xchange, PROSEA/PROTA4U, university extension/campus-flora pages, DENR/agriculture
  references — one source URL inline per field, not a bulk citation). Frozen and hashed as release `v1.0-review`
  (`data/processed/dataset_release.txt`): species file sha256 `13787b81…`, sources file sha256 `88edfb30…`, combined hash
  `34964a09fe44`. 2,347 cited cells; every ingest issue is counted and kept (34 cells cite a source PDF not supplied, 30 cite a
  source outside the supplied list, etc. — flagged, never silently dropped or replaced with a guess).
- **Site data**: `backend/Working_Points.csv`, 8,255 real surveyed points (San Mateo, Rizal), rebuilt into an 8,088-square,
  ~100 m grid (`pipeline/rebuild_site_grid.py`) against the real `data/LandUses.shp`, `data/BRGY_BOUNDARY.shp` and
  `data/SMR_WATERBODIES_POLY.shp` shapefiles, plus the LGU's own digitized soil map (round 11) and ESA WorldCover 2021 satellite
  land cover (round 8, DOI 10.5281/zenodo.7254221).
- **The pair table the model trains on**: `data/processed/scores/pair_table.csv.gz`, 360,450 real (square x species) pairs
  (8,010 scored squares x 45 species) — every row traces back to one of the two real inputs above through
  `pipeline/make_pair_table.py`. No synthetic point, synthetic species, or placeholder label was used anywhere in this table.

## 2. The train/val/test split actually used

The panel heard both **80/20** and **70/15/15** mentioned in different parts of the exchange. The honest answer is neither single
split by itself — the real procedure (`pipeline/compare_models.py`, `pipeline/train_rf.py`) is **nested nested cross-validation**,
which is a stronger test than one static split because every pair gets scored by a model that never saw it in training, not just
the one held-out slice:

- **Outer loop — 5-fold spatial `GroupKFold`** (`CFG["outer_folds"] = 5`, groups = ~1 km spatial blocks, `spatial_block_cells = 10`):
  each fold trains on 4/5 of the blocks (80%) and tests on the held-out 1/5 (20%) — so every number in the table below **is** an
  80/20 split, repeated 5 times so every pair is tested exactly once (out-of-fold), never on the same blocks it trained on.
  Grouping by spatial block (not by individual square) matters here: without it, two 100 m-apart squares could land in different
  folds and leak almost-identical neighbourhood information between train and test, inflating the score. The spatial setting
  below is the conservative, leakage-resistant number; the plain `random` setting is reported alongside it to show how much a
  naive random split would have overstated performance.
- **Inner loop — 3-fold cross-validation for hyperparameter tuning** (`CFG["inner_folds"] = 3`), run only on each outer fold's own
  80% training portion, never touching that fold's 20% test portion. This inner split is what the "70/15/15" figure was likely
  gesturing at: within the 80% training portion, roughly two-thirds is used to fit each candidate and one-third to score it
  (≈53% / 27% of the original data), before the single best hyperparameter setting is refit on the full 80% and scored once on
  the untouched 20%. Four hyperparameter candidates were tried per model (`CFG["grids"]`), an identical tuning budget across all
  four models compared.
- **Scope of this comparison**: a stratified subsample of 30,000 pairs (`CFG["subsample_n"] = 30000`) out of the 360,450 real
  pairs, for runtime — the production Random Forest actually deployed (`pipeline/train_rf.py`) is separately retrained and
  evaluated on **all 360,450 real pairs**, same 5-fold spatial `GroupKFold`, same out-of-fold discipline (section 4 below).

## 3. Result — model comparison, spatial (leakage-resistant) holdout, no label noise

Source: `data/processed/model_comparison.csv` (read directly, no recomputation), `setting="spatial"`, `noise=0.0`, mean ± std over the 5 outer folds, n=30,000 pairs each.

| Model | Accuracy | Precision | Recall | F1 | ROC AUC | Brier |
|---|---|---|---|---|---|---|
| **Random Forest** | 0.9972 ± 0.0015 | 0.9969 ± 0.0018 | 0.9990 ± 0.0006 | 0.9980 ± 0.0012 | 0.9997 ± 0.0006 | 0.0050 ± 0.0027 |
| Decision Tree | 0.9971 ± 0.0010 | 0.9979 ± 0.0013 | 0.9980 ± 0.0008 | 0.9980 ± 0.0007 | 0.9972 ± 0.0015 | 0.0027 ± 0.0009 |
| Logistic Regression | 0.9838 ± 0.0022 | 0.9870 ± 0.0031 | 0.9903 ± 0.0032 | 0.9886 ± 0.0020 | 0.9956 ± 0.0021 | 0.0169 ± 0.0018 |
| KNN | 0.9651 ± 0.0039 | 0.9659 ± 0.0110 | 0.9858 ± 0.0050 | 0.9757 ± 0.0037 | 0.9948 ± 0.0016 | 0.0283 ± 0.0020 |

**Reading this honestly** (the same honesty this project has applied everywhere else — see `CLAUDE.md`'s round 19 "HONEST" note):
Random Forest and Decision Tree are statistically indistinguishable here (within one standard deviation of each other on every
metric); the label itself (S ≥ 0.50) is produced by the project's own expert rules, so this measures how well each model
*reproduces the rules*, not an independent measurement of real-world tree survival — no such ground-truth survival dataset exists
for San Mateo yet (that is exactly what round 22's survival-monitoring feature starts collecting going forward).

### Harder test: unseen species (never seen during training, any fold)

Source: same file, `setting="species"` — an even stricter holdout where whole species, not just whole squares, are held out of training.

| Model | Accuracy | Precision | Recall | F1 | ROC AUC |
|---|---|---|---|---|---|
| Decision Tree | 0.9729 ± 0.0233 | 0.9705 ± 0.0297 | 0.9923 ± 0.0057 | 0.9811 ± 0.0165 | 0.9686 ± 0.0349 |
| Random Forest | 0.9706 ± 0.0245 | 0.9698 ± 0.0309 | 0.9887 ± 0.0096 | 0.9790 ± 0.0179 | 0.9809 ± 0.0351 |

Both models hold up reasonably on species they never trained on (still above 0.97 accuracy), with wider variance across folds
than the spatial setting above — expected, since a 5-species-per-fold holdout is a much smaller, noisier test than a
square-block holdout over 360,450 pairs.

## 4. Result — the production model (all 360,450 real pairs, out-of-fold)

Source: `data/processed/rf_vs_dt_oof.csv` and `data/processed/rf_vs_rules_report.txt` section 4 (slope mode: graded, round 18).

| Model | Accuracy (OOF) | Precision | Recall | F1 | ROC AUC | Fold accuracy (mean ± std) |
|---|---|---|---|---|---|---|
| **Random Forest (deployed, after hard gates = `s_prob`)** | 0.99958 | 0.99953 | 0.99988 | 0.99971 | 0.99991 | 0.99956 ± 0.00026 |
| Random Forest (raw, before hard gates) | 0.99955 | 0.99949 | 0.99988 | 0.99969 | 0.99991 | 0.99954 ± 0.00026 |
| Decision Tree | 0.99945 | 0.99950 | 0.99974 | 0.99962 | 0.99923 | 0.99943 ± 0.00040 |

The regressor that actually produces the deployed `s_prob` column: **MAE 0.00059, R² 0.99981** against the rule score S
(out-of-fold, same 5 spatial folds). 257,929 of 360,450 pairs are eligible (S ≥ 0.50) under the forest versus 257,869 under the
rules directly — a 0.047% difference (168 pairs), Spearman rank correlation 0.9940. The matching benchmark (`rf_vs_rules_report.txt`
section 3b) confirms this difference almost never changes which plan gets built: six real plans (urban/planting/watershed x
points/blocks, 300 trees each) built with the forest's scores lose at most **0.04%** of total W when judged back against the
rules, well inside the project's own 2% "success test" threshold.

## 5. What this does *not* yet show

- No field-measured survival outcome yet exists for San Mateo to test the model against — this comparison is internal
  consistency (does the model reproduce the expert rules it was trained to approximate), not external validation against real
  tree survival. Round 22/23's survival-monitoring feature (`pipeline/survival.py`, the 85%-at-1-year provisional threshold cited
  to DENR's National Greening Program requirement) is what starts collecting that ground truth going forward, honestly labelled
  provisional until the agriculturist confirms it for this project's own species and sites.
- The one-reviewer, 40-pair agriculturist sample validation (`data/validation/agri_sample_marks_20261007.csv`,
  `docs/SAMPLE_VALIDATION_RESULT.md`) is a separate, smaller, human-expert spot-check — not reproduced here; cite it separately
  if asked about expert agreement specifically (69.4% / 66.7% depending on how "Marginal" is scored, kappa 0.00 / 0.21 — openly
  reported as a thin, single-reviewer sample, not a claim of strong validation).

## Reproduction

Every number above is read verbatim from these already-committed files (no `pytest`/`fastapi` needed, pure pandas):
`data/processed/model_comparison.csv`, `data/processed/rf_vs_dt_oof.csv`, `data/processed/rf_vs_rules_report.txt`,
`data/processed/dataset_release.txt`. The settings that produced them are the module-level `CFG` dicts of
`pipeline/compare_models.py` and `pipeline/train_rf.py` (`RF_CFG`/`REG_CFG`), unchanged since the round 9 refresh noted in
`CLAUDE.md`. To regenerate from scratch: `python scripts/rebuild_scores.py` (needs `geopandas`/`shapely`/`pyproj`, not available in
this sandbox — confirmed blocked here; run it in the real project environment) then `python pipeline/compare_models.py`.
