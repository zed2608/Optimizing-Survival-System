# Demo script (10 minutes)

For the thesis panel or the MENRO staff. Everything below was checked against the real data of release **v1.0-review** (hash `34964a09fe44`). The numbers will be the same on your screen unless the data changes.

## Before you start (5 minutes before the demo)

1. `.\scripts\start_dev.ps1 -Demo` (the `-Demo` switch keeps field checks of the demo out of your real `data\field\field_checks.db`). Wait for "Backend ready" and "Frontend ready".
2. Open **http://localhost:5173/** in Edge or Chrome. The page opens on the new dashboard. Full screen (F11) works well.
3. Check the top right says **API connected** and the map shows squares.
4. Plans you make in the demo are saved (there is no delete button). Use a clear name like "DEMO" so you can tell them apart in Campaign Logs.
5. Today is October, and **no species is in its planting months in October**. The dashboard will say "Only 0 of 45 species can be planted ...". The first click below fixes that. Mention it: it is a real finding, not a fault.

## The walkthrough

### 1. The page and the planting window (1 minute)
- Say: "This helps MENRO choose which tree goes where in San Mateo. Every value has a source, and what is missing is shown as missing."
- Sidebar step **3 Planting window**. Press **Jump to the next planting season**. It picks **1 May - 29 Jun 2027**, where **36 of 45 species** are in season for the whole window (38 can be planted at least in part). Say: "All 45 species have planting months only from May to September in our sources, so in October none can be planted. These months come from the species sources and are not yet verified by the agriculturist."

### 2. "I have an area": area to species (2 minutes)
- Step **1 Goal**: **I have an area**. Step **2 Purpose**: **Urban greening**. Step **4**: choose the barangay **Santa Ana**.
- The right panel lists the best species. For Santa Ana the top five are **Kamagong, Weeping Fig (Balete), Indian/Carabao Mango, Chesa/Tiesa and Sampalok**; with the dates you just chose, **38 of 45** species can be planted and **37 of 45** have a suitable square there (44 if you switch off "Only species for my dates"). The suggested mix has Kamagong at 19 percent.
- Say: "Santa Ana has 60 planting squares of 100 m."

### 3. "I have species": species to area, with two species (2 minutes)
- Goal: **I have species**. Pick **Duhat** and **Kamagong**. Keep **Suits all**.
- The **Areas** tab ranks barangays: **Santo Nino** first (mean score W 0.73, all 36 squares suitable for both), then **Gulod Malaya** (0.69, 108 squares), **Guitnang Bayan II** (0.64) and **Banaba** (0.64). Click a row and the map zooms to that barangay.
- Say: "'Suits all' means both trees must suit the square, so the lowest of the two scores counts. 'Suits at least one' takes the best."

### 4. The explanation, with sources (1 minute)
- Search the bar for **5048** and press Enter (a grid point in **Malanday**, Forest Zone, 201 m high, slope 38%). Switch the panel to **Full details**; under **Kamagong** open **Why this score?**.
- It shows S = 1.00, P = 0.77, so W = 0.77, with the four terms (elevation, slope, soil, wetness; weight 0.25 each) and for each term the link to the source it came from (for example The Ferns Tropical Plant Database for elevation and slope, the NParks Flora page for soil).
- Say: "S is a rule score from the species data; P is how well the species fits the purpose. Neither is a survival rate."

### 5. The field check on grid point 5048 (1 minute)
- Still on point 5048: the **Field check** card. Type your name once, then press **Plantable**, **Not plantable** (pick a reason) or **Needs recheck**.
- Point out the line "Ground cover (satellite 2021): **64% bare**, 22% grass" and the badge "Looks bare in satellite land cover": the square sits next to a quarry. Say: "Satellite ground cover is only a hint (76.7 percent accurate worldwide); the field check settles it."
- A "not plantable" mark removes the square from rankings and plans. In demo mode this goes to a temporary database.

