# Planting blocks (round 10a)

Status: **provisional**. Every number below is a placeholder until the licensed agriculturist signs it off (golden rule 4 in CLAUDE.md).

## Why

Before round 10a every planned point was **one tree in one 100 m square**, so 300 trees were scattered over about 300 hectares. A real planting day plants many
trees close together at the species spacing. The plan tool now plans **blocks**: one block = one 100 m grid square planted at the species spacing. `n_saplings` means
**total trees**. The old behaviour is still there as `layout_mode = "points"`; old saved plans load as points plans and keep working.

## The block model (one config block: `BLOCK_CFG` in `pipeline/palettes.py`)

| Setting | Value | Meaning |
|---|---|---|
| `block_side_m` | 100 | a block is one grid square (the grid is about 100 m) |
| `usable_share` | 0.6 | the part of the square that is planted (paths, boundaries, rocks are left out) |
| usable side | 100 x sqrt(0.6) = 77.46 m | side of the planted square in the middle of the grid square |
| `contour_slope_pct` | 30 | above this slope the block gets the note "Plant along the contour" |

For every species:

1. **spacing** = the midpoint of `spacing_min_m` and `spacing_max_m`, rounded to the nearest 0.5 m (if only one limit exists it is used; if both are missing the species
   **cannot be planned in blocks**: it is left out with a plain reason and nothing is guessed; today no species lacks both limits).
2. **trees per row = rows** = floor(usable side / spacing), at least 1.
3. **capacity** = rows x trees per row.
4. Rows run **east-west**, counted from the **south-west corner** of the planted part. A block holding fewer trees than its capacity fills row by row from the south.

### Spacing, rows and capacity of all 45 species

| id | Species | spacing_min - max (m) | spacing used (m) | rows | trees per row | capacity |
|---|---|---|---|---|---|---|
| 1 | Narra | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 2 | Molave | 5 - 8 | 6.5 | 11 | 11 | 121 |
| 3 | Dao | 15 - 20 | 17.5 | 4 | 4 | 16 |
| 4 | Banaba | 5 - 8 | 6.5 | 11 | 11 | 121 |
| 5 | Bitaog | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 6 | Kalumpit | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 7 | Duhat | 8 - 12 | 10 | 7 | 7 | 49 |
| 8 | Kamagong | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 9 | Katmon | 8 - 12 | 10 | 7 | 7 | 49 |
| 10 | Batikuling | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 11 | Palosapis | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 12 | Talisay | 8 - 12 | 10 | 7 | 7 | 49 |
| 13 | Clumping Bamboo | 5 - 7 | 6 | 12 | 12 | 144 |
| 14 | Langka | 8 - 12 | 10 | 7 | 7 | 49 |
| 15 | Guyabano | 5 - 7 | 6 | 12 | 12 | 144 |
| 16 | Atsuete | 4 - 6 | 5 | 15 | 15 | 225 |
| 17 | Cacao | 3 - 4 | 3.5 | 22 | 22 | 484 |
| 18 | Rambutan | 8 - 10 | 9 | 8 | 8 | 64 |
| 19 | Kasoy | 8 - 10 | 9 | 8 | 8 | 64 |
| 20 | Sampalok | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 21 | Yakal | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 22 | Indian/Carabao Mango | 10 - 12 | 11 | 7 | 7 | 49 |
| 23 | Santol | 8 - 12 | 10 | 7 | 7 | 49 |
| 24 | Malunggay | 2 - 3 | 2.5 | 30 | 30 | 900 |
| 25 | Star Apple | 8 - 12 | 10 | 7 | 7 | 49 |
| 26 | Banana - Saba | 3 - 5 | 4 | 19 | 19 | 361 |
| 27 | Banana - Latundan | 3 - 4 | 3.5 | 22 | 22 | 484 |
| 28 | Coconut | 8 - 10 | 9 | 8 | 8 | 64 |
| 29 | Calamansi | 4 - 5 | 4.5 | 17 | 17 | 289 |
| 30 | Papaya | 2 - 3 | 2.5 | 30 | 30 | 900 |
| 31 | Fire Tree | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 32 | Salinggogon | 5 - 8 | 6.5 | 11 | 11 | 121 |
| 33 | White Lauan | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 34 | Red Lauan | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 35 | Bagtikan | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 36 | Robusta (Coffee) | 3 - 4 | 3.5 | 22 | 22 | 484 |
| 37 | Apitong | 10 - 15 | 12.5 | 6 | 6 | 36 |
| 38 | Chesa/Tiesa | 6 - 8 | 7 | 11 | 11 | 121 |
| 39 | Avocado | 8 - 10 | 9 | 8 | 8 | 64 |
| 40 | Peacock Flower Tree | 2 - 3 | 2.5 | 30 | 30 | 900 |
| 41 | Guava | 5 - 8 | 6.5 | 11 | 11 | 121 |
| 42 | Weeping Fig (Balete) | 15 - 25 | 20 | 3 | 3 | 9 |
| 43 | Lemon | 4 - 6 | 5 | 15 | 15 | 225 |
| 44 | Balai Lamok | 6 - 8 | 7 | 11 | 11 | 121 |
| 45 | Kamias | 4 - 6 | 5 | 15 | 15 | 225 |

