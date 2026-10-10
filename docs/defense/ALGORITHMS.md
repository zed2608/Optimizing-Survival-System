# Algorithms: what each one does, where it lives, and what it really shows

Written on 10 Oct 2026 from the code and the saved data (no figure is from memory; every figure is also in `NUMBERS.md` with its source file). Everything about weights, margins, caps and thresholds is **provisional** until the licensed agriculturist signs it off. Nothing here is validated against field survival: there is no survival data.

Order of the live pipeline: **rule score S -> Random Forest s_prob (the S the app uses) -> purpose fit P -> W = S x P -> palette (species mix) -> Hungarian matching (species slots to squares) -> blocks -> field kit with a check code.**

---

## 1. Rule scoring of site suitability S (the labels)
- **Purpose.** For every 100 m grid square and each of the 45 species, say how well the land suits the species, 0 to 1, from the species' own limits.
- **Inputs.** Square: elevation `elev_m`, slope in percent `slope_pct`, LGU soil texture `soil_texture_lgu` (provisional), distance to the nearest creek or river polygon `water_dist_m`, zoning status. Species: `elev_min_m`, `elev_max_m`, `max_slope_pct`, soil texture list, waterlogging tolerance (Low / Medium / High = 0 / 0.5 / 1).
- **Output.** `s_rule` (0 to 1), `confidence` (share of the weight that could be evaluated), per-term values and flags (`slope_graded`, `soil_provisional`), in `data/processed/scores/site_scores.csv` and `.db` (git-ignored).
- **Method.** Hard gates make S = 0: zone is `excluded`, elevation outside the species range, slope beyond the limit (see graded rule below). Four soft factors in [0,1], each weight 0.25: elevation (falls linearly over the outer 10% of the range), slope (falls over the top 10% of the limit), soil (1 on a texture match, 0.25 on a mismatch in "soft" mode, not evaluated if the square has no texture), wetness (waterlogging tolerance level, relaxed linearly to 1 at 50 m from a creek or river). S = weighted mean of the factors that could be evaluated. **Graded slope rule (round 18, `SLOPE_MODE = "graded"`):** above the limit S is multiplied by 1 - (slope - limit) / (0.25 x limit); beyond limit x 1.25 the pair is rejected. A pair is eligible when S >= 0.50.
- **Key parameters.** `TERM_WEIGHTS`, `MARGIN_FRACTION` 0.10, `SLOPE_GRADED_MARGIN_FRACTION` 0.25, `SOIL_MISMATCH_FACTOR` 0.25, `WETNESS_RISK_DISTANCE_M` 50, `SOIL_COMPAT`, `ELIGIBLE_S` 0.50. None has a source; all are team proposals.
- **Where.** `pipeline/score_sites.py` (`score_pairs`, `distance_to_water`, `build_breakdown`); run by `scripts/rebuild_scores.py` step 1.
- **In the app.** "Why this score?" (terms, weights, source links), the verdict card, the grey "why few species suit this square" card (`limiting_factors` in `/rank`).
- **Headline numbers.** 8,010 squares x 45 species = 360,450 pairs; 257,869 eligible with the graded rule (249,389 with the old hard gate; 8,480 pairs are eligible only because of the graded rule, 72 of them on squares steeper than 57.7%: Molave 59, Clumping Bamboo 13); the wetness term lowers S for 2,960 pairs; 3,393 squares have no soil texture so their soil term is not evaluated.
- **Honest reading.** These are expert thresholds taken from the species data, not measured survival. NOT scored: pH, rainfall, temperature, canopy, exposure (no real layer).

## 2. Purpose fit P
- **Purpose.** How well a species suits the goal (urban greening, tree planting, watershed), 0 to 1, independent of the square.
- **Inputs.** Species traits and tags; weights in `data/config/purpose_weights.csv` (6 criteria for urban and planting, 7 for watershed, each purpose summing to 1.00; all `weight_provisional`).
- **Output.** `data/processed/purpose_scores.csv` (P per species per purpose, with breakdown and confidence); `purpose_sensitivity.csv` (76 weight scenarios).
- **Method.** Each criterion is scored from species columns by explicit rules (`COLUMN_SCORERS`; ordinal levels, tag present/absent, text rules). A missing or unreadable value scores the neutral 0.5, is marked missing and lowers the confidence (never guessed). P = weighted sum.
- **Where.** `pipeline/score_purposes.py` (`component_scores`, `score_species`, `aggregate`, `sensitivity`).
- **In the app.** The "Purpose fit" number, "Why this score?" purpose table, the purpose picker.
- **Combination.** W = S x P if S >= 0.50, else 0 (`matching.weights`). In four Habagat barangays (Maly, Dulong Bayan I and II, Santa Ana) W is multiplied by 0.8 when the planting window touches July to September (`site_rules.HABAGAT_CFG`, MAO interview).
- **Honest reading.** The criteria and weights are our proposals; the sensitivity file shows how ranks move when weights change, not that they are right.

