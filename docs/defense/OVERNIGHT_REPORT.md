# Round 20 overnight report (audit and defense documents), 10 Oct 2026

No feature was added. No default was changed (`S_SOURCE` stays "rf", `SLOPE_MODE` stays "graded"). Nothing was committed. `species_clean.csv`, `species_sources.csv` and the printed sample sheet files were not touched. Nothing outside `docs/defense/` was created; edits to existing files are limited to plain-text documentation (listed at the end).

## 1. What passed and what failed, by part
| Part | Result |
|---|---|
| A Reproducibility | **PASS.** A rebuild from scratch in a scratch copy gives the same `s_rule` and `s_prob` (max and mean difference 0), the same eligible pairs (257,869 rules, 257,929 rf), a byte-identical model file, byte-identical `site_scores.csv`; only the gzip header of the pair table differs (content identical) and `trained_at` in the meta file. Times: 10 s + 5 s + 262 s = 278 s. Not covered: the steps before scoring (ingest, grid, soil, land cover). Details: `_partA_reproducibility.md`. |
| B Demo run-through (rf, Guinayang) | **PASS** (after fixing 4 mistakes of my own script). Three purposes, Simple and Detailed, blocks layout, "Why this score?" with the forest line, species card, advice panel, field check "Planted", progress, field kit (7.2 s, zip with blocks.csv, GPX, KML, README, PDF), Help search, **tour (24 steps, not 23)**: 0 console errors, 0 failed network calls. Time to a 300-tree plan: 0.52 s urban, 0.45 s planting, 0.46 s watershed (15 / 12 / 13 blocks). The points layout is not offered on screen (API only). Details: `_partB_demo_run.md`; 46 screenshots in `C:\Users\user\Desktop\Optimizing_Survival_Screenshots\round20\`. |
| C Defense documents | **DONE.** ALGORITHMS.md, LIMITATIONS.md, NUMBERS.md (generated from the data files by `make_numbers.py`, 64 rows), PANEL_QA.md (30 questions). |
| D Consistency audit | **DONE; 2 high-risk statements found** (below). Plain-text documentation errors were fixed; code and UI text were only listed. |
| E Robustness | **PASS.** Three full pytest runs: 661 passed, 1 skipped each time, no flaky test. qa_day1 34 passed / 0 failed. Clean start of the API: `/health` after 4.2 s, rf, no warning; 191 MB working set at start; main endpoints 0.001 to 0.12 s warm. |
| F Edge cases | **PASS with 2 findings.** 51 API calls and the screen: no crash, no 5xx. Plain sentences everywhere on the screen; direct API calls with invalid bodies return FastAPI's default validation list (19 of 51). The fallback (s_prob missing) works but the dashboard shows no notice. Details: `_partEF_robustness_edge_cases.md`. |

Final run after all edits: pytest 661 passed, 1 skipped (270 s); qa_day1 34 passed, 3 warnings, 0 failed; `npm run build` OK; `npx eslint src/new` no problems; 7 node test files all pass; `node scripts/build_user_guide.mjs --check`: up to date.

## 2. Issues found, ranked by risk to the defense

### HIGH
1. **Help text, tour, user guide say the creeks and the 50 m wetness rule "are not used", but the scoring uses a wetness term.** `frontend/src/new/tutorial/tutorialContent.js` lines 277 and 343 (and `docs/USER_GUIDE.md` lines 191 and 431, generated from them): "The waterways form was signed blank, so creeks and the 50 metre wetness rule are not used." In `pipeline/score_sites.py` the wetness term (weight 0.25, 50 m from the CREEK / RIVER polygons) is evaluated for all 360,450 pairs and lowers S for 2,960. The form's answers are indeed not used, but the sentence reads as if the scoring ignores creeks. A panel member who opens "Why this score?" and sees "Wetness 25%" will catch it. **Not changed** (UI text and a generated guide). Suggested fix: reword both sentences to say the waterways form is unvalidated but the system's own wetness rule (50 m, provisional) is used, then `node scripts/build_user_guide.mjs`. The plain-text note in `docs/INTERVIEW_FINDINGS.md` was corrected.
2. **The fallback to the expert rules is silent on screen.** With `s_prob` missing the API warns correctly (`/health`) but the dashboard shows no notice (main screen, point panel, System Analytics all checked; there is no `s_source` in `frontend/src`), and Help still says the site match "is predicted by a Random Forest". A fresh clone (scores and model are git-ignored) starts exactly in this state. Suggested fix: show `s_source_warning` as a banner and in System Analytics. Not changed (feature).

### MEDIUM
3. **The plan form's estimate understates the number of blocks 2.4 to 3 times** ("About 5 blocks of 64 trees" for 300 trees; real plans 12 to 15 blocks, `blocks_estimate` uses the median block size). Expect the question in the demo; `docs/DEMO_SCRIPT.md` now warns about it.
4. **"Known limits" strings still say S comes from rules**: `api_v2.py:124` ("Suitability S comes from rules written from the species dataset...") and `pipeline/run_plan.py` LIMITS ("S comes from rules, not from field survival data."), shown in the app and in plan results. True in spirit (no field data) but they do not mention the forest. Not changed (code).
5. **Planned blocks can lie on land that looks built up** (Guinayang screenshot `on_08_...png`). Scores do not see buildings; ground-cover flags are information only (76.7% accurate worldwide). The field check is the safeguard; say so.
6. **Direct API calls return FastAPI's default validation list** for invalid bodies (19 of 51 edge calls: `type`, `loc`, `input`, readable `msg`). The dashboard never sends such input. Not changed.
7. **The 40-pair sample cannot support a validity claim** (one reviewer, 36 judged, no "Not suitable" marks, kappa 0.00 / 0.21). Documented in LIMITATIONS.md and PANEL_QA.md.
8. **Model comparison wording**: the claim "the forest is not clearly better than the decision tree" holds on clean labels only. With 5% flipped labels the forest leads by about one point (0.946 against 0.936; spread 0.001 to 0.003). DEMO_SCRIPT.md now says so; CLAUDE.md round 9 text and `docs/RF_SOURCE.md` use the short version.

### LOW
9. The tour has 24 steps (the brief said 23); 6 steps are centred cards because their element needs an open card or plan.
10. Legacy: `#/legacy` and `backend/app.py` mix slope units (degrees only when the value is above 90); 25 root-level scripts (`api.py`, `optimization.py`, `train_model.py`, `generate_targets.py`, ...) are legacy; the live code does not import them (a test asserts `api_v2.py` does not import `api`). Left alone as instructed.
11. `scripts/rebuild_scores.py` ends with a printout that imports `run_plan` and fails in a copy without the `frontend/` folder (FileNotFoundError for `fieldStatus.json`); the scores are already complete. Not an issue in a normal clone.
12. The API worker had a 5 GB working set after a long session of plan and kit requests (not measured further; 191 MB at start). UNKNOWN whether it grows without limit.
13. Points layout of 2000 trees returns the warning "caps_cannot_absorb_all_saplings: 600 of 2000 saplings allocated ..." with a code word (API / command line only; the dashboard uses blocks and plain words).
14. Historical sections of CLAUDE.md and `docs/FOUR_DAY_PLAN.md` keep the numbers of their round (338,850 pairs, 7,530 squares, 228,919); they are labelled by round, not by "now". `README_DAY1.md` is Day 1 history.
15. No TODO, FIXME or "MCE" text anywhere in code and docs. Slope is percent everywhere in the live system; `slope_deg` is derived and used by no score.