### 6. The Forest Reserve label and the toggle (1 minute)
- In step 4, find the switch **Include land outside the zoning map** and open its "?" help. Say: "**1,279 squares** are outside our zoning map. The CLUP 2021-2031 shows that land as **Forest Reserve (Watershed)**, part of the Upper Marikina River Basin that the Sangguniang Bayan resolved to co-manage with DENR. We score them but flag them: coordinate with MENRO and DENR before planting."
- Click a square in the east (for example grid point **12888**, Pintong Bukawe) and read "Zoning: outside our zoning map (CLUP: Forest Reserve, Watershed)". Switch the toggle off: those squares turn into grey squares and are left out.

### 7. Grid point 5474 and the "why few species" card (1 minute)
- Search **5474** (Maly, 72 m high). The panel says **0 of 45 species suit this square**. The card "Why few or no species suit this square" says: *Slope 93% is steeper than the limit of every species (highest allowed: 70%).*
- Say: "A system that only gives a ranking would show weak scores. This one says why: this square is simply too steep for every species in our data."

### 8. The soil line (1 minute)
- On 5048 (or 5474) read the header line **Soil: Antipolo Clay (clay), LGU soil map, provisional**; open its "?".
- Say: "The soil comes from the LGU soil map of the Bureau of Soils and Water Management, which we digitized from a scan. It is provisional. **42 percent of the squares (3,393 of 8,088) have no soil value**: the map is blank in the north-east watershed area. For those squares the soil term is simply not scored; we do not guess." (Search point 12446 to show "Soil: Data Unavailable (outside the LGU soil map)".)

### 9. A blocks plan with progress (2 minutes)
- Step **5 Plan**: area **Santa Ana**, purpose urban, name **DEMO**, **300 trees**. The form shows a rough estimate ("About 5 blocks of 64 trees" for the dates you chose; it uses the typical block size, not the final mix); press **Create plan**.
- Result: **300 of 300 trees in 14 blocks, 14 hectares** (six species: Kamagong 56 trees, Weeping Fig 51, Indian/Carabao Mango 50, Chesa/Tiesa 48, Sampalok 48, Salinggogon 47). Say: "A block is one 100 m square planted at the species spacing: Kamagong every 12.5 m, 36 trees per full block. Without blocks, 300 trees would be 300 squares, about 300 hectares."
- Open a block (the list, then click a row): the drawn **layout** shows rows from the south-west corner. Mark it **Planted** (the count box starts at all its trees), mark another **Can't plant here** (Rock or ledge). The **Progress** card shows planted, remaining and problem trees; **Plan top-up** makes a new plan, "DEMO (top-up 1)", for the trees lost.

### 10. The field kit and the weather (1 minute)
- In the result card: **Field kit**, **Build field kit**, then **Download kit**. It holds GPS waypoints (one per block), `blocks.csv` to fill in, a Google Earth file, a README on how to lay out a block, and a printed map with a layout diagram.
- The **Weather** tab: the forecast for the week with a verdict (good to plant, plant with care, avoid) and the numbers behind it (heavy rain above 80 mm in a day = avoid; under 20 mm in 7 days = plant with care). Say: "The forecast covers 16 days and comes from Open-Meteo. If it is outside our window we say so."

### 11. Campaign Logs and Analytics (30 seconds)
- **Campaign Logs**: each saved plan with its status (Active, Upcoming, Concluded), kit, progress and top-up.
- **System Analytics**: saved plans, trees planned, field kits built, field checks, **8,088 map squares = 7,530 planting squares + 558 grey squares**, and the dataset **v1.0-review, hash 34964a09fe44**.

## Backup plan if the internet is down

| Still works (it all runs on this computer) | Does not work |
|---|---|
| All scores, rankings, areas, plans, blocks, progress, top-ups | The satellite and street **map pictures** (the map is plain, squares and outlines still show) |
| Field checks, field kits (GPX, KML, CSV, PDF) | The **weather forecast**: it says "not available now" or shows a saved forecast with its age, never invented numbers |
| The explanations with source **links** (the links open only online) | Opening the source pages |
| The new dashboard, the old dashboard, the tests | The one-time satellite download of the pipeline (not needed in the demo) |

