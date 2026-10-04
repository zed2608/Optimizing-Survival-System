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

## Repo map (as of 2026-10-04)
- `api.py` - current FastAPI app (`POST /api/plan-event`, SQLite, K-Means). `optimization.py` - matching (to be rewritten, see below).
- `main.py`, `evaluate_system.py`, `train_suitability_model.py` - STALE legacy; do not extend. `train_model.py` - current 20-class RF (to be replaced).
- `backend/app.py` - Flask CSV server the dashboard still calls (`127.0.0.1:5000/api/points`). Replace with the FastAPI endpoints.
- `frontend/` - React 19 + Vite + Leaflet. `frontend/src/App.jsx` scores species in JavaScript (to be replaced by API calls).
- `pipeline/` - NEW Day 1 scripts. `data/raw/` inputs, `data/processed/` outputs (+ `optimizing_survival.db`), `data/config/` weights.
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

## Current status and next tasks
Day 1 DONE: loader, site grid rebuild, QA. **Next: Day 2** - see `docs/FOUR_DAY_PLAN.md` (tasks and acceptance criteria).
When you finish a task: run QA/tests, update this "status" line, commit, and summarize what changed and what is still unverified.
Ask before changing the schema in `data/processed/` or the meaning of any column.