## 3. Documentation errors fixed (plain text only)
- `README.md`: 7,530 scored squares -> 8,010 (6,731 + 1,279) and S described as the forest's prediction by default; test counts (661, 4 to 7 minutes; pinned counts 8,010 and 257,869).
- `docs/DEMO_SCRIPT.md`: the areas ranking of step 3 (Santo Nino 37 squares, Gulod Malaya 114, Guitnang Bayan II 0.67, Silangan 0.64), the 5474 message (new wording of the graded rule), "Full details" -> "Detailed" with the forest line, the System Analytics numbers (8,010 + 78), the zoning answer (78 never scored), the model answers (0.9976, forest is now the live S, tie on clean labels, ahead only with noise), the soil sensitivity qualified as an older measurement, the estimate remark. Every demo number was re-checked against the running API on 10 Oct 2026.
- `docs/INTERVIEW_FINDINGS.md`: clarified that "nothing is used" means nothing from the blank form, and that the scoring's own wetness term is in use.
- `docs/FOUR_DAY_PLAN.md`: note that the slope gate of the original plan is now the `hard` mode.
- `CLAUDE.md`: one note on the Habagat exception to "scores never depend on the dates", and a "LATEST" status line.

## 4. Files created (all in `docs/defense/`)
`ALGORITHMS.md`, `LIMITATIONS.md`, `NUMBERS.md`, `PANEL_QA.md`, `OVERNIGHT_REPORT.md`, `make_numbers.py` (generates NUMBERS.md), `_runtime_numbers.json` (measured values read by it), `_partA_reproducibility.md`, `_partB_demo_run.md`, `_partEF_robustness_edge_cases.md`. Screenshots: 46 files in `C:\Users\user\Desktop\Optimizing_Survival_Screenshots\round20\` (outside the repository, as in earlier rounds).
Browser and test scripts of this run stay in the session scratchpad (`cdp_20b.mjs`, `cdp_20b2.mjs`, `cdp_20f.mjs`, `cdp_20f2.mjs`, `edge20f*.py`, `time_api.py`, `cmp20a.py`), not in the repository.

## 5. State left behind
- The real API runs again on port 8001 from a clean start (default `S_SOURCE` rf). Earlier temporary APIs (their plans and field checks were in temporary folders) are stopped. No plan or field check was written to your real `data/processed/plans` or `data/field/field_checks.db`; the real weather cache received one forecast response (git-ignored).
- Git status: `README.md`, `CLAUDE.md`, `docs/DEMO_SCRIPT.md`, `docs/FOUR_DAY_PLAN.md`, `docs/INTERVIEW_FINDINGS.md` modified; `docs/defense/` new. The pre-existing changes (`scripts/rebuild_scores.py`, deleted `san_mateo_species_rules.csv`, untracked `Tree_Species_Harmonized.csv`, `try.py`) were there before this round and were not touched except `scripts/rebuild_scores.py`, which only gained per-step timing (needed for Part A).

## 6. Unverified
The steps before scoring were not rebuilt (Part A); the field kit was not tested on a phone, GPS or paper; the browser runs used headless Edge at 1366 x 768 only (a phone width was covered by earlier rounds, not this one); memory growth over a long session; all provisional rules and weights remain unvalidated.
