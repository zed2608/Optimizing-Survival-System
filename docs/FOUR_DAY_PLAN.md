# Four-day plan (scoped build) - San Mateo Optimizing Survival

Goal: one working end-to-end slice on real data, with a thin version of every adviser-requested feature. Everything else is
documented future work (see the full master plan). Never cut: matching with sapling slots, source links, baselines, breakdown, GPX/CSV export.

## Scope
| Keep in full | Keep thin | Defer (future work) |
| --- | --- | --- |
| Species loader + sources (DONE) | Purpose scores with provisional weights; +-25% sensitivity | Soil pH scoring (no real layer) |
| Real slope + one row per cell (DONE) | Palettes = species quotas + diversity cap + dioecious rule | Rainfall and temperature layers |
| Site match with breakdown | Weather advisory: forecast vs `planting_months` | Pairwise compatibility matrix, palette optimizer |
| RF vs LR/KNN/DT, same split, unseen-species test | Search: barangay list, coordinates, fallback ring scan | Geocoder, map pack, offline web app, return log |
| Matching with sapling slots + constraints | ISO/IEC 25010 short questionnaire | Full 16-table schema |
| One backend wired to the dashboard; Field kit level 1 | | |

## Day 2 - scores and model
1. `pipeline/score_sites.py`: S for every (point, species) pair.
   - Hard gates (S=0 if violated): `is_legal_zone`; elevation within `elev_min_m..elev_max_m`; slope <= `max_slope_pct`;
     soil texture: species `soil_textures` contains the site's `soil_texture_legacy`, or `soil_any_texture` is true. If the site texture is unknown
     (Technosol / None) treat the soil gate as unknown: do not exclude, lower confidence.
   - Soft factors (0..1, linear fall-off over a margin; margin = 10% of the species range, parameter in one config place):
     elevation margin, slope margin, soil match, wetness (distance to nearest CREEK/RIVER vs `waterlog_tol`).
     NOT scored: pH, rainfall, temperature, canopy, exposure (no real layers).
   - Output `data/processed/site_scores.csv` + DB table `site_scores(point_id, species_id, s_rule, s_prob NULL, breakdown_json, confidence)`.
     `breakdown_json` lists each term with its value, weight, and the species-field source URL from `species_sources`.
2. `pipeline/score_purposes.py`: P per species and purpose from `data/config/purpose_weights.csv` (weights are PROVISIONAL).
   Criterion scores 0..1: ordinal levels Low/Medium/High = 0/0.5/1 (inverted where lower is better); numeric traits min-max across the 45 species;
   tags 1 if present else 0; missing -> 0.5 and lower the species confidence. Write `data/processed/purpose_scores.csv` with a per-criterion breakdown.
   Also write a +-25% weight sensitivity table (rank change per species).
3. (Cyrus) `pipeline/make_pair_table.py` then `pipeline/compare_models.py`: pair table (site features + species traits -> label `suitable = s_rule >= 0.5`,
   with a documented noise rule); RF, Logistic Regression, KNN, Decision Tree on the SAME stratified CV folds, tuned equally; also a leave-species-out test
   (train ~35 species, test ~10). Report accuracy, precision, recall, F1, ROC-AUC, Brier. Fix seeds. Calibrate the RF (isotonic or Platt) and store `s_prob`.
Acceptance: `site_scores` covers all legal points x 45 species; a unit test shows a species outside its elevation range gets S=0; baselines table exists with fixed seeds.

## Day 3 - palettes, matching, API
1. `pipeline/palettes.py`: per zone, choose k=4..8 species by sum(P x S) with caps: <=10% per species, <=20% per genus (provisional), include both sexes for dioecious species,
   shared planting month window. Output species shares.
2. `matching.py` (replace `optimization.py` logic): left nodes = sapling slots (species quota), right nodes = candidate points (legal zone, S>=0.50, not within 5 m of
   existing trees if that data exists, grid spacing >= largest min spacing in the palette). Cost = 1 - W. Use `scipy.optimize.linear_sum_assignment` on a rectangular matrix.
   Vectorize scoring; no per-pair model calls.
3. Property tests (pytest): no assignment below threshold; no two trees closer than their spacing; no tree outside a legal zone; no species over its cap; unmatched points reported.
4. FastAPI (extend `api.py`): `GET /species`, `GET /rank?purpose=&lat=&lon=`, `POST /plan-event` (returns plan items with score + breakdown + source links),
   `GET /search/species`, `GET /nearest-viable`. Remove dependence on `backend/app.py`.
