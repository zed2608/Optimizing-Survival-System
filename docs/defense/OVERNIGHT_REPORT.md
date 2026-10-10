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


---

# Round 21: fixes of the audit findings (10 Oct 2026)

Wording and small fixes only. No new feature; `S_SOURCE` stays "rf", `SLOPE_MODE` stays "graded"; nothing committed; nothing deleted outside new folders.

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | Wetness wording (high) | **Fixed** | The code: `score_sites.py` wetness term, weight 0.25, 50 m, layer `data/SMR_WATERBODIES_POLY.shp` (CREEK and RIVER), `tolerance + (1 - tolerance) x distance / 50` (tolerance Low / Medium / High = 0 / 0.5 / 1), lowers S for 2,960 of 360,450 pairs. New wording everywhere: "Distance to creeks and rivers is used as a soft wetness factor (50 metres), but the waterways map has not been validated by MENRO: the waterways form was signed blank." Changed: `tutorialContent.js` (tour step "Data and limits", the "signed off" answer, and the glossary "Site match", which also wrongly said "rain" is scored), `docs/USER_GUIDE.md` (rebuilt, up to date), README, INTERVIEW_FINDINGS, `docs/defense/LIMITATIONS.md` and `PANEL_QA.md`. Tests: `tests/test_round21.py` (no text says the creek rule is "not used"; the wording is present; the term is in the scores) and `tutorial.test.mjs`. Browser: the Help "signed off" answer shows the new words in normal and fallback mode, PASS. |
| 2 | Fallback notice (high) | **Fixed** | A strip at the top: "Random Forest scores are not loaded. The app is using the rule scores. Run scripts/rebuild_scores.py." (`ScoreSourceNotice.jsx`, `scoreSource.js`, `new.css`). Browser check on a data copy without `s_prob`: notice at y = 0, 1366 x 28 px, role status, the dashboard sits 28 px lower without scroll bar or cut-off (screenshot `round21/r21_fallback_notice_top.png`); the Help "site match" answer says "Right now the Random Forest scores are not loaded, so site suitability comes from the expert rules themselves" and no longer says the forest predicts. Normal rf mode: no notice, Help unchanged (browser PASS). |
| 3 | Block estimate (medium) | **Fixed** | Cause: `/plan-event/preview` divided the trees asked by the median trees per full block of every available species (64). Now it runs the real `make_plan` (same seed, season, exclusions) and reports its blocks (`exact` true). Browser, form against the plan really made (Guinayang, 9 cases): urban 300 trees 15 / 15, 100 trees 7 / 7, 1000 trees 45 / 45; planting 12 / 12, 6 / 6, 30 / 30; watershed 13 / 13, 7 / 7, 32 / 32 (it said "About 5" for 300 trees before). `tests/test_round21.py`: 12 parametrized cases (3 purposes x 4 counts) plus other areas and chosen species compare estimate and real plan. Cost: the preview takes 0.15 to 0.23 s instead of 0.007 s. The capacity message ("Only N suitable squares ...") now also fires when fewer trees fit than were asked. |
| 4 | Known limits text (medium) | **Fixed** | `api_v2.LIMITS` and `run_plan.LIMITS / BLOCK_LIMITS` use `{S_LIMIT}`, filled by `run_plan.s_limit_text(ctx)`: default "S comes from a Random Forest trained on expert rules (the rule limits for zone, elevation and steep slope apply first), not from field survival data."; in rules mode only: "S comes from expert rules written from the species data, not from field survival data." Live `/health` checked; tests in `test_round21.py`. |
| 5 | Invalid API input (medium) | **Fixed** | One handler (`plain_validation_handler`): 422 with `{"message": "The request could not be used: n_saplings must be less than or equal to 2000.", "detail": (same text), "fields": ["n_saplings"]}`; no `type`, `loc`, `input` or `ctx`. The service's own error messages are unchanged. Live check with 5,000 trees. Ten kinds of bad input and the model-level errors are tested; all older tests pass (698). The 19 raw answers of round 20 are now plain. |
| 6 | Memory (important) | **Measured; no clear cause; nothing changed** | See below. |
| 7 | Built-up land (documentation) | **Done** | `LIMITATIONS.md` D3, `PANEL_QA.md` Q17 and new Q17b: blocks can lie on land that looks built up because the only inputs that could show it are the zoning map and the ESA land cover, the land cover is information only, and MENRO checked the ground cover on only 10 squares (stated by the project team; the repository holds no record of which squares or what was found: UNKNOWN). Mitigation: field check before planting (move the block, never plant on paved or built land, mark Not plantable with a reason, top-up). |
| 8 | Re-run | **Done** | pytest 698 passed, 1 skipped (297 s); qa_day1 34 passed, 3 warnings, 0 failed; `npm run build` OK; `npx eslint src/new` no problems (it found one problem in my first version, fixed by moving `isFallback` to `scoreSource.js`); 7 node test files pass; user guide up to date; browser checks `cdp_21.mjs` in normal and fallback mode: ALL PASS, 0 console errors. |