## 3. Random Forest regressor (the S the app uses by default)
- **Purpose.** Predict the rule score S from the raw site and species values, out of fold, so the live S is a model prediction (`s_prob`).
- **Inputs.** The pair table `scores/pair_table.csv.gz` (`pipeline/make_pair_table.py`): 20 raw features: elevation, slope, distance to water, the species elevation and slope limits, waterlogging level, soil flags (site texture one-hot, species texture one-hot). Target: `s_rule`. These are the same raw values the rules read, so the forest relearns the rule formula.
- **Output.** `s_prob` = clip(prediction, 0, 1), set to 0 where `s_rule` = 0 (hard gates kept); model files in `data/processed/models/` (git-ignored); `rf_site_suitability_meta.json`.
- **Method.** `RandomForestRegressor`, 200 trees, no depth limit, at least 2 pairs per leaf, seed 42. Spatial out-of-fold: 10 x 10-cell (about 1 km) blocks, GroupKFold with 5 folds (the folds of `compare_models.py`); every pair gets the prediction of the model that did not train on its block. A classifier (S >= 0.50) is also trained and reported but does not make `s_prob`.
- **Where.** `pipeline/train_rf.py` (`spatial_folds`, `oof_predictions`, `apply_hard_gates`); source switch `matching.S_SOURCE = "rf"` (`OS_S_SOURCE`, `API_CFG["s_source"]`); automatic fallback to the rules with `Context.s_warning` and a `/health` warning when `s_prob` is missing.
- **In the app.** Every ranking, grid colour, area table and plan; the "Suitability from the Random Forest: 0.83. Rules check: passed." line in "Why this score?" (Detailed view).
- **Headline numbers.** Out-of-fold MAE 0.00059, R-squared 0.9998 (Decision Tree regressor 0.00061 / 0.9997); 257,929 eligible pairs against 257,869 for the rules, 168 pairs differ (54 rules-only, 114 forest-only); Spearman 0.994; the saved model rebuilds identically (round 20 Part A: s_prob and the model file are byte identical after a rebuild from scratch, 278 s).
- **Honest reading.** It copies the rules (R-squared 0.9998) and is **not an independent measurement of survival**. Its only effects: it smooths the sharp edges of the rules slightly and changes 0.047% of the eligibility decisions.

## 4. Decision Tree comparison
- **Purpose.** Check whether a forest is worth its complexity compared with simpler models, on the same labels and folds.
- **Inputs / method.** `pipeline/compare_models.py`: 30,000-pair stratified subsample, 5 outer folds, 3 inner folds for tuning (4 candidates per model, scoring ROC-AUC), models Random Forest, Logistic Regression, KNN, Decision Tree, plus calibrated RF; settings random folds, spatial folds (1 km blocks), unseen-species folds; label noise 0 and 0.05.
- **Output.** `data/processed/model_comparison.csv` (and the `_hard` copy made with the old slope gate); `rf_vs_dt_oof.csv`, `rf_vs_dt_regression_oof.csv` for the full-data out-of-fold comparison inside `train_rf.py`.
- **Headline numbers (accuracy, clean labels).** Random folds RF 0.9976 / DT 0.9979; spatial folds 0.9972 / 0.9971; unseen species RF 0.971, DT 0.973, LR 0.979 (spread about 0.02). With 5% flipped labels RF 0.946 against DT 0.936 (spread 0.001 to 0.003): the forest is ahead only when the labels are noisy.
- **Honest reading.** The labels are deterministic threshold rules; a tree represents thresholds exactly, so a tie is expected. The comparison measures how well models copy the rules, not survival.

## 5. Hungarian assignment (the matching)
- **Purpose.** Assign species slots to grid squares so the total W is as large as possible.
- **Inputs.** Matrix W (species x squares) from S (or `s_prob`) and P; a slot count per species (the quotas of the palette); feasibility S >= 0.50; area mask; field-check exclusions.
- **Output.** One square per slot, no square used twice (`assign_hungarian` returns point and species index per slot). Cost = 1 - W; infeasible pairs cost 1e6; a tiny tie-break term (weight 1e-6) prefers squares near the centre of the area.
- **Method.** `scipy.optimize.linear_sum_assignment` on the slots x squares cost matrix.
- **Where.** `pipeline/matching.py` (`assign_hungarian`), called from `pipeline/run_plan.py` (`make_plan`, `_finish_blocks`) and through `POST /plan-event` in `api_v2.py`.
- **In the app.** Step 5 "Create plan", the plan result, Campaign Logs, the field kit.
- **Headline numbers.** `matching_benchmark.csv` (300 trees, whole municipality): urban points 201.93, planting 180.15, watershed 184.55 total W; blocks 10.77 / 7.20 / 6.66 (16 / 12 / 11 blocks). Hungarian equals greedy in all six cases (largest gap 0.000000). Time for a 300-tree plan in the browser (Guinayang, blocks): 0.45 to 0.52 s.
- **Honest reading.** The optimal solver gives no gain over the greedy baseline in any of the six benchmark cases. Our explanation (a reading, not tested separately) is that there is little competition between species for squares: many squares share the top S, so greedy never has to give up a good square. Hungarian stays in the system because it is exact and would matter when squares are scarce, but this thesis cannot claim that it beat greedy.

