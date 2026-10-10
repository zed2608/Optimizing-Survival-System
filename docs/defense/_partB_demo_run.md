# Part B - demo run-through in the browser, S_SOURCE = "rf" (round 20, run 2026-10-10)

Setup: a TEMPORARY API on port 8001 (plans, kits and field checks in a temporary folder; the data folder `data/processed` read-only), `/health` = `s_source: rf`, `s_source_requested: rf`, no warning, `slope_mode: graded`, model trained 2026-10-09T12:53:56+00:00.
Browser: headless Edge 1366x768 against the Vite dev server (port 5173), scripts `cdp_20b.mjs` and `cdp_20b2.mjs` (kept in the session scratchpad, not in the repo).
Area: barangay GUINAYANG (257 scored squares; picked from the open-land ranking (share of grass / crop cover of the satellite layer) among barangays that are not Habagat barangays; Ampid II was not used). Planting window 10 May - 30 Jun 2027 (inside the planting months; outside Jul-Sep so Habagat never applies).
Screenshots (46 files, clear names): `C:\Users\user\Desktop\Optimizing_Survival_Screenshots\round20\` (outside the repository, as in earlier rounds).

## What was run and the result
| Step | Result |
|---|---|
| B0 app state | PASS: rf, no fallback warning |
| B1-B2 pick the barangay; area panel for urban, planting, watershed (Simple and Detailed) | PASS, "45 of 45 species suitable somewhere here" for each purpose |
| B3 create a 300-tree plan from the screen, each purpose | PASS: urban 15 blocks, planting 12 blocks, watershed 13 blocks; placed 300 of 300 each |
| B4 plan is in blocks (default layout), 300 trees | PASS |
| B5 "Why this score?" in Detailed shows the RF line | PASS: "Suitability from the Random Forest: 1.00. Rules check: passed." + the honest note |
| B6 species card (Clumping Bamboo, then Kamagong) | PASS |
| B7 advice panel | PASS in the plan result (5 items by the API, closed in Simple) and in the Kamagong card; Clumping Bamboo (the first row) has no advice item for this window, so its card shows no panel (correct: no rule fires) |
| B8 field check "Planted" (16 trees, observer "Audit tester") | PASS: saved, confirmation shown, 1 new event |
| B9 Progress card | PASS: "16 of 300 trees planted (5.3%)", blocks 1 done / 12 to do |
| B10 field-check export csv | PASS: holds the new event |
| B11 field kit | PASS: built in 7.2 s, zip 186 KB with blocks.csv, GPX, KML, README, field-map.pdf, manifest |
| B12-B13 points layout | PASS: the points layout is NOT offered in the screen (API / command line only); a points plan saved through the API opens from Campaign Logs ("257 trees" shown) |
| B14 tour | PASS: the tour has **24 steps** (not 23); all shown, none skipped; 6 steps are centred cards (welcome, species-card, advice, species-filters, kit-use, field-progress) because their element needs an open card/plan |
| B15-B16 Help search | PASS: "random forest" finds the answer "What are site match, purpose fit and overall match?" (the Random Forest sentence is in the answer text, not in the question title); "field kit" finds the kit answer |
| Console / network | 0 console errors, 0 failed network calls (tile-server noise excluded; none occurred) |

First run: 4 FAIL, all script mistakes (the first row Clumping Bamboo has no advice rule; progress JSON key; Field-kit tab hidden behind the point panel; Help check only read question titles). Re-run of those parts: all PASS.

## Time to plan, 300 trees, Guinayang, rf, blocks
| Purpose | Browser (click "Create plan" -> result card) | API POST /plan-event (blocks) | API POST /plan-event (points) | Blocks / hectares |
|---|---|---|---|---|
| urban | 0.52 s | 0.55 s | 0.69 s | 15 / 15 ha |
| planting | 0.45 s | 0.30 s | 0.46 s | 12 / 12 ha |
| watershed | 0.46 s | 0.42 s | 0.48 s | 13 / 13 ha (browser) |
(The Part A training was finished when these were timed. Field kit build 7.2 s.)

## Observations for the report
- The satellite picture in the screenshots (`on_08...`) shows planned blocks lying on land that looks like housing / roads in Guinayang: the squares are scored on elevation, slope, soil, wetness, zone; the ground-cover flags (bare / built-up / water) are information only. The "Check first" box and the ground-cover line exist for this; a field team must still look. (This is the documented design, see LIMITATIONS.md.)
- FINDING (medium for a demo): the form's estimate "About 5 blocks of 64 trees (about 5 ha)" for 300 trees is the same for all three purposes (`/plan-event/preview` -> `blocks_estimate`: typical = median trees per full block of the species with a suitable square, 64; range 1 to 34 blocks, `blocks_high` 34), but the real plans used 15 / 12 / 13 blocks (13-15 ha), i.e. 2.4 to 3 times more than "about 5". The service states its basis in `blocks_estimate.basis`, and the screen says "About", but a panel member may ask why the form says 5 and the result says 13. Not changed (no new features); listed in the report.
- Species that showed no advice panel in the species card in this run: ids 13 (Clumping Bamboo) and 3 (0 advice items from `/species/{id}/advice` for this window); ids 6, 11, 35, 33 had 1 or 2 items. A species card with no rule hides the panel (by design, `AdviceSection.jsx`).