## Item 6: memory measurements
Setting: a temporary API on the real data (plans and kits in a temporary folder), clean start, `OS_S_SOURCE` unset (rf). Figures are the working set of the API worker process (the 3 MB launcher stub excluded; my first probe read the stub and was discarded and the run repeated).

| Moment | Working set | Private |
|---|---|---|
| Start | 187 MB | 855 MB |
| After 100 plans (mixed purposes, 10 to 2000 trees, 14 areas, 15% points layout) with /grid, /rank and /rank/area at every plan | 194 MB (+7) | 862 MB |
| After 5 / 10 / 15 / 20 field kits | 342 / 350 / 329 / 348 MB | 1,040 to 1,083 MB |
| After 600 more /grid + /rank pairs | 270 MB | 1,005 MB |
| After 100 more plans | 265 MB | 1,013 MB |
| After 10 / 20 / ... / 80 more kits (100 kits in all) | 308 / 312 / 304 / 326 / 317 / 326 / 322 / 311 MB | 1,053 to 1,073 MB |

Total: 200 plans, 100 kits, about 1,500 read calls. Memory rises by about 150 MB when the first kits are built (matplotlib and the PDF), then oscillates between 304 and 350 MB and falls again after the kit phase. **There is no growth trend, so memory does not grow without limit in this test.** Code review: the in-memory caches are bounded (`multi_cache` 48, `areas_cache` 64, `plan_index_cache` 64 entries; `grid_cache` at most 3 purposes x 46 species of about 300 KB; the Habagat and zoning views are built once), and the PDF code closes every figure (`plt.close`).
The 5 GB working set seen in round 20 was **not reproduced** and its cause is UNKNOWN (that process had served many hours of browser runs, kit builds and plans of up to 2,000 trees; no pattern in my test comes near it). I did not guess and added no cache or limit. If it happens again in a demo: restart the API (about 4 s) and watch the working set of the `uvicorn` process in Task Manager.

## Files changed in round 21
Code: `api_v2.py` (limits placeholder, validation handler, exact estimate in the preview, capacity condition), `pipeline/run_plan.py` (`s_limit_text`, `{S_LIMIT}`), `frontend/src/new/AppNew.jsx`, `ScoreSourceNotice.jsx` (new), `scoreSource.js` (new), `new.css`, `tutorial/tutorialContent.js`, `tutorial/HelpPage.jsx`, `tutorial/tutorial.test.mjs`.
Tests: `tests/test_round21.py` (new, 37 tests), `tests/test_api_blocks.py` (the preview test now pins the exact estimate instead of the median one).
Docs: `docs/USER_GUIDE.md` (rebuilt), `README.md`, `CLAUDE.md` (Round 21 section, status line), `docs/DEMO_SCRIPT.md` (estimate line), `docs/INTERVIEW_FINDINGS.md`, and in `docs/defense/`: `LIMITATIONS.md`, `PANEL_QA.md`, `ALGORITHMS.md`, `NUMBERS.md` (regenerated), `_runtime_numbers.json`, this report.
Screenshots: `C:\Users\user\Desktop\Optimizing_Survival_Screenshots\round21\` (notice, Help answers, the estimate against the plan).
State left: your real API runs again on port 8001 from a clean start (rf, no warning); temporary APIs are stopped; the real plans folder still holds its 15 plans (nothing was written by this round).

## Unverified in round 21
The fallback notice was checked at 1366 x 768 only (no phone width); the "10 squares checked by MENRO" statement is the project team's and has no file behind it; the cause of the 5 GB reading; the preview now costs 0.15 to 0.23 s per form change (not measured in a long session).