Acceptance: `POST /plan-event` returns a plan for a drawn polygon in a few seconds; all property tests pass.

## Day 4 - product, exports, evaluation
1. Dashboard: replace JS scoring with API calls; purpose selector; ranking table; accordion showing the breakdown with source links and source rank; `Data Unavailable` shown as such.
2. Weather advisory: one forecast call (Open-Meteo or OpenWeatherMap), compare the forecast window with the species `planting_months`; show warnings; cache the response.
3. Search: barangay list (from `data/BRGY_BOUNDARY.shp`, 15 names; add aliases Sta -> Santa, Sto -> Santo), coordinate box, species search, fallback ring scan to the nearest viable point.
4. Field kit level 1 from an approved plan: `points.gpx`, `points.kml`, `point-list.csv` (point_id, species_code, common_name, lat, lon, utm_e, utm_n, barangay, spacing, planting months, notes),
   `readme` page; PDF grid map if time. Stamp plan id, dataset hash, date on every file.
5. Test: open the GPX in an offline map app in airplane mode on a real phone; walk >= 5 points if possible and record GPS error.
Cut order if time slips: PDF map, weather advisory, municipality-wide ranking.

## Saved field verification (added after Day 4)
Why: a site researcher may visit a ranked or planned spot and find it cannot be planted (paved, building, rock, creek, too steep, existing tree, owner refused).
The old dashboard's Verify / Flag Paved marks were lost on refresh; this keeps them.
1. `pipeline/field_verify.py` + `data/field/field_checks.db`: append-only events (`verified_plantable`, `not_plantable` with a required reason, `needs_recheck`; observer name,
   time, optional GPS, optional moved stake position, source `dashboard` or `kit_import`, optional plan id). The latest event per point is its current status; two different
   observers who disagree in the latest two events make the point DISPUTED.
2. API (`api_v2.py`): `POST /field-checks`, `GET /field-checks`, `GET /field-checks/{point_id}`, `GET /field-checks/summary`, `GET /field-checks/export.csv`,
   `POST /field-checks/import` (the filled `point-list.csv` of a field kit; rows are mapped point_ref -> point_id through the saved plan and its check code; bad rows are
   rejected with a reason; importing the same file twice adds nothing).
3. Effects (switch, default ON): `not_plantable` points are left out of rankings, the grid, area rankings, nearest-viable and plans; plan summaries report how many points
   were left out. `verified_plantable` adds a badge only and never changes a score. `needs_recheck` / disputed: warning, not excluded. To clear a point add a new event with a note.
4. Dashboard `#/new`: Field check section in the point panel (status, history, three buttons, reason and note, remembered observer name), map symbols (ring / cross / triangle,
   never colour alone) with a legend and a toggle, sidebar counts, CSV download and import with an accepted/rejected report, not-plantable counts in area results, and a line in
   Known limits: no login yet, a name only, anyone with access can add a check.
5. Field kit: the kit's `status`, `moved_lat`, `moved_lon` columns are what the import reads. The kit README should say how to bring the filled file back (open item: it needs a
   one-line change in `pipeline/field_kit.py`); `pipeline/run_plan.py` should apply the same exclusion (open item, see CLAUDE.md).
6. Later use of the logged moved positions: they record where a cell is really plantable, so they can later correct a cell's planting position, show cells that are never usable,
   feed a review of the 100 m grid and, with enough checks, give real survival-site evidence to compare with the rule-based scores (the RF labels are still rule-derived).
Acceptance: events can never be changed or deleted; the latest event wins; excluded points never appear in plans, grid ranking, area ranking or nearest-viable; verified does not change
any score; import is idempotent and reports errors; old endpoints behave as before when there are no checks (`tests/test_field_verify.py`).

## Search bar (added after field verification)
Why: planners and field teams know places by barangay, species, point number or plan point reference, not by clicking a map.
1. One search box in `#/new` with grouped suggestions (Barangays, Coordinates, Species, Planting points, Places), keyboard use, clear button, recent searches (browser only),
   a plain "no results" message with examples, 2-character minimum with a short delay and cancelled stale requests.
2. Actions: barangay -> mode 2 with outline highlight and ranked species; coordinates (decimal or UTM 51N) -> marked spot and ranking, friendly message plus nearest viable spot when
   outside the municipality or not a planting zone; species -> mode 1; grid point id or plan point (`MOL-001`) -> zoom and open its panel (plan id and species shown).
