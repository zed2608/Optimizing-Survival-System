# Optimizing Survival - project guide for Claude Code

Undergraduate thesis system for San Mateo, Rizal (Philippines): species-site suitability (Random Forest) plus weighted
bipartite matching (Hungarian algorithm) for community-led urban greening. Stack: FastAPI + SQLite backend, React/Vite/Leaflet
frontend, Python data scripts. Audience: LGU planners, a thesis panel, and a licensed agriculturist who signs the dataset.

## Golden rules (never break)
1. **Never invent data.** A missing value stays empty / "Data Unavailable". No guessing, no filling from memory.
2. **Every value shown or released carries its source** (URL or file) and source rank. Provenance lives in `species_sources`.
3. **Do not edit `data/raw/`.** Raw inputs are read-only; all cleaning happens in `pipeline/` and writes to `data/processed/`.
4. Provisional choices (tag maps, weights, soil texture mapping) are labelled `provisional` / `_prov` until the agriculturist signs off.
5. Do not commit large rasters, `.tif`, model pickles, or secrets. Use environment variables for keys.
6. Small commits on a branch per workstream; run `python pipeline/qa_day1.py` before committing data changes.

## Repo map (as of 2026-10-05)
- `api_v2.py` - the NEW FastAPI backend (port 8001): rankings, grid, boundaries, areas, plans, field kits, weather advisory and saved field checks.
  Start: `python -m uvicorn api_v2:app --port 8001`. `api.py` / `optimization.py` are the OLD app: do not extend.
- `main.py`, `evaluate_system.py`, `train_suitability_model.py` - STALE legacy; do not extend. `train_model.py` - old 20-class RF (replaced by `pipeline/compare_models.py`).
- `backend/app.py` - Flask CSV server that only the legacy dashboard (`#/legacy`) still calls (`127.0.0.1:5000/api/points`).
- `frontend/` - React 19 + Vite + Leaflet. `src/App.jsx` + `src/App.legacy.jsx` = the OLD dashboard (scores in JavaScript; keep untouched until the
  revamp is approved). `src/new/` = the revamp (`#/new`), `src/v2/` = the first v2 page (`#/v2`). `src/dashboardConfig.js` picks the default dashboard.
- `pipeline/` - `ingest_species`, `rebuild_site_grid`, `qa_day1` (Day 1); `score_sites`, `score_purposes`, `make_pair_table`, `compare_models` (Day 2);
  `palettes`, `matching`, `run_plan` (Day 3); `field_kit`, `advisory` (Day 4); `field_verify` (saved field checks). `tests/` has the pytest suites.
- `data/raw/` inputs, `data/processed/` outputs (+ `optimizing_survival.db`; `scores/`, `plans/`, `kits/`, `cache/` are git-ignored), `data/config/` weights,
  `data/field/field_checks.db` = the saved field checks (git-ignored, back it up).
- `docs/FOUR_DAY_PLAN.md` - the scoped plan with acceptance criteria. `docs/MASTER_PLAN.md` (if present) - full plan (future work).

## Commands
```
pip install -r requirements-day1.txt
python pipeline/ingest_species.py --input data/raw/species_directsource.csv --sources data/raw/sources_list.csv --out data/processed
python pipeline/rebuild_site_grid.py --input backend/Working_Points.csv --landuse data/LandUses.shp --out data/processed
python pipeline/qa_day1.py --out data/processed          # must end with 0 failed
```

## Known defects being fixed (verified)
- Grid `slope_1` was a copy of `elevation_`; `soil_ph` was random. Day 1 rebuilt slope; **pH is not scored** (no real layer).
- The old RF is a 20-class species classifier trained on synthetic positives; its probabilities sum to 1 across species.
- The old matching used species as nodes (max one tree per species). Nodes must be **sapling slots**.
- Dashboard does not call the RF/matching code.

## Data facts to respect
- Species dataset: 45 species. 34 Batikuling cells cite a PDF that was not provided (`file_source_not_provided`) - treat as unverified.
- 30 cells cite sources outside the supplied SOURCES list (flag `off_list`). Endangered scheme (DENR vs IUCN) is mostly unnamed.
- Soil texture per soil code is the legacy mapping from `backend/app.py` and is UNVERIFIED (`soil_mapping_status`).
- Site grid is ~100 m cells; slope is finite differences, 22% of cells have `partial` slope (one axis) and may under-estimate.
- Legal zones: the 11 CLUP zones in `rebuild_site_grid.py` (`VALID_ZONES`, includes the LGU typo "General Institutional Zonec").

## Definitions
S(site, species) = site suitability in [0,1]; P(species, purpose) = purpose fitness in [0,1]; W = S x P if S >= 0.50 else 0.
Purposes: `urban`, `planting`, `watershed`. Matching: Hungarian on cost = 1 - W over sapling slots x legal points.

