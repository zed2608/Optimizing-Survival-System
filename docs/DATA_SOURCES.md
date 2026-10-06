# External data sources

Only data that comes from outside the project is listed here. The species values and their sources are in `data/processed/species_sources.csv` (see CLAUDE.md); site inputs (elevation, soil code, zoning, barangays) are the files named in CLAUDE.md.

## ESA WorldCover 10 m 2021 v200 (satellite land cover) - used for ground-cover flags only

| Item | Value |
|---|---|
| Product | ESA WorldCover 10 m 2021 v200 (land cover map, 11 classes, 10 m, based on Sentinel-1 and Sentinel-2) |
| DOI | 10.5281/zenodo.7254221 |
| Licence | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| Attribution text (shown in the dashboard under More and in the ground-cover legend) | (c) ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium |
| Tile used | `ESA_WorldCover_10m_2021_v200_N12E120_Map.tif` (3 x 3 degree tile, lon 120-123, lat 12-15, EPSG:4326, cloud-optimised GeoTIFF, 30.8 MB, nodata 0) |
| URL | https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N12E120_Map.tif (data-access page: https://esa-worldcover.org/en/data-access) |
| What was downloaded | one window of that tile (the grid's bounding box plus 0.004 degrees, lon 121.1044-121.2558, lat 14.6384-14.7439, 1,817 x 1,267 pixels, 0.13 MB) with `python pipeline/landcover.py clip` |
| Where it is kept | `data/external/worldcover/worldcover_2021_v200_sanmateo.tif` (git-ignored: `data/external/` and `*.tif`) |
| Download date | 2026-10-06 |
| Class codes | 10 tree cover, 20 shrubland, 30 grassland, 40 cropland, 50 built-up, 60 bare / sparse vegetation, 70 snow and ice, 80 permanent water bodies, 90 herbaceous wetland, 95 mangroves, 100 moss and lichen (Product User Manual V2.0, table 3) |
| Accuracy statement | "resulted in a global overall accuracy of 76.7%" for the 2021 map (2020 v100 map: 74.4%). Source: Product Validation Report V2.0, section 1 (validated independently by Wageningen University and IIASA), https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/docs/WorldCover_PVR_V2.0.pdf, repeated on https://esa-worldcover.org/en/data-access |
| Product User Manual | https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/docs/WorldCover_PUM_V2.0.pdf |

**The accuracy is global.** It says nothing about San Mateo in particular; per-class accuracy differs (bare / sparse vegetation and built-up are often confused with each other and with grassland). The dashboard therefore says "about 76.7% accurate worldwide ... check on the ground". No local accuracy has been measured.

**How it is used** (`pipeline/landcover.py`):
1. `python pipeline/landcover.py clip` (needs the internet once) saves the window.
2. `python pipeline/landcover.py compute` (offline) counts, for each of the 8,088 grid squares, the 10 m pixels whose centre lies inside the square (centre +/- 50 m, worked out in metres in UTM 51N) and writes `data/processed/site_landcover.csv`, the table `site_landcover` of `optimizing_survival.db` and `landcover_report.txt`. Shares are over valid pixels; a square with less than half of its footprint covered keeps its shares empty (never zero).
3. Provisional flags, information only (`LC_CFG` in `landcover.py`): `ground_bare` (bare / sparse share >= 50%), `ground_built_up` (built-up >= 50%), `ground_water` (permanent water + herbaceous wetland + mangroves >= 30%), and an information line (not a flag) when tree cover >= 50%. They appear in `/rank`, plan items, the field kit (flags and notes) and the dashboard.
4. **No score, ranking, eligibility, plan composition or square count depends on ground cover** (tested in `tests/test_landcover.py`).

## LGU soil map (Bureau of Soils and Water Management) - the soil layer of the scores (round 11, PROVISIONAL)

| | |
|---|---|
| What | "Soil Map, Municipality of San Mateo, Province of Rizal". Printed source line: "Source of Information: Bureau of Soils and Water Management, Soil Map of Rizal Province". |
| Where we found it | CLUP 2021-2031, Volume 1, Final Report, **Figure 1-3** (PDF page 28, printed page 1-17, captioned "Source: 2010 CLUP"), and **LCCAP 2021-2025, page 10**. Both pages hold the same scanned picture (1255 x 887 pixels, JPEG; 97.5% of the pixels are identical). The CLUP copy is the one used (equally sharp: Laplacian variance 1459.5 against 1460.2; it carries the figure number and caption). A 300 dpi render of a page only enlarges this picture, so the native picture is read. |
| Files | `data/external/lgu/` (git-ignored): `CLUP__1_.pdf`, `SAN_MATEO_LCCAP_2021-2025.pdf`, `San-Mateo_DRRMPlan_2022-2024.pdf`, the 300 dpi page renders and the extracted `clup_soilmap_native.jpeg`. `python pipeline/lgu_soil.py render` makes the renders and the native pictures (needs `pip install pymupdf`). |
| Our work | `python pipeline/lgu_soil.py compute --out data/processed [--qa-dir DIR]` writes `data/processed/site_soil_lgu.csv` (point_id, soil_series, soil_texture, purity, valid_share, soil_filled) and `soil_lgu_report.txt`; `rebuild_site_grid.py` (SOIL_SOURCE = "lgu") adds `soil_series_lgu`, `soil_texture_lgu`, `soil_purity`, `soil_source` to the grid and keeps the legacy columns. |
| Status | **Provisional.** It is a scan, digitized by us (about 13 m per pixel, colours read from the printed legend), and the agriculturist has not verified it. The old layer (four world-soil-database codes with legacy textures, about 1 km blocks) is also unverified and is kept as `soil_code`, `soil_name_legacy`, `soil_texture_legacy`. |

**Georeferencing** (all distances in EPSG:32651). The frame carries graticule lines at 121 08', 121 12' (labelled) and a middle meridian (unlabelled, found half way: the spacings are 279.0 and 278.4 px) and at 14 40', 14 42'. They were found by line detection (meridians at x = 351.1, 630.1, 908.5 px; parallels at y = 308.0, 594.6 px) and give an affine fit of 12.88 m per pixel with a **residual of 1.6 m on average (2.3 m at most) at the six control points**. The municipal outline drawn on the map was then compared with the union of the barangays of `data/BRGY_BOUNDARY.shp`: the map colours only part of the municipality (the upper watershed area in the north-east is drawn dashed and left white), so the comparison uses the part of the barangay union inside the map's extent: **IoU 0.834**, and on the sides the two outlines share (89% of the outline points) they are on average **164 m** apart (95th percentile 337 m). A shift of the whole map by 250 m would raise the IoU only to 0.877 and lower the mean outline distance to 111 m; that was **rejected** (more than 150 m, and the graticule is exact to 2 m), so the graticule fit is the one used. The remaining 164 m is a difference between the two drawn outlines, not a placement error that a shift could remove. The map covers 56.9% of the municipality: 3,393 of the 8,088 grid squares (the eastern watershed) lie outside it and have **no soil texture** (never filled, never guessed).

**Classification.** The eight legend swatches are read from the picture (median colour of each swatch) and every map pixel gets the nearest legend colour in CIELAB, or none when it is farther than Delta E 40 from every legend colour (black lines, text, red roads, blue rivers, the legend box, the landfill circle, white paper). Then: the outline of the coloured area is found (an opening of 9 px removes thin lines and text); pixels outside it are dropped; an 11 px majority filter lets the area colour outvote roads and rivers; thin red and orange structures (5 px opening) are roads, not soil; blobs of the road-like colours must be big (red Antipolo Clay Loam at least 1,300 px, orange Marikina Clay Loam at least 700 px, pale Quingua Sandy Loam at least 300 px, others 150 px; the real red areas measure 1,513 and 10,589 px, the red road patches in the urban west 166 to 1,092 px); every remaining gap inside the outline takes the nearest valid class within 14 px. All numbers are in `LGU_CFG` of `pipeline/lgu_soil.py`.

**Per square.** The pixels whose centre lies inside the square (centre +/- 50 m) vote; the series is the majority class; `purity` = its share of the valid pixels; `valid_share` = valid pixels over all pixels of the footprint; a square with `valid_share` below 0.30 takes the series of the nearest valid square within 300 m (`soil_filled` = 1), else it stays empty.

**Series and texture table (PROVISIONAL, for the agriculturist to confirm)**, `SERIES` in `pipeline/lgu_soil.py`:

| Legend series | Texture used | Squares (of 8,088) |
|---|---|---|
| Antipolo Clay | Clay | 2,903 |
| Antipolo Clay Loam | Clay Loam | 146 |
| Binangonan Clay | Clay | 789 |
| Marikina Clay Loam | Clay Loam | 0 (a small strip at the north-west tip of the map, outside our squares) |
| Marikina Loam | Loam | 254 |
| Marikina Silt Loam | Silt Loam | 502 |
| Novaliches Clay Loam | Clay Loam | 26 |
| Quingua Sandy Loam | Sandy Loam | 75 |
| (outside the soil map) | none | 3,393 |

**How the texture is matched to a species** (`SOIL_COMPAT` in `pipeline/score_sites.py`, PROVISIONAL). A species lists the textures its source names (`soil_textures`, e.g. "Loam;Sandy"). A site texture counts as a match when the species list holds any word on its row:

| Site texture | Matches species that list | Why |
|---|---|---|
| Clay | Clay | the rule of before (the same word) |
| Clay Loam | Clay Loam | the rule of before |
| Loam | Loam | the rule of before |
| Silt Loam | Silt Loam or Loam | a silt loam is a loam; no species text names silt, so in practice it matches the species that list Loam |
| Sandy Loam | Sandy Loam or Sandy | a sandy loam suits species that list the plain "Sandy" |

A mismatch only lowers the soil factor (0.25 instead of 1.0; soft mode, unchanged) and is flagged `soil_unverified_mismatch`. **A square with no texture is never scored as a mismatch**: the soil term is not evaluated for it (the same as the old "not set"), so the term leaves the weighted mean; this can move S slightly either way. Pairs whose soil term was evaluated from the LGU map carry the flag `soil_provisional` ("Soil from the LGU soil map, digitized by us: provisional"). No species soil text mentions silt or silty, so `pipeline/ingest_species.py` only gained the word "Silt Loam" in its vocabulary and the species table is unchanged (`soil_map_review.csv` lists no change).

**What changed compared with the legacy layer** (all 8,088 squares): 4,426 squares have a texture in both layers and 4,014 of them changed texture (3,381 Clay Loam to Clay, 148 Clay Loam to Loam, 268 Clay to Silt Loam, 88 Clay to Loam, 75 Clay to Sandy Loam, 52 Clay to Clay Loam, 2 Clay Loam to Silt Loam); 3,390 squares had a legacy texture but lie outside the soil map; 269 squares had none and now have one. Of the 7,530 scored squares: 3,906 have a texture in both layers, 3,531 of them changed, 375 kept the same texture, 3,390 lost their texture (outside the map) and 231 gained one.

**Limits.** Scanned and approximate (about 13 m per pixel, JPEG); an outline difference of about 164 m between the map and our barangay outline; colour classification can confuse dense red road networks with soil, which is why the road rules above exist (checked by eye on the picture saved with the QA pictures); the map says nothing about the north-east watershed area.

## Climate: LCCAP 2021-2025 (reference only, not used in any score)

LCCAP page 11, section "F. Climate": "The climate in San Mateo belongs to the Type I climate pattern, characterized by a **relatively dry season from December to May and wet during the rest of the year**. The northeast monsoon brings cool, relatively dry winds. The municipality is not directly hit by typhoons, strong winds and low pressure systems because of the protection by the Sierra Madre Mountain ranges on the east and by the Batangas and Laguna mountains on the southwest. Cooler temperatures can be experienced at the eastern highland section of the municipality."

LCCAP page 12, chart "Temperature - Rizal, Philippines" (monthly values printed on the chart; it is labelled for Rizal, not for San Mateo alone):

| Month | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| High (deg C) | 26.2 | 27.4 | 29.2 | 31.0 | 31.4 | 30.8 | 29.6 | 29.4 | 29.5 | 28.9 | 28.4 | 27.3 |
| Low (deg C) | 21.9 | 21.7 | 22.4 | 23.2 | 24.0 | 23.8 | 23.3 | 23.5 | 23.1 | 23.3 | 23.3 | 22.8 |

(The same page has a wind chart: 6.1 to 11.7 km/h, highest from November to February.) Nothing in the scoring, the thresholds or the weather advice uses these values or the season months. A search of the code, docs, kit text, advisory notes and dashboard text found no other statement of dry or wet season months, so there was nothing to correct (the species planting months May to September come from the species sources and are unchanged).

## Species data release v1.0-review (frozen for the agriculturist's review, 2026-10-06)

| | |
|---|---|
| Tag | `v1.0-review` (the tag of the data, in `dataset_versions`, `dataset_release.txt`, `GET /health`, Known limits and the dashboard's Dataset version note) |
| Species file | `data/raw/species_directsource.csv`, sha256 `13787b81cf3de9503a51defd5d977c7ce683686d41aaeaabe1f0889b86f9d8ec` (copied unedited from `species_directsource_v1.0-review_candidate.csv`, found in `C:\Users\user\Downloads`) |
| Sources file | `data/raw/sources_list.csv`, sha256 `88edfb30b9dc92c6020d4991636ce608a252f18f01d7edeb6c59e9dd06210e23` (from `sources_list_v1.0-review_candidate.csv`; byte-identical to the file it replaced) |
| Combined hash | **`34964a09fe44`** = the first 12 characters of sha256(species sha256 text + one newline + sources sha256 text) |
| Content | 45 species, 2,347 cited cells, 190 ingest findings (34 high, 51 medium, 8 low, 97 info), listed in `data/processed/dataset_release.txt` and `ingest_report.csv` |
| Status | **Not signed off.** Frozen so that the agriculturist reviews one fixed version; weights, tag maps and soil are provisional. |

**What changed since the draft (`v0.1-draft`)**: two cells of the species file. 1) *Palosapis* `annual_rainfall_max_mm` was removed (it was 3500, cited to the Anisoptera thurifera page of The Ferns; the cell is now `-`, i.e. missing, never guessed). 2) The *Batikuling* `Sexuality` citation URL was repaired (`Dioecioushttps [Source: //tropical.theferns.info/...]` is now `Dioecious [Source: https://tropical.theferns.info/...]`; the value was already read as Dioecious, the citation is now a clean URL and no longer flagged `truncated_url` / `url_missing_scheme`). Effect on `species_clean.csv`: only Palosapis `rain_max_mm` (3500 to empty), `n_cells_cited` (52 to 51) and `confidence_r12` (0.154 to 0.157). **Every one of the 338,850 site scores S and every confidence is identical** to before; the `breakdown_json` texts differ only in renumbered source ids (the removed cell shifts the ids that follow). Rain is not scored.

**Known issues left for the agriculturist** (counts from the ingest report): 34 cells cite a file that was not provided (`file_source_not_provided`, all Batikuling: "RISE Volume 29 No. 3 - Batikuling (Litsea leytensis Merr.).pdf"); 30 cells cite sources outside the supplied SOURCES list (`off_list_source`); 20 non-standard citations (`nonstandard_citation`); 6 species with no Type I climate preference (`no_type_I_preference`: Katmon, Batikuling, White Lauan, Red Lauan, Bagtikan, Apitong); the Batikuling soil text "Top soil and manure 10:1" is unmapped to a texture (`soil_text_unmapped`). Also informational: the endangered scheme (DENR or IUCN) is mostly unnamed (44 `scheme_not_named`).

**How to reproduce**: `python pipeline/ingest_species.py --input data/raw/species_directsource.csv --sources data/raw/sources_list.csv --out data/processed --tag v1.0-review`, then `score_sites.py`, `score_purposes.py` and `qa_day1.py` (`make_pair_table.py` does not work with the unconfirmed squares since round 7a and nothing uses its output; it was left alone). `/health` also gives `dataset_hash` (the 12-character hash), `dataset_species_file_sha256`, `dataset_sources_file_sha256` and `dataset_note`; `dataset_file_hash` stays the species file's sha256. The `#/v2` page footer (not changed) shows the tag and the species file's sha256.
