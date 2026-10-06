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

## Grey squares, point panel redesign, precise location, season wording (feedback round 3)
1. `GET /grid/context`: the 1,837 grid squares that are not planting zones (outside zoning, special reserved, industrial, commercial, quarry, landfill), compact, cached at startup,
   under 120 KB, no nulls. Map: a faint grey layer in the same canvas (ON by default, switch in Map view, legend count, hover and a short click panel with the nearest suitable spot,
   no verify buttons). Known limits: "6,251 planting squares + 1,837 other squares = 8,088 map squares."
2. Point panel as three cards (header, field check, best species), compact rows (5 / 10 / all) with one Details disclosure, tips for legends and explanations, the greyed state kept.
3. Precise location: search suggestions with barangay and type, "Searched: ..." plus the same location block after choosing, barangay display names everywhere.
4. Season wording: "Outside best months" with the best months and the note that planting outside them is possible but riskier. No score or filter change.
Acceptance (`tests/test_api_grid_context.py`, browser checks with the API on and off): 1,837 rows and reasons adding up, size limit, grey layer + toggle + hover + click, header lines,
compact actions, 5 default rows, Details, tips, suggestion text, new wording, plus the earlier modes, season, search, species card and verify checks.

## Compact | Full details, chosen species, honest Plan here, map polish (feedback round 4a)
1. A "Compact | Full details" switch (remembered, keyboard accessible) in the point panel and the area panels: Full opens every row's Details with S, P, W, confidence, the month strip and
   its explanation, flags, the colour legend and the "Why this score?" breakdown (terms, weights, source links); nothing is hidden without a way to open it in Compact.
2. "Your chosen species here" at the top of the point panel ("I have species"): S, P, W, confidence, season and a verdict for each chosen species (8, then "Show all") and the combined
   score with its rule (suits all: lowest W; suits at least one: highest W), equal to the map's score.
3. "Plan here" becomes a disabled "Plan here (next feature)" with a tooltip; the selection is still saved when an area row is chosen.
4. The legend is a small collapsible button; hover cards never run into the results panel, the sidebar, the zoom buttons or the top bars; the "outside the zoning map" sentence in
   the grey-square panel and in Known limits.
Acceptance: browser checks (API on and off) of the switch in both panels, the chosen-species card in both combine modes, the disabled button and its tooltip, the legend, and hover cards
near the panels and edges (rectangle-overlap test), plus the earlier modes, season, search, species-card, field-check and grey-layer checks.

## Plan tool, part 1 (feedback round 5)
1. API: POST /plan-event takes campaign {name, unit}, species_ids and barangay; campaign name, unit and dates are saved and returned; species_ids restrict the palette and relax the caps to the minimum
   needed with a plain warning; /plans and /plans/{id} return campaign, n_species and n_placed (older plans: explicit missing markers); POST /plan-event/preview reports capacity without saving.
   run_plan.py has --campaign-name, --campaign-unit, --species-ids. Defaults and existing outputs are unchanged.
2. Sidebar step 5 "Plan": name, unit, saplings, summary, capacity and empty-season messages, one "Create plan" button with plain disabled reasons; "Plan here" opens it.
3. Result card (Compact | Full), the Planned trees layer (one shape per species + code, legend, hover, click opens the point panel), searchable point list, "Make another plan".
Acceptance (tests/test_api_plan_tool.py, browser checks with the API on and off): campaign fields saved and returned, invalid names rejected, species_ids restriction, cap relaxation message, unknown
ids, unchanged defaults, command line equals API; step 5 reasons, plans in both modes, capacity and empty-season messages, shapes, legend, hover, click, field-checked points never planned.

## Plan tool, part 2 (feedback round 6)
1. Field kit in the dashboard: Build/Rebuild + Download kit (.zip) with details (built date, size, check code, PDF yes/no) in the plan result card and in every Campaign Logs card; GET /plans/{id}/field-kit.
2. Weather advice: GET /plans/{id}/advisory (one forecast request, cache fallback, 503 if none); a card with forecast numbers and warnings grouped by kind (icon + words); honest message when the
   planting dates are beyond the 16-day forecast; the same card in the species card.