Capacity ranges from 9 (Weeping Fig, 20 m) to 900 (Malunggay and Papaya, 2.5 m); the median is 64.

## The plan engine in blocks mode

* **Trees per species.** The palette (same rules, caps and scores as before) shares the trees out; the shares become **exact tree counts** that add up to the number asked for.
  A species can take at most (squares it fits x its capacity) trees, so the caps are capacity-aware.
* **Blocks per species** = ceil(trees / capacity). Every block is full except the **last block, which holds the remainder**: among the squares matched for a species, the one
  with the lowest W holds the remainder, so the best squares carry full blocks.
* **Matching.** Blocks (slots) are assigned one-to-one to squares by the same Hungarian solver (or greedy), on the same cost (1 - W), the same threshold (S >= 0.50), caps, season
  filter, field-check exclusions, zoning and ground-cover flags. At most one block per square; a square marked not plantable is never used.
* **Tie-break (blocks sit together).** Squares whose W is practically equal are ordered by their **distance to the centroid of the squares of the chosen area** (distance divided
  by the largest distance, weight 1e-6 in the cost). It cannot change a result that differs by more than 1e-6 per block.
* **Plan items** add: `block_ref` (CODE-B01), `trees_planned`, `spacing_m`, `rows`, `trees_per_row`, `usable_side_m`, `row_direction`, `start_corner`, `capacity`, `layout_note`.
  The summary adds `layout` (trees, blocks, hectares, per species), `blocks_placed`, `blocks_requested`, `mean_W_trees` and a `request` snapshot used by top-ups.

## Progress and top-up

* New field-check status **`planted`** with an integer `trees_planted` (0 to the trees of the block). It is **distinct from `verified_plantable`**. The database was migrated safely
  (`field_verify.migrate`: every event copied with its id, a copy of the old file kept as `field_checks.db.before_planted.bak`, the triggers refusing UPDATE and DELETE re-created,
  `CHECK ((status = 'planted') = (trees_planted IS NOT NULL))`).
* **`GET /plans/{id}/progress`**: per block the latest relevant event; totals planned / planted / remaining / problem; blocks **done** (all trees), **partly done**, **problem** (latest check
  not plantable) and **to do**; per species; the shortfall = the trees of the problem blocks. `planted` only counts for the plan it was saved for; not plantable, needs recheck and verified are
  facts about the square and count for every plan.
* **`POST /plans/{id}/top-up`** (optional body `{"include_remaining": true}`): a new blocks plan for the shortfall (and optionally the trees not planted yet), the same campaign unit,
  dates and settings (from the saved `request` snapshot), named `"<campaign> (top-up N)"`, with `parent_plan_id` saved and shown. It never uses a square of the parent plan (or of the
  plan family), nor a square marked not plantable. Asking twice for trees an earlier top-up already covers is refused in plain words.

## Field kit

One waypoint per block in `points.gpx` / `points.kml` with the layout in the description; a new `blocks.csv` (columns of the specification, then `plan_id` and `check_code` so a filled file
can be matched to its plan); `point-list.csv` keeps its exact columns and carries the block summary in `notes`; the README explains how to lay out a block with a tape or by pacing, where
to start, how to count trees and how to bring `blocks.csv` back; the PDF has a layout diagram per species when matplotlib is installed.

## Assumptions and limits

* Midpoint spacing, 60% usable share and a 100 m block are placeholders for the agriculturist.
* The waypoint of a block is the **centre of the grid square**; the start corner is about 39 m south and 39 m west of it.
* The 100 m grid is not a surveyed parcel: ownership, boundaries and obstacles are checked on the ground.
* A top-up is planned on the same area and dates; squares outside the zoning map are used only if the parent plan could use them.
* "Planted" in `point-list.csv` of a blocks plan means all the trees of the block; use `blocks.csv` for counts.
