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