## 6. Greedy baseline (and random baselines)
- **Purpose.** The simple comparison for the Hungarian solver.
- **Method.** `assign_greedy`: repeatedly take the best remaining feasible (square, species) pair that still has quota, mark the square used (equal W: nearest to the area centre first); `assign_random` with `respect_feasible` True ("random feasible") or False ("random blind", which breaks the rules: 45 / 32 / 22 rule breaks per 300 trees in points mode).
- **Where.** `pipeline/matching.py`; benchmark in `pipeline/run_plan.py` (`run_benchmark`) -> `matching_benchmark.csv`.
- **Numbers.** Random feasible loses 5.6 to 9.0% of total W against Hungarian (urban points 190.69 against 201.93, watershed 168.00 against 184.55); greedy loses nothing.

## 7. Palette (species mix) and tree counts
- **Purpose.** Choose which species and how many trees each when the user only gives a total.
- **Method.** `palettes.build_palette`: 6 to 10 species, at most 20% of the trees per species and 30% per genus (caps are team proposals with no source), dioecious species at least 2 trees (both sexes), common planting months (window cut), spacing at least the grid spacing excluded. With `species_counts` the user's exact counts are placed (`fixed_palette`; no caps; warnings for one species or 80% in one species).
- **Where.** `pipeline/palettes.py`, `pipeline/run_plan.py`.

## 8. Block geometry
- **Purpose.** Turn "300 trees" into a number of 100 m squares with a drawn layout the field team can lay out.
- **Method.** Planting distance = midpoint of `spacing_min_m` and `spacing_max_m` rounded to 0.5 m; rows = trees per row = floor(usable side / spacing), usable side 100 x sqrt(0.6) = 77.46 m, capacity = rows x trees per row; `block_geometry`: planted rectangle = n x spacing, centred in the square, trees at cell centres from the south-west, east first; slope above 30% adds "Plant along the contour". Blocks per species = ceil(trees / capacity); the worst-W matched square holds the remainder.
- **Where.** `pipeline/palettes.py` (`species_spacing`, `block_layout`, `block_geometry`, `block_table`), `pipeline/run_plan.py` (`_finish_blocks`), JavaScript mirror `frontend/src/new/blockGeometry.js`, `pipeline/field_kit.py` (`attach_geometry`).
- **Numbers.** 300 trees = 15 / 12 / 13 blocks (urban / planting / watershed, Guinayang); Kamagong 12.5 m, 36 trees per block; since round 21 the form's estimate is the real rule (`/plan-event/preview` runs the same `make_plan` as Create plan and reports its blocks, e.g. "About 14 blocks of 21 trees" for Santa Ana urban); before, it used the median block size (64 trees) and understated the real number 2.4 to 3 times.
- **Honest reading.** The 60% usable share, the 0.5 m rounding and the north alignment of the grid (assumed UTM north) are assumptions; nothing was laid out with a real GPS.

## 9. Partner-species rules ("Works well with")
- **Purpose.** Suggest species that can grow together.
- **Method.** `pipeline/partners.py` (`pair_rules`, `build_partners`; thresholds in `PARTNER_CFG`): a pair (main A, partner B) is listed if the suitable squares overlap (>= 50% of the smaller set, S >= 0.50, >= 2 shared planting months), no High-against-Low clash in drought or waterlogging tolerance, roots (not both under 0.4 root urban safety), and layering (B at most 60% of A's height and shade tolerance Medium or High) OR B's name is written in A's `plant_partners` text. A waterlogging mismatch on land within 50 m of water is only a caution. Score = 0.35 layering + 0.25 overlap + 0.15 water + 0.10 roots + 0.15 named. Pairs named in the sources but failing the rules are labelled "named in the sources, conditions differ".
- **Output.** `data/processed/species_partners.csv`: 164 fitting pairs for 40 of 45 species, plus 3 named pairs with differing conditions. `GET /species/{id}/partners`.
- **Honest reading.** Starting rules, provisional, not verified in the field; name matching is word-based.

## 10. Plan check codes
- **Purpose.** Let the field team prove that a printed or filled sheet belongs to one exact plan.
- **Method.** `field_kit.check_code(plan_csv_path)` = the first 8 hexadecimal characters of the sha256 of the saved plan CSV; printed in the kit README, the PDF footer, `blocks.csv` (trailing `check_code`) and the kit details in the dashboard. The PDF footer also carries the release tag and the 12-character dataset hash.
- **Where.** `pipeline/field_kit.py` (`check_code`, `sha256_file`).
- **Honest reading.** It detects a changed plan file; it is not a signature (no key) and is only 32 bits.

## 11. Other rules that never change a score
- **Survival advice** (`pipeline/advice.py`, `data/processed/survival_advice.csv`): text only, 8 rules, provisional.
- **Ground-cover flags** (`pipeline/landcover.py`): bare / built-up / water from ESA WorldCover 2021 (76.7% accurate worldwide); information only.
- **Rehabilitation food warning, zone conditions** (`pipeline/site_rules.py`): warnings only.
- **Season filter** (`api_v2.py`, `pipeline/palettes.py`): month granularity; scores do not depend on the dates, except the Habagat multiplier on W above.
