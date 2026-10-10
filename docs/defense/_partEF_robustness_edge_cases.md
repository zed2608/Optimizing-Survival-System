# Parts E and F - robustness and edge cases (round 20, run 2026-10-10)

## E. Clean start and timings
Clean start of the real app as a user starts it (`python -m uvicorn api_v2:app --port 8001`, no environment overrides): `/health` answered after **4.2 s**; `status ok`, `s_source rf` (requested rf, no warning), `slope_mode graded`, dataset `v1.0-review 34964a09fe44`.
Memory at start: API worker process **191 MB working set** (856 MB private/committed); a 5 GB working set seen earlier belonged to an old process that had served many plan and kit requests (not re-measured; UNKNOWN whether it grows without limit).

| Endpoint (real data, rf) | HTTP | size KB | first call s | warm s |
|---|---|---|---|---|
| GET /health | 200 | 4.1 | 0.017 | 0.004 |
| GET /grid (all squares, compact) | 200 | 297.9 | 0.004 | 0.003 |
| GET /grid/context | 200 | 4.5 | 0.001 | 0.001 |
| GET /grid/landcover | 200 | 75.5 | 0.001 | 0.001 |
| GET /geo/boundaries | 200 | 58.5 | 0.001 | 0.001 |
| GET /rank (one square, 45 species) | 200 | 240.8 | 0.032 | 0.026 |
| GET /rank with explain | 200 | 242.3 | 0.028 | 0.027 |
| POST /rank/area (barangay) | 200 | 43.5 | 0.117 | 0.116 |
| GET /areas/rank (2 species) | 200 | 4.6 | 0.003 | 0.002 |
| GET /species | 200 | 92.4 | 0.013 | 0.013 |
| GET /species/8 | 200 | 25.1 | 0.006 | 0.005 |
| GET /species/8/partners | 200 | 3.0 | 0.007 | 0.005 |
| GET /species/8/advice | 200 | 0.7 | 0.004 | 0.003 |
| GET /nearest-viable | 200 | 6.8 | 0.007 | 0.006 |
| POST /plan-event/preview (300 trees) | 200 | 1.3 | 0.009 | 0.007 |
| GET /search/all | 200 | 0.6 | 0.169 | 0.012 |
| GET /plans | 200 | 5.1 | 0.112 | 0.008 |
| GET /field-checks/summary | 200 | 0.9 | 0.001 | 0.001 |
| GET /weather/week (real network call) | 200 | 19.1 | 2.178 | 0.008 |
POST /plan-event (300 trees): 0.30 to 0.69 s (Part B). Field kit build: 7.2 s. Memory after these calls: unchanged (191 MB).
The page `/grid` is 298 KB (limit 330 KB). Grid size is fine.

## F. Edge cases (51 API calls on the real data; screen checks)
No 5xx server error in any of the 51 calls. 32 answers carry a plain sentence; **19 answers are FastAPI's default validation list** (JSON with `type`, `loc`, `input`, `ctx`, but readable English `msg`, e.g. "Input should be less than or equal to 2000") when the API is called directly with a body the model refuses (5,000 trees, missing purpose, 0 trees, text instead of a number, empty species list, empty campaign name, too-short search, bad purpose word). The dashboard never sends them (its inputs refuse them first: "Trees: 1 to 2000", "Name the campaign").

| Case | Result |
|---|---|
| Area only outside the zoning map, switch ON (default) | plan works (watershed, flagged); with the switch OFF: 400 "The polygon contains no legal-zone grid points (it may lie outside San Mateo or only cover non-planting zones)." |
| Area with zero eligible squares (cemetery / quarry squares; a polygon in the sea) | 400 with the same plain sentence; rank at a far point: 404 "The nearest grid point is 77517 m away (limit 150 m): the coordinate is outside the mapped area of San Mateo."; nearest-viable: 404 "No point with an eligible species (S >= 0.50) was found within 5000 m of this spot." |
| Exact counts that cannot be met (500 Clumping Bamboo in Santa Ana, points layout) | 200, `species_counts.per_species`: asked 500, placed 60, "Only 60 squares in this area suit Clumping Bamboo, enough for 60 trees." |
| 2000 trees automatic in Santa Ana (blocks) | placed 1402 of 2000 in 60 blocks (all 60 squares); unmatched by species Sampalok 284, Salinggogon 314; screen says "Placed 1402 of 2000 trees in 60 blocks. 598 found no suitable square left for their species." |
| 2000 trees points layout, Santa Ana | warning "caps_cannot_absorb_all_saplings: 600 of 2000 saplings allocated (per-species/genus caps or eligible points)" (API wording with an underscore code; the dashboard uses blocks and plain words) |
| 5,000 trees | API 422 (default list: "Input should be less than or equal to 2000"); screen: Create plan is off, reason "Trees: 1 to 2000" (also for 0, -5, empty, 1.5, abc) |
| Empty or bad inputs | empty body, unknown barangay (lists the 15 valid names), empty barangay, bad polygon (plain sentence), bad dates (plain sentences), unknown species / plan ids (404 plain sentences), path tricks (404 "Not Found"), field check without reason (plain sentence), top-up with nothing to top up (400 plain sentence) |
| Restart with `s_prob` missing (scratch copy, only `score_sites.py` re-run: `s_prob` empty in 360,450 rows) | `/health`: `s_source rules`, `s_source_requested rf`, `s_source_warning` "The saved scores have no complete Random Forest prediction (s_prob), so the app is using the expert rules for the site match S. To use the Random Forest run: python scripts/rebuild_scores.py"; rank and plans still work (100 trees placed 100 of 100); the "Why this score?" line of the forest disappears. **The dashboard shows no notice anywhere** (main screen, point panel, System Analytics); Help still says the forest predicts S. Medium risk for a demo: a silent fallback. |
| Console / network in all screen runs | 0 console errors, 0 failed calls (tile-server noise excluded) |

Script mistakes in my own first runs (not defects): the first-row species had no advice item; progress JSON key; Help check read only question titles; one regex looked for a word the card does not use.