## Saved field verification (added 2026-10-05)
A researcher who visits a ranked or planned spot can save what they saw. Storage: SQLite `data/field/field_checks.db`, table `field_checks`, APPEND-ONLY
events (the database triggers refuse UPDATE and DELETE; never edit or delete an event: add a new one). Fields: check_id, point_id, status
(`verified_plantable` | `not_plantable` | `needs_recheck`), reason (required for not_plantable), note, observer (a name only: there is no login), observed_at,
gps_lat/lon/accuracy, moved_lat/moved_lon (where the stake was really placed), source (`dashboard` | `kit_import`), plan_id, created_at.
The latest event of a point is its current status; if the latest two come from different observers and disagree the point is DISPUTED.
- Code: `pipeline/field_verify.py` (storage, validation, import) and the `/field-checks` endpoints of `api_v2.py` (POST, GET list, GET {point_id}, summary,
  export.csv, POST import = the filled `point-list.csv` of a field kit; point_ref -> point_id through the saved plan; a repeated import adds nothing).
- Effects, one switch `API_CFG["field_exclude_not_plantable"]` (default ON): `not_plantable` points are left out of /rank, /grid (own class `field` in the compact
  response), /rank/area, /areas/rank, /nearest-viable and /plan-event (plan summaries report `field_checks.excluded_points`). `verified_plantable` only adds a
  badge/flag and NEVER changes a score. `needs_recheck` and disputed points are warned about, not excluded. Clearing a not_plantable point needs a new event with a note.
- /rank/municipal is NOT affected (it is precomputed over all points). Tests: `tests/test_field_verify.py` (they use their own temp database).
- Dashboard `#/new`: Field check section in the point panel, map symbols (ring = verified, cross = not plantable, triangle = recheck), sidebar counts, CSV
  download and import with a report.
- Moved positions are logged so that they can LATER improve the results (correct a cell's real planting position, learn where cells are unusable, review the
  100 m grid); nothing uses them yet.

## Search bar in `#/new` (added 2026-10-05)
One search box at the top of the map (`frontend/src/new/SearchBar.jsx`, an ARIA combobox: arrows, Enter, Escape, clear x, 8 recent searches kept in the browser).
Suggestions start after 2 characters and a 250 ms pause; stale requests are cancelled. Groups and what choosing them does:
- Barangays (accent/case/"Sta"="Santa"/"Sto"="Santo" tolerant) -> mode 2, outline highlighted and zoomed, ranked species from `POST /rank/area`.
- Coordinates (read in the browser by `coords.js`, tested by `coords.test.mjs`): `14.69, 121.12`, `14.69 121.12`, with N/E letters, or UTM zone 51N `296799 1625091`.
  Bad input is rejected with a reason, never guessed. Chosen -> spot marked, ranked; outside the municipality or not a planting zone the panel says so and offers `/nearest-viable`.
- Species -> mode 1 with that species chosen. Planting points: a grid point id (`832`) or a plan point (`MOL-001`, species code, or common name from the 20 newest saved plans).
- Places (streets, landmarks): only if the optional geocoder is on; the page calls it ONLY when Enter is pressed on that row.
API (`api_v2.py`): `GET /search/all` (compact, per-group `limit`, 2+ chars), `GET /search/point?q=<digits>`, `GET /plans/{plan_id}/points?q=`, `GET /search/place` (now with
`type` and `display_name`), `GET /search/geocode?q=`. Plan items (in `/plan-event` and `/plans/{id}`) now also carry `point_ref`, `species_code`, `barangay`,
`barangay_display`; they are DERIVED at read time (`field_verify.plan_point_refs`, same numbering as the kit): the saved plan CSV columns did not change.
Geocoder (Nominatim) is OFF by default (`API_CFG["geocoder_enabled"]`, answers 503). To use it set `geocoder_enabled` True AND `geocoder_contact` (an email or web address;
empty = no request is ever sent). Rules built in: User-Agent with that contact, Philippines only, bounded to a box around San Mateo, max 1 request per second, every answer cached
on disk 30 days (`data/processed/cache/geocode/`, git-ignored), stale cache used when the network fails, credit text "Search data (c) OpenStreetMap contributors" shown with results.
All tunables are in the one `API_CFG` block (`geocoder_*`, `search_*`). Tests: `tests/test_api_search.py` (the network is faked; it also runs the node tests of the parser).

## Current status and next tasks
DONE: Day 1 (data), Day 2 (site scores, purpose scores, model comparison), Day 3 (palettes, matching, `api_v2.py`), Day 4 (field kit, weather advisory),
the `#/new` dashboard steps 0-3 (map, outlines, grid layer) and both modes ("I have species - find areas" / "I have an area - find species"), saved field checks,
and the search bar (290 tests pass).
**Open items**: none. (Closed 2026-10-05: the field kit README has a "BRINGING THE RESULTS BACK" paragraph; `pipeline/run_plan.py` leaves out not_plantable points through
`field_verify.filter_context` (option `--field-db`, default `data/field/field_checks.db`, never created by planning), prints the count and writes `field_checks` into the plan
summary like `/plan-event`. Tests: `tests/test_run_plan_field.py`.)
**Later**: plan tool in `#/new` (step 6), saved campaign name/dates/unit with each plan, replace Search-by-Species/Land modes of the legacy page (decided: later),
real login for field checks, phone test of the GPX/KML kit, agriculturist sign-off of weights/soil mapping.
When you finish a task: run QA/tests (`python -m pytest tests`, `python pipeline/qa_day1.py`, `npm run build` in `frontend/`), update this status, commit, and summarize what
changed and what is still unverified. Ask before changing the schema in `data/processed/` or the meaning of any column.