3. API: `GET /search/all`, `GET /search/point`, `GET /plans/{plan_id}/points`, `GET /search/place` (adds type), `GET /search/geocode`; plan items gain `point_ref`, `species_code`,
   `barangay` without changing the saved plan CSV.
4. Optional street/landmark search through Nominatim, OFF by default: contact required, Philippines + San Mateo box, 1 request per second, 30-day disk cache, only on Enter,
   attribution shown, cache or a clear error when the network fails.
Acceptance (`tests/test_api_search.py`, 29 tests): accents/case/Sta-Sto; parser accepts decimal and UTM and rejects bad input; point and plan-point lookups with 404s; plan_id
traversal rejected; `/search/all` limits and speed with 20 plans; geocoder 503 when off, no request without a contact, cache hit, rate limit, network failure, never the real internet.

## Planting window (season) and guided sidebar (feedback round, part 1)
Why: the earlier dashboard let the user set campaign dates and the period decided the season; `#/new` had lost this, and the sidebar was too crowded.
1. API (`api_v2.py`): optional `start`, `end`, `season_filter=only|mark` on /grid, /rank, /rank/area, /areas/rank, /species, /species/{id}, /nearest-viable, /plan-event.
   Species get a `season` object (in_season / partly / out_of_season / unknown with window months, species months and the months in common); windows may cross the year end.
   Scores never change. `only` removes out-of-season species from rankings, grid colours, area tables, the mix and the plan palette (whose shared months are cut to the window)
   and reports how many were removed and why. No dates = unchanged. Bad dates = 422 in plain words.
2. `#/new`: Planting window step (dates, 12-month strip, remembered), toggle "Only species for my dates" (default ON), season badges with words and month strips everywhere a
   species appears, and a notice "Only N of 45 species can be planted between ..." with [Show all species] [Change dates] when few or none are left.
3. Sidebar: five collapsible steps (Goal, Purpose, Planting window, Species/Area, Options), one open at a time, one-line summaries when collapsed, one "More" menu for Known
   limits, dataset version, field-check summary, download and import. Labels of at most 5 words, one-sentence paragraphs, "?" help tips that work with the keyboard.
Acceptance (`tests/test_api_season.py`, 24 tests): status for in/partly/out/unknown; year-end windows; scores unchanged by dates; `only` removes the right species and reports
counts; no dates = old behaviour; bad dates 422; palette months inside the window; date helpers in the browser (node).
Known consequence: all 45 species have planting months only from May to September, so in October and November none is in season and the default window (today +30 days in
early October) shows the "Only 0 of 45" notice until the dates or the toggle are changed. This is a data fact to confirm with the agriculturist, not a defect of the filter.

## Sidebar fix, species card and verify-first point panel (feedback round, part 2)
1. Sidebar: four steps only (Goal, Purpose, Planting window, Species/Area); "Only species for my dates" and a "Jump to the next planting season" button (best 60-day window starting
   today or later, most species fully in season, earliest on ties) are in step 3; "Suits all / at least one" is in step 4; map type and the field-checked layer are in a "Map view"
   menu on the map; "More" stays at the bottom.
2. Species card: a drawer opened from every place a species name appears, built from GET /species/{id}; deployment stage and timing first and large; every value with its source
   link and rank badge; gaps shown as Data Unavailable; flagged sources marked draft.
3. Point panel: verify first (100 m notice, one-tap Plantable / Paved or road / Building / River or creek / Other problem / Needs recheck, name asked once, confirmation, Change,
   history); a not-plantable point shows its ranking greyed ("Left out of plans because of a field check").
4. API: `GET /rank?include_left_out=true` (display only; default unchanged). Test: `tests/test_api_rank_left_out.py`.
Acceptance: browser checks of the four steps, the Map view menu, the jump button (equals an independent computation), the card from ranking rows, area rows, the mix, the picker
and search, one-tap verify (saved, confirmation, history, change adds a second event, point leaves the nearest-viable offers), with the API on and off.

## Thesis limits to state
RF labels derive from rules; weights are provisional; pH is not scored; slope comes from ~100 m cells; soil texture mapping is unverified;
sign-off status as of the defense date; GPS accuracy untested; field checks carry a name only (no login) and are not yet used to change any score;
street/landmark search relies on OpenStreetMap coverage (not authoritative, off by default); a typed UTM coordinate is assumed to be WGS84 zone 51N.