3. Campaign Logs: cards with status chips (Active / Upcoming / Concluded / No dates), filters with counts, search, Open on map. System Analytics: six counter cards from the service.
Acceptance: tests/test_api_plan_part2.py (success, cached, 503, window beyond/partial/past/none, bad ids, kit info); browser checks with the API on and off (kit build + zip with points.gpx and matching check code,
weather success/cached/offline/beyond forecast, Campaign Logs with past/current/future plans, filters, search, Open on map, Analytics counters) plus all earlier checks. 360 tests pass.

## Land outside the zoning map and the Weather tab (feedback round 7a)
1. Data: `zoning_status` (confirmed 6,251 / unconfirmed 1,279 / excluded 558) in `rebuild_site_grid.py`; `is_legal_zone` unchanged; `score_sites.py` scores confirmed + unconfirmed (7,530 squares) with the same rules.
2. API: `include_unzoned` (config default True, query parameter on every endpoint); `false` = the results of before; flag `zoning_unconfirmed` in /rank, plan items, the kit's flags and notes (columns unchanged); plan summary counts the unconfirmed trees; Known limits and counts from the data.
3. Dashboard: step 4 switch, dotted ring + legend, point-panel zoning line, result-card count.
4. Weather tab: `GET /weather/week` (one forecast request, cached/offline handling, verdict with numbers, two species lists, held-back list) and the tab (location, purpose, 7 day cards, verdict, lists, Compact | Full).
Acceptance (`tests/test_api_unzoned.py`, `tests/test_api_weather_week.py`, browser checks with the API on and off): counts 6,251 / 1,279 / 558; `include_unzoned=false` equals the old results; flags in rank, plans and the kit; excluded squares never planned; the switch changes /grid counts; weather success, cached, offline, empty season list, heavy rain, dry week; plus all earlier checks (with the switch off they give the old numbers). 396 tests pass.

## Calmer `#/new` and configurable zone rules (feedback round 7b)
1. Zone rules: one `ZONE_RULES` table in `rebuild_site_grid.py` (same results by default); a zone moved to unconfirmed is scored, flagged and named in the note; how to change a zone is in CLAUDE.md.
2. Map: filled squares (no circles), faint flat grey squares, small tree shapes with bubbles at overview, outlines and labels lighter (overlapping labels hidden), Simple | Detailed (Simple by default; the user's own plan and marks always show).
3. Style: one icon set, calmer hierarchy (see `docs/VISUAL_STYLE.md`).
Acceptance (`tests/test_zone_rules.py`, `cdp_look`, all earlier browser checks with the API on and off): moving Special Reserved to unconfirmed adds its 355 squares (counts add up, defaults unchanged); no circles or white outlines, hover and click on squares, grey tone, bubbles and shapes by zoom, codes only at zoom 17 in Detailed, Simple | Detailed remembered, own work visible in Simple, icons only (SVG, stroke 1.5), two font weights, one radius, draw time at overview (JS drawing under 1 ms). 400 tests pass.

## Ground cover from satellite land cover and "why few species suit this square" (feedback round 8)
1. Data: ESA WorldCover 10 m 2021 v200 (one window clipped once, then offline); `site_landcover.csv` with the shares of each class in every 100 m square; sources, licence, attribution and the accuracy statement in `docs/DATA_SOURCES.md`.
2. Flags (information only, provisional): `ground_bare`, `ground_built_up`, `ground_water` in `/rank`, plan items, the kit (notes and README) and the plan summary; no score, rank, eligibility, plan or square count changes.
3. API: `ground_cover` in `/rank` and the point search, `GET /grid/landcover`, `limiting_factors` in `/rank`.
4. Dashboard: the ground-cover line with its tip and badges, the optional layer with a legend (colour + pattern + icon), corner markers in Detailed, the result-card line, the "Why few or no species suit this square" card, Data credits.
Acceptance (`tests/test_landcover.py`, `cdp_ground`, all earlier browser checks with the API on and off): shares add up, dominant class, edge squares, missing coverage, flags at the thresholds, scores and plans identical with and without ground cover, square counts unchanged, kit notes and README sentence, API fields, `/grid/landcover` under 100 KB, the why-none numbers equal the species table (slope limits 15 to 70). 414 tests pass.

## Thesis limits to state
RF labels derive from rules; weights are provisional; pH is not scored; slope comes from ~100 m cells; soil texture mapping is unverified;
sign-off status as of the defense date; GPS accuracy untested; field checks carry a name only (no login) and are not yet used to change any score;
street/landmark search relies on OpenStreetMap coverage (not authoritative, off by default); a typed UTM coordinate is assumed to be WGS84 zone 51N.