Say: "Everything you see was computed from files on this computer; only the picture tiles and the forecast need the internet."

## Questions the panel may ask, with honest answers

**The labels come from rules, so is the machine learning circular?** Yes, and we say so. The suitability labels are produced by the rules from the same raw inputs the models see, so the models can only learn the rules back. On clean labels the Random Forest reaches about 0.999 accuracy; that measures how well it copies the rules, not how well trees survive. We kept the comparison to show that the rule scores are stable and that nothing special is lost by using simple rules. There is no field survival data yet to test against.

**Why is Random Forest not clearly better than a decision tree?** After the refresh on the final data (30,000 sampled pairs, 5 folds): in the random and spatial tests the Random Forest and the decision tree are within the fold-to-fold spread of each other (for example, 5 percent label noise: accuracy 0.948 against 0.942, spread about 0.003). For species the model has never seen, the decision tree (0.979) and logistic regression (0.983) are slightly *ahead* of the Random Forest (0.969). The rules are simple thresholds, which a decision tree represents exactly. So we use the transparent rules in the dashboard and report the comparison as it is.

**Why are the weights provisional?** The weights (equal quarter weights for elevation, slope, soil and wetness; the purpose weights; the 0.50 cut-off; the species caps) are our proposals, not from a source. They are marked provisional until the agriculturist signs off. A sensitivity test is saved in `data/processed/purpose_sensitivity.csv`.

**Why is soil pH not scored?** There is no real pH layer for San Mateo. The old grid had a random pH column that we found and removed. Rainfall and temperature are not scored for the same reason.

**What about the gaps in the zoning map?** 1,279 squares lie outside every zoning polygon. The CLUP shows that land as Forest Reserve (Watershed). We keep them (flagged) because planting there may be exactly the point of a watershed project, but they need MENRO and DENR agreement. Squares in a named non-planting zone (special reserved, industrial, commercial, quarry, landfill: 558) are never scored.

**The soil map was digitized from a scan; how reliable is it?** It is provisional. We placed the scan using its own graticule lines (accurate to about 2 m at the control points) and read the legend colours with a computer. The map outline and our barangay outline differ by about 164 m on average on the sides they share. **3,393 of 8,088 squares (42 percent) are blank** because the map does not cover the north-east watershed area. A texture mismatch only lowers a score (it never removes a species), and a missing soil never counts against a square. Strict soil mode would remove about 98,000 of the 229,000 suitable square-species pairs; we did not choose it because the soil layer is unverified.

**Is a 100 m square precise enough? What about GPS?** No: a square is an area, not a tree spot. The field kit tells the team to check the square on the ground and allows moving the block by up to 10 m, recording the real position. Phone GPS is accurate to a few metres in the open and worse under trees, near buildings or in a gully; we have not tested the kit files on a phone yet.

**How accurate is the satellite ground cover?** The ESA WorldCover 2021 map states **76.7 percent overall accuracy worldwide**; it is not measured for San Mateo, and bare ground, built-up and grass are often confused. So it only adds flags and never changes a score.

**What data is unverified?** (1) 34 cells for Batikuling cite a PDF file we do not have. (2) 30 cells cite sources outside the supplied source list and 20 citations are non-standard. (3) The soil mapping (both the old four-code layer and the new LGU map). (4) The planting months, which are May to September for every species in the sources. (5) Six species have no Type I climate preference. (6) The Batikuling soil text "Top soil and manure 10:1" cannot be mapped to a texture. All are listed in the release note (`data/processed/dataset_release.txt`) for the agriculturist.

**Is the data final?** No. It is release `v1.0-review`, frozen so that one fixed version can be reviewed. A change to either raw file means a new tag.
