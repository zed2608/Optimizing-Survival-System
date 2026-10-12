# Pending documentation updates

Decisions already taken that are NOT yet written into the user-facing documents. Nothing here has been applied.

## Wording of the "potential" layer (decision of 12 Oct 2026, Ayzhiedy)
- If a layer built from satellite tree cover is ever used or mentioned, call it only **"environmental support for woody cover (satellite-derived, provisional)"**.
- It is **not** a survival measure and must never be described as one.
- It uses the model's *predicted* value from the environment (elevation, slope, soil), never the observed tree cover, and never penalises open land by its observed cover.
- No gap or restoration score for now.

Status: the pre-registered benchmark (`docs/defense/POTENTIAL_BENCHMARK.md`, 12 Oct 2026) says DROP; no screen, Help text, README or CLAUDE.md sentence uses the term yet. If the layer is built later, the wording above has to be added to Help and the user guide, `README.md`, `CLAUDE.md`, `docs/defense/ALGORITHMS.md`, `LIMITATIONS.md` and `PANEL_QA.md`.

## Potential layer: verdict of the pre-registered benchmark (12 Oct 2026): DROP
Accepted by Ayzhiedy. Steps 4 to 7 (the switch, labels, outputs) are NOT built. No rule or setting may be changed to alter the verdict; a different setup would be a new, labelled run. The rules, thresholds and the numbers below are pinned by `tests/test_potential_benchmark.py`. Source: `docs/defense/POTENTIAL_BENCHMARK.md`, `scripts/potential_benchmark.py`.

**The three rules and the numbers**
- **R1 (forest at least 0.10 R-squared above EACH of Decision Tree, linear regression and KNN, and better in at least 4 of 5 folds): FAILED.** Forest above the Decision Tree by +0.040 and above KNN by +0.084 (needed 0.10); above linear regression by +0.158 (passes); better than each of them in 5 of 5 folds.
- **R2 (forest R-squared of the main model, environment only, at least 0.30): FAILED at 0.29999** (folds 0.067, 0.354, 0.614, 0.337, 0.128; standard deviation about 0.22). The drop does not depend on this rounding: R1 fails by a wide margin.
- **R3 (|Spearman| with the rule score at most 0.80): passed at -0.221** (-0.315 with the number of eligible species).

**The 430-square finding (descriptive, not a drop rule).** On the 430 squares with tree cover below 0.5 (grassland and cropland) the forest's predicted potential separates them from the rest with an AUROC of 0.865. The lowest 10% of predicted potential holds 38.8% low-cover squares (base rate 5.9%) and catches 66.0% of all of them; the mean predicted potential is 0.66 for them and 0.95 for the others. So even a prediction from elevation, slope and soil tracks where open land already is, which conflicts with "never penalize open land".

**The decision-gate numbers (rf source, Hungarian, nothing built; 534 barangay plans and 893 drawn-polygon plans).**
- Placed blocks and trees changed in 0 of 1,427 plans in every variant (by construction: S and the 0.50 test are untouched).
- Tie-break: 5,519 of 10,167 blocks (54.3%) of barangay plans and 3,698 of 9,247 (40.0%) of polygon plans moved to other squares; total W change 0.0000%; the blocks spread out (mean distance from the area centre 1.67 and 1.50 times larger); 89.4% and 80.7% of chosen blocks have another equally scored square.
- adjust_w factors 0.05 / 0.10 / 0.20 (none chosen): 41% to 49% of blocks moved; total W -0.009% / -0.024% / -0.034% (barangay plans) and -0.002% / -0.003% / -0.005% (polygon plans); worst single plan -1.5%.

**The sentence we can keep:** "a nonlinear model predicts real tree cover clearly better than a linear one, but the forest is not clearly better than a single tree or KNN."

**Do not quote the R-squared of 0.435.** The estimate of 0.435 (0.405 without latitude and longitude; Decision Tree 0.066 and 0.252; linear 0.282) in section 4b of `docs/HANDOFF_2026-10-12.md` came from a rougher setup in the chat session (an untuned fixed-setting run that used `nearest_feature_dist_m` and 7,392 squares). The registered benchmark gives 0.300 for the forest on 7,322 squares. The handoff is historical and was left unchanged.
