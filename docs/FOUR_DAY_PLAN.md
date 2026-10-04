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

## Thesis limits to state
RF labels derive from rules; weights are provisional; pH is not scored; slope comes from ~100 m cells; soil texture mapping is unverified;
sign-off status as of the defense date; GPS accuracy untested.
