# Optimizing Survival - tree planting decision support for San Mateo, Rizal

This is an undergraduate thesis project. It helps the Municipal Environment and Natural Resources Office (MENRO) and community groups decide **which trees to plant where**, and then helps a field team **plant them and keep count**.

Release of the data: **v1.0-review** (hash `34964a09fe44`). It is frozen for the licensed agriculturist's review and is **not signed off yet**. Weights, tag maps and the soil map are provisional.

## What the system does

1. **Scores every place for every tree.** The municipality is cut into 8,088 map squares of about 100 m. For each of the 8,010 squares where planting can be considered (6,731 inside a legal zone plus 1,279 outside the zoning map, which are flagged) and each of the 45 species, a *suitability* score S between 0 and 1 is made from rules written from the species data (elevation, slope, soil texture, distance to water). By default S is the prediction of a Random Forest that learned those rules (see Known limits below); the rules themselves stay available.
2. **Scores every tree for the goal.** Each species gets a *purpose* score P for one of three goals: urban greening, tree planting (conservation and livelihood) or watershed. The overall score is W = S x P (and W = 0 when S is below 0.50).
3. **Matches trees to places.** For a plan (for example "300 trees in Santa Ana") it chooses a mix of species and assigns them to squares so that the total W is as large as possible (the Hungarian algorithm). A **block** is one 100 m square planted at the species spacing, so 300 trees take about 15 hectares, not 300.
4. **Supports the field work.** A *field kit* (GPS waypoints, a sheet to fill in, a printed map) goes to the planting team. They record what they find (plantable, not plantable, planted with a tree count), and the system shows progress and can plan a top-up for what was lost.
5. **Shows the source of every value.** Every number shown can be traced to the paper or web page it came from, with a source rank. Missing data stays "Data Unavailable"; nothing is guessed.

## The default page

Open **http://localhost:5173/** and you get the new dashboard (`#/new`). Other addresses:

