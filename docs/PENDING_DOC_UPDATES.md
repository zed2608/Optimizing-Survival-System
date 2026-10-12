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

## Estimating soil for the squares without soil: NOT pursued (decision of 12 Oct 2026, Ayzhiedy)
Considered: use the Random Forest to estimate the soil texture of the squares that have none in the LGU soil map, and compare it with simple baselines. **Decision: the benchmark is not run and no script was written.** The reasons are the read-only findings below (nothing was changed or computed into any file).

**Where the squares without soil are**
- 3,393 of 8,088 grid squares have no soil texture; all of them are scored squares (3,393 of 8,010). 3,392 lie where the digitized LGU map has no coloured pixel (the map leaves the upper watershed white: outside the map, not digitization gaps); 1 is a partial gap. Zoning: 2,173 confirmed and 1,220 outside our zoning map.
- They form ONE block: 3,384 squares (99.7%), plus 9 squares in 4 small blocks (2 single squares, 2 blocks of 2 to 4). By barangay: Pintong Bukawe 3,389 of its 4,591 squares (73.8%), Banaba 3, Silangan 1, the other 12 barangays none.
- Distance of each such square to the nearest square with soil: median 2.1 km (2,059 m), 90th percentile 5.2 km, 99th percentile 7.2 km, maximum 8.1 km; 233 squares within 300 m, 600 within 300 m to 1 km, 1,450 within 1 to 3 km, 1,110 farther than 3 km.
- The land is steeper than the mapped area: median slope 28% against 14% (elevation overlaps: median 215 m against 200 m; 5% of the squares outside the 1st to 99th percentile elevation range of the mapped squares, 3% for slope).
- It is forest land: 2,105 of the squares are in the confirmed Forest Zone (62%), 1,220 lie outside our zoning map and carry the Forest Reserve flag (36%), and only 68 are in other zones (64 Institutional Research, 4 High Density Residential - Mixed Use).

**Classes of the known squares**
- Of the 4,695 squares with soil texture: Clay 3,692 (78.6%), Silt Loam 502, Loam 254, Clay Loam 172, Sandy Loam 75 (imbalance 49 to 1). Only 4,397 come from the map itself; 298 were filled from a neighbour within 300 m (`soil_filled`) and the system treats them as known. Seven series (Antipolo Clay 2,903 down to Novaliches Clay Loam 26).
- Soil follows elevation in the known area: Clay has a median elevation of 267 m, the other four classes 18 to 36 m.

**How the rules treat missing soil today**
- For 44 of the 45 species (the one species that accepts any texture is unaffected) the soil term is NOT evaluated on these squares: the other three terms are re-weighted, the confidence drops, and there is no mismatch penalty. The Random Forest copies this (an "unknown soil" input), so `s_prob` does the same.

**The most an estimate could change (an upper bound, rule S in memory, 152,685 pairs in these squares, 90,120 eligible now; nothing saved)**
- S would change in 52,702 to 86,507 pairs (mean change 0.04 to 0.085, maximum 0.188), depending on the class assumed.
- Eligibility (S >= 0.50) could flip in up to 4,230 pairs (2.8%) in up to 651 of the 3,393 squares (19%); if every square were Clay: 2,253 pairs lost, 238 gained. The Random Forest would need retraining (the rebuild takes about 278 s).

**Why it is not pursued**
- This is not gap-filling but predicting one 34 km² block up to 8 km from the nearest known soil, on steeper land than the model could learn from; the majority class is already 78.6%, so a forest would most likely only reproduce "upland = Clay" (an expectation; it was not tested).
- The white area of the map may be unmapped or mountain soil that is not one of the five classes (UNKNOWN), and the land is forest land (Forest Zone and flagged Forest Reserve), for which the zoning and the MENRO and DENR permits matter more than the texture.
- The LGU soil map is itself provisional (digitized by us, not signed by the agriculturist), so an estimate would stack a guess on a provisional layer and would not improve the survival evidence.
- What stays as it is: squares without soil are scored without the soil term and labelled "Data Unavailable (outside the LGU soil map)"; nothing is estimated or invented.

## Public sandbox link on Render (free plan): built, not yet deployed (13 Oct 2026, branch `deploy-sandbox`)
Procedure: `docs/DEPLOYMENT.md` (click by click, with every item written from memory marked **[RE-CHECK: ...]**). Nothing in CLAUDE.md, README.md, the Help or the user guide mentions it yet; the existing documents were not changed.
- **Public sandbox mode** (`pipeline/public_mode.py`, OFF unless `OS_PUBLIC_MODE=1`): throwaway state in `OS_STATE_DIR` (emptied at start and every 24 h; the real field-check file is never opened), field-check exclusion switch OFF, caps (CSV import 200 KB, 200 plans, 30 kits, 2,000 field events), per-visitor rate limits (plans 20/h, kits 6/h, field checks 60/h, calculations 60/min) plus a global limit of 5 times that, one kit build at a time, `/docs` closed, first-screen notice, 8-source credits list, old-dashboard links hidden. Tests: `tests/test_public_mode.py` (15).
- **One container** (`Dockerfile`, `.dockerignore`, `render.yaml`, `requirements-deploy.txt`, `OS_STATIC_DIR`): the API also serves the built dashboard (`VITE_API_BASE` empty = same address), Python 3.12, port from `PORT`, health check `/health`. The score database travels as `deploy/site_scores.db.gz` (9.8 MB; `scripts/deploy_pack.py` refreshes it; `tests/test_deploy_files.py` fails if it is stale).
- **Numbers (Windows, not Linux):** full suite 735 passed / 1 skipped before Phase 2 and 740 / 1 after on Python 3.14; 735 / 1 on Python 3.12.6. Memory with the runtime packages on 3.12: 185 MB after start, 257 MB after a plan and a kit. Under 10 simultaneous visitors on 3.14 (Phase 1): 222 MB at start, 325 MB after.
- **UNKNOWN until the first deploy:** image size, build time, Linux memory, the visitor-address guess (`OS_TRUST_PROXY_HOPS`), Render's free-plan terms, and the terms of Esri World Imagery, OpenStreetMap tiles and Open-Meteo for a public demo (the credits page says "terms to be checked").
- **Repository facts (checked 13 Oct 2026 without logging in):** `zed2608/Optimizing-Survival-System` is PUBLIC with no licence file. The decisions about a licence, about publishing the LGU files, and about naming LGU staff and the agriculturist's marks are listed in section 1 of `docs/DEPLOYMENT.md` and are NOT taken.
- **Repository findings to settle (13 Oct 2026, nothing decided or changed):** the GitHub repository is public with no licence file; the LGU zoning, boundary, waterways and soil-derived files are published without written permission found in the repository; ten tracked files name LGU staff or contain the agriculturist's marks (listed in section 1 of `docs/DEPLOYMENT.md`); `deploy/` adds the provisional scores to what is public.
