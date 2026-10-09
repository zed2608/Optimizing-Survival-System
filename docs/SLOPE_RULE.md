# Slope rule: graded, not a hard gate (rounds 18 and 18b)

**Status: PROVISIONAL. A team decision. The adviser (licensed agriculturist) confirms next week.** Until then treat every result that depends on it as a guide.

## The unit (checked in round 18b)
Slope is in **percent** everywhere it is scored: the squares (`slope_pct` in `site_points_clean.csv`, rise over run times 100, from finite differences of the elevation grid) and the species table (`max_slope_pct`, raw column `max_slope_percent`, limits from 15 to 70). The grid also keeps `slope_deg`, a derived column (`slope_deg = atan(slope_pct / 100)`, checked for all squares); it is NOT used by any score. 57.7 percent is about 30 degrees; 132.9 percent (the steepest square) is about 53 degrees. Reports, CSV files, the API and the screens speak in percent. A named setting, `STEEP_SQUARE_SLOPE_PCT = 57.7` in `pipeline/score_sites.py`, marks a "steep square" in the reports (it changes no score).

## What changed
Before round 18 a square steeper than a species' limit (`max_slope_pct`) had S = 0 (a hard gate). Now, by default (`SLOPE_MODE = "graded"` in `pipeline/score_sites.py`):

- **Within the limit:** nothing changes. The existing slope term still falls to 0 in the top 10% of the limit.
- **Above the limit:** S is multiplied by a factor that falls linearly from 1 at the limit to 0 at the limit plus a margin of 25% of the limit.
- **Beyond the margin:** the pair is still rejected (hard stop).
- The S >= 0.50 eligibility test still decides what is eligible. W = S x P is unchanged.

Formula: `S = S_soft x g`, `g = 1 - (slope - limit) / (0.25 x limit)` for `limit < slope <= 1.25 x limit`, else the hard stop. `S_soft` is the weighted mean of the four terms as before. At the limit the slope term is already 0, so S is continuous across the limit.

## Why 25% of the limit and not 5 degrees
The data is in percent. A fixed 5 degrees is a very different relative margin for each species: about 20% of the limit for a 70% species, about 60% for a 15% species. A fraction of the limit follows each tree's own tolerance. The fraction is one setting: `SLOPE_GRADED_MARGIN_FRACTION`.

## The switch
`SLOPE_MODE = "hard"` (or `python pipeline/score_sites.py --out data/processed --slope-mode hard`) reproduces the earlier numbers exactly: 249,389 eligible pairs; the output file is byte for byte the old one (`tests/test_slope_mode.py`). `scores/score_run.json` records which mode made the saved scores; `GET /health` shows it as `slope_mode`.

## What it does to the numbers (8,010 squares x 45 species)
Eligible pairs (S >= 0.50): hard 249,389; graded 257,869; newly eligible 8,480 (on 1,508 squares; every species gains); none lost. Every pair that was eligible keeps exactly the same S. The newly eligible pairs are at most 4.4 percentage points (8.3% of the limit) over the species limit. Full report: `data/processed/slope_mode_report.txt`; the list of pairs: `data/processed/slope_graded_newly_eligible.csv` (columns in percent; rebuild with `scripts/slope_mode_report.py`).

**Newly eligible pairs on steep squares (slope above 57.7 percent): 72**, all with S 0.50 or more: Molave 59 (squares at 60.0 to 63.7 percent against a limit of 60 percent) and Clumping Bamboo 13 (70.1 to 74.4 percent against a limit of 70 percent). The steepest square is 74.4 percent. 51 are on confirmed squares (Forest Zone 48, Institutional Research Zone 3) and 21 are outside the zoning map. Each is listed in the report with its point number.

## Tables re-run with the graded rule (round 18b)
The pair table, the model comparison and the matching benchmark were re-run with `SLOPE_MODE = "graded"`. The results made with the hard gate are kept, not overwritten: `data/processed/model_comparison_hard.csv`, `data/processed/matching_benchmark_hard.csv`, `data/processed/scores/pair_table_hard.csv.gz`. Side by side: `data/processed/slope_tables_hard_vs_graded.txt` and `.csv` (`scripts/slope_tables_compare.py`).

| Accuracy (label S >= 0.50) | Random Forest hard | graded | Decision Tree hard | graded |
|---|---|---|---|---|
| random folds | 0.9982 | 0.9976 | 0.9993 | 0.9979 |
| random folds, 5% label noise | 0.9472 | 0.9459 | 0.9408 | 0.9362 |
| spatial folds | 0.9983 | 0.9972 | 0.9973 | 0.9971 |
| unseen species | 0.9700 | 0.9706 | 0.9825 | 0.9729 |
| unseen species, 5% noise | 0.9228 | 0.9210 | 0.9305 | 0.9257 |

Matching, total W of 300 trees (Hungarian = greedy in every purpose and both layouts, in both modes):

| Purpose | points hard | points graded | blocks hard | blocks graded |
|---|---|---|---|---|
| urban | 201.65 | 201.93 | 10.04 (15 blocks) | 10.77 (16 blocks) |
| planting | 172.37 | 180.15 | 6.89 | 7.20 |
| watershed | 184.55 | 184.55 | 6.66 | 6.66 |

The story is unchanged: the Random Forest does not clearly beat the Decision Tree (the gap under label noise grows from 0.6 to 1.0 point, still small), the decision tree and logistic regression stay ahead for unseen species, and Hungarian and greedy tie. The very high accuracy still only shows that the models learn the same rules (CLAUDE.md, known limits).

## Saved plans from the old rule
Nothing was deleted or changed. `scripts/slope_plans_compare.py` repeats every saved request on today's data twice, scored hard and graded (`data/processed/slope_plans_report.txt`). Result: **3 of 15 saved plans would come out different**: `plan_planting_20261005_021813` (about 280 squares replaced, no species change), `plan_urban_20261005_021810` (about 280 squares, no species change) and `plan_watershed_20261005_021824` (about 280 squares, 2 species change). These are the three 300-tree "one tree per square" plans of 5 Oct 2026, which have no saved request, so their request was rebuilt from the summary (purpose, number of trees, seed, points mode): an approximation. The 12 block plans of 6 and 7 Oct are unchanged by the rule. (Compared with today's hard result, 5 of the 15 plans also differ because of other changes since they were made, for example the zone rules.)

## What the user sees
A pair that is eligible only because of the graded rule carries the flag `slope_graded` and this plain caution: "Slope is steeper than this tree's usual limit. Plant on terraces or use contour planting, or choose another tree." It shows:
- in the **verdict card** of the point panel, when that species is the top one (Simple and Detailed);
- as a **line under the species row** in the list (Simple and Detailed) and as a badge in the row's Details;
- in the plan result's **Check first** box ("N of M trees are on squares steeper than the tree's usual limit ..."), with "Show these on the map";
- in the plan items (flag), the block's point panel, and the field kit notes.
Help has the answer "What does the steep slope caution mean?"; the tour's point step and the Site match glossary entry mention it.

## Not changed
`species_clean.csv`, `species_sources.csv` and the printed sample sheet files are untouched. The agriculturist sample (`scripts/score_agri_sample.py`) is scored with `SLOPE_MODE = "hard"`, as it was printed (see `docs/SAMPLE_VALIDATION_RESULT.md`).