- `http://localhost:5173/#/legacy` - the old dashboard (also a small "Old dashboard" link in the sidebar's **More** menu). It still needs the small Flask server (`python backend\app.py`, port 5000).
- `http://localhost:5173/#/v2` - the first v2 page.

## Folder map

| Folder or file | What is in it |
|---|---|
| `api_v2.py` | the backend (FastAPI, port 8001). `api.py`, `main.py`, `optimization.py` and the other old scripts in the root are legacy: do not extend them |
| `pipeline/` | the data scripts: ingest, grid, scoring, matching, plans, field kits, weather advice, soil map, model comparison |
| `frontend/` | the React + Leaflet dashboards. `src/new/` is the dashboard you use; `src/App.legacy.jsx` is the old one (do not edit) |
| `data/raw/` | the two released raw files (species data and source list). Read-only: never edit |
| `data/processed/` | everything the scripts produce (scores, species tables, the release note `dataset_release.txt`) |
| `data/external/` | downloaded or supplied outside files (satellite land cover window, the LGU documents). Not in git |
| `data/field/` | the saved field checks (`field_checks.db`). Not in git: **back it up**, it cannot be rebuilt |
| `tests/` | the automatic tests (pytest and a few node tests) |
| `docs/` | `DATA_SOURCES.md` (every source and its limits), `FOUR_DAY_PLAN.md`, `PLANTING_BLOCKS.md`, `DEMO_SCRIPT.md`, `VISUAL_STYLE.md` |
| `scripts/start_dev.ps1` | starts the backend and the frontend for you |
| `CLAUDE.md` | the detailed technical notes of the project (for the AI assistant and for you) |

## Install on Windows

You need **Python** and **Node.js**. The project was tested with Python 3.14.4 and Node.js 22.12 (npm 10.9); other recent versions will probably work, but those are the ones that were tried. Open PowerShell in the project folder.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-day1.txt
cd frontend
npm install
cd ..
```

Nothing else is needed: the processed data is already in `data/processed/`.

## Start it

The easy way: `.\scripts\start_dev.ps1` (it checks everything, opens two windows, and prints the addresses). Then open http://localhost:5173/.

By hand, in two PowerShell windows opened in the project folder:

```powershell
# window 1 - the backend
.venv\Scripts\python.exe -m uvicorn api_v2:app --port 8001
# window 2 - the frontend
cd frontend
npm run dev
```

Check the backend at http://localhost:8001/health (it should say `"status":"ok"` and `"dataset_version":"v1.0-review"`) and its documentation at http://localhost:8001/docs.

**If port 8001 is busy** ("address already in use"): find out what uses it with `Get-NetTCPConnection -LocalPort 8001 -State Listen | Select-Object OwningProcess`, then `Get-Process -Id <that number>`. If it is an old copy of this backend, stop it with `Stop-Process -Id <that number>` and start again. If you want to keep it, run the new one on another port (`--port 8002`) and create the file `frontend\.env.local` with the line `VITE_API_BASE=http://127.0.0.1:8002`, then restart the frontend.

To stop everything press `Ctrl+C` in each window (or `.\scripts\start_dev.ps1 -Stop`).

## The data pipeline, in order

You only need this when the data changes. Run from the project folder (use `.venv\Scripts\python.exe` if you did not activate the environment).

```powershell
# 1. species data (release v1.0-review) -> species tables and the release note
python pipeline/ingest_species.py --input data/raw/species_directsource.csv --sources data/raw/sources_list.csv --out data/processed --tag v1.0-review
# 2. the grid of 100 m squares (slope, zones). Add --soil-source legacy the very first time, before step 3 exists
python pipeline/rebuild_site_grid.py --input backend/Working_Points.csv --landuse data/LandUses.shp --out data/processed
# 3. soil from the LGU soil map (needs the PDFs in data/external/lgu/ for the render step only), then repeat step 2
python pipeline/lgu_soil.py render
python pipeline/lgu_soil.py compute --out data/processed
# 4. satellite ground cover (needs the internet once for the "clip" step)
python pipeline/landcover.py clip
python pipeline/landcover.py compute
# 5. scores. ORDER MATTERS: the expert rules, the pair table, then the Random Forest (it fills s_prob; running score_sites.py again empties it).
#    One command runs the three steps and prints the S_SOURCE it ends with:
python scripts/rebuild_scores.py
#    (the same as: score_sites.py -> make_pair_table.py -> train_rf.py, each with --out data/processed)
python pipeline/score_purposes.py --out data/processed
# 6. quality check - it must end with "0 failed"
python pipeline/qa_day1.py --out data/processed
# 7. optional research tables: the model comparison and the matching benchmark (the pair table of step 5 is reused)
python pipeline/compare_models.py --out data/processed
python pipeline/run_plan.py --benchmark --out data/processed
```

A plan can also be made without the dashboard: `python pipeline/run_plan.py --purpose urban --n-saplings 300` (here 300 means trees, planted in blocks).

## Help, tour and user guide

The dashboard has a guided tour (Help, Take the tour again), a Help page with questions and answers, and a printable guide. All the wording lives in ONE file: `frontend/src/new/tutorial/tutorialContent.js`. To change a sentence, edit that file and rebuild the guide:

```powershell
node scripts/build_user_guide.mjs           # rewrites docs/USER_GUIDE.md from the tour and Help text
node scripts/build_user_guide.mjs --check   # fails if docs/USER_GUIDE.md is out of date
```

Do not edit `docs/USER_GUIDE.md` by hand. The Help page also has a Print this guide button.

## Tests and quality checks

```powershell
python -m pytest tests                      # 661 tests (1 skipped), 4 to 7 minutes
python pipeline/qa_day1.py --out data/processed   # data checks, must end with 0 failed
cd frontend
npm run build                               # the dashboard must build
npx eslint src/new                          # no lint problems
```

The tests use temporary copies for plans and field checks, so they do not change your saved work.

## Where the data comes from (and the credit)

| Data | Source |
|---|---|
| Species traits and every cited cell | the species dataset (release v1.0-review), each cell with its source URL and rank, see `docs/DATA_SOURCES.md` |
| **Soil** | **LGU soil map**: Bureau of Soils and Water Management, *Soil Map of Rizal Province*, printed as Figure 1-3 of the San Mateo CLUP 2021-2031 and on page 10 of the LCCAP 2021-2025. **We digitized it from a scanned picture**: provisional |
| **Ground cover** | **ESA WorldCover 10 m 2021 v200**, (c) ESA WorldCover project 2021 / contains modified Copernicus Sentinel data (2021) processed by the ESA WorldCover consortium, CC BY 4.0, DOI 10.5281/zenodo.7254221 |
| **Weather forecast** | **Open-Meteo** (open-meteo.com), a free forecast service used for the planting advice. It needs the internet |
| **Map pictures** | **Esri World Imagery** satellite tiles and OpenStreetMap tiles (c) OpenStreetMap contributors, shown by Leaflet. They need the internet |
| Boundaries and zoning | the LGU barangay boundary and land-use (zoning) files in `data/` |
| Elevation | the elevation grid of the project (`backend/Working_Points.csv`) |

## Known limits (please read)

- The scores come from **rules written from the species data, not from field survival data**. The machine-learning comparison (`data/processed/model_comparison.csv`) learns those same rules, so its very high accuracy is expected and proves nothing about real survival.
- **Weights, caps and thresholds are provisional** until the agriculturist signs off.
- **Soil pH, rainfall and temperature are not scored** (there is no real layer for them).
- **Creek and river distance is used as a soft wetness factor** (`score_sites.py`: weight 0.25 of S, 50 m from the CREEK / RIVER polygons of `data/SMR_WATERBODIES_POLY.shp`; trees that do not fully tolerate wet ground (Low or Medium tolerance) score lower within 50 m; it lowers S for 2,960 of 360,450 pairs). **The waterways map has not been validated by MENRO** (the waterways form was signed blank).
- The grid squares are about **100 m**, so a point is "this square", not an exact tree spot; check on the ground. Slope comes from these coarse squares and can under-estimate steep ground.
- The **soil map is digitized from a scan** (about 13 m per pixel) and is **blank in the north-east watershed area**: 3,393 of the 8,088 squares (42 percent) have no soil texture, and for them the soil term is simply not scored. It has not been verified by the agriculturist.
- **1,279 squares lie outside our zoning map.** The CLUP 2021-2031 shows that land as **Forest Reserve (Watershed)**, part of the Upper Marikina River Basin that the Sangguniang Bayan resolved to co-manage with DENR. They are scored but flagged: coordinate with MENRO and DENR before planting.
- **Planting months are unverified**: all 45 species have planting months from May to September only. In October and November no species is "in season" (the dashboard says so and offers a jump to the next season).
- Satellite ground cover is about **76.7 percent accurate worldwide** (not measured for San Mateo): information only.
- Some source data is unverified: 34 cells cite a file we do not have (Batikuling), 30 cite sources outside the supplied list, 20 citations are non-standard.
- **Slope rule is graded and provisional** (round 18, a team decision, the adviser confirms): a square a little steeper than a tree's limit can still pass with a lower score and a caution; much steeper is still rejected. `SLOPE_MODE = "hard"` restores the old gate. The pair table, model comparison and matching benchmark were re-run with it (the results of the hard gate are kept in the files with the suffix `_hard`). Slope is in percent everywhere. See `docs/SLOPE_RULE.md`.
- **Site suitability S comes from a Random Forest by default** (`S_SOURCE = "rf"`, round 19c). The forest is trained on the expert-rule scores (it learns the rule score S, out-of-fold on spatial folds), so it generalises those rules and copies them very closely (error 0.0006, R-squared 0.9998; 168 of 360,450 pairs change eligibility; its plans lose under 0.05% of total W when judged by the rules). It is **not an independent measurement of survival**. The hard limits (zone, elevation, steep slope) always apply first: where the rules say S = 0, the forest says 0. `S_SOURCE = "rules"` (environment variable `OS_S_SOURCE=rules` or `API_CFG["s_source"]`) uses the expert rules themselves. If the saved scores have no complete `s_prob` (for example a fresh clone, because the scores folder is git-ignored, or `score_sites.py` was run again alone) the app falls back to the rules automatically and `/health` shows a warning. Rebuild with `python scripts/rebuild_scores.py` (score_sites.py -> make_pair_table.py -> train_rf.py). See `docs/RF_SOURCE.md`.
- Field checks carry only a typed name (no login yet).
- **Interview answers are provisional** (MPDC forms of 7 Oct 2026, MAO interview of Oct 2026): zone rules and permissions, the landfill / mining food warning, the nursery list, purpose tags and species notes. They show a "Provisional" label. See `docs/INTERVIEW_FINDINGS.md` for what was applied and what is deferred.
- **Habagat (heavy rain, flooding):** for Maly, Dulong Bayan I and II and Santa Ana the ranking score W is lowered by 20% when the planting dates touch July to September. So scores in those barangays now depend on the planting month. Site suitability S does not change.
- Optional map layers: **Zoning** (Map view menu, off by default) and the field-check colours (planted, plantable, needs recheck, not plantable, water, paved / building / rock) are the same on the map, the progress tab and the field map PDF.
- The weather forecast covers 16 days and needs the internet.

## The dataset release

`v1.0-review`, frozen 2026-10-06: 45 species, 2,347 cited cells.
Species file `data/raw/species_directsource.csv` sha256 `13787b81cf3de9503a51defd5d977c7ce683686d41aaeaabe1f0889b86f9d8ec`;
sources file `data/raw/sources_list.csv` sha256 `88edfb30b9dc92c6020d4991636ce608a252f18f01d7edeb6c59e9dd06210e23`;
combined 12-character hash **`34964a09fe44`**. The full note is `data/processed/dataset_release.txt`, and the backend shows the tag and hash at http://localhost:8001/health and in **More > Dataset version**. A change to either raw file means a new tag.

## If something is not working

- **The page says the planning service is not reachable / "API off"**: the backend is not running, or runs on another port. Start it (see above) and check http://localhost:8001/health.
- **"address already in use" on port 8001**: see "If port 8001 is busy" above.
- **The map is grey or has no pictures**: the tiles need the internet. The squares and all scores still work.
- **Weather says "not available now"**: no internet and no saved forecast yet; nothing is invented.
- **"Only 0 of 45 species can be planted between ..."**: the dates are outside every species' months (October and November). Press **Jump to the next planting season**, or switch off "Only species for my dates".
- **`npm` or `node` is not recognized**: install Node.js (nodejs.org), open a new PowerShell window.
- **`ModuleNotFoundError` (for example pytest, matplotlib, cv2, fitz)**: run `.venv\Scripts\python.exe -m pip install -r requirements-day1.txt`.
- **The field kit has no printed map (PDF)**: matplotlib is not installed in the environment that runs the backend; install it as above and rebuild the kit.
- **The old dashboard (`#/legacy`) shows nothing**: it needs the small Flask server, `python backend\app.py`.
- **Tests fail right after you changed data**: some tests pin counts (8,010 scored squares, 257,869 eligible pairs, the soil counts, the release hash). Restore the data or update the numbers on purpose.
- **A field check was saved by mistake**: they cannot be deleted (the database refuses it, by design). Save a new check with a note that says what you saw.
