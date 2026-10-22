# Tree Planting Decision Support: user guide

San Mateo, Rizal. Municipal Environment and Natural Resources Office (MENRO).

This guide is built from the same text as the in-app tour and the Help page (`frontend/src/new/tours/tourDefs.js` for the tours, `frontend/src/new/tutorial/tutorialContent.js` for the questions). Do not edit it by hand: change that file and run `node scripts/build_user_guide.mjs`.

## Contents

1. [The tours, step by step](#the-tours-step-by-step)
2. [Questions and answers](#questions-and-answers)
3. [Glossary](#glossary)

## The tours, step by step

### Header and settings

The top bar: pages, settings, connection.

#### Top bar

**1. Whose tool this is**

This is the LGU San Mateo badge. The tool was made to help MENRO decide which trees to plant, and where.

**2. Four pages**

Active Studio is the map where you plan. The cloud shows the Weather for the week. The clipboard lists your saved plans (Campaign Logs). The bars count what exists (System Analytics).

*Watch for:* A tour always explains the page you are on.

**3. Settings**

This button opens one menu: theme, language, animations, and the Welcome, Tours and Help links.

**4. Light or dark**

Choose the light or the dark look. Dark is easier on the eyes at night and saves battery on some phones.

**5. Language**

English is the default. Pick Taglish to read the whole screen in Filipino.

**6. Animations**

Auto follows your device. On always shows motion. Off removes every animation and blur: use it on a slow phone.

**7. Welcome**

Plays the short introduction slides again.

**8. Tours**

Opens the list of tours: one for every page and a short one for every section.

**9. Help**

Questions and answers, a glossary of the words used, and a guide you can print.

**10. Connection**

Green means the planning service answers. If it says offline, check your connection: the map keeps what it already loaded.

**11. Demo notice**

This public demo uses provisional data that the agriculturist has not signed off. What you enter here is reset regularly.

### Studio: the control panel

Goal, purpose, dates, species or area, plan.

#### Goal and purpose

**1. The control panel**

You work from top to bottom: goal, purpose, planting window, species or area, plan. One step is open at a time and a closed step shows your choice in one line.

**2. Show hints**

Turn this on to see a small ? next to the main controls. Each ? explains that control in a sentence.

**3. Step 1: Goal**

Choose what you want to know. This is the first question of the system.

**4. Two ways in**

“I have species” shows where the species you pick can grow. “I have an area” ranks the best species for an area you choose.

**5. Step 2: Planting purpose**

The purpose changes which species rank best.

**6. Three purposes**

Urban greening: shade and low root-damage risk. Tree planting: conservation and livelihood. Watershed: holding soil on slopes and by waterways.

#### Planting window

**7. Step 3: Planting window**

Your start and end dates. They never remove a species and never change a score: they only add a label (In season, Outside best months) and the order.

**8. Start and end**

Pick the first and last day you could plant. Up to 366 days, and the start cannot be in the past.

**9. The month strip**

Twelve letters, January to December. A ring marks the months your dates touch. Species list their own best months, so you can compare.

**10. Jump to the next season**

Sets the dates to the 60 days with the most species in their best months. Most species are in season from May to September.

#### Species (I have species)

**11. Step 4: Species**

With “I have species” this step has four small steps: choose species, where to look, mark on the map, create the plan.

**12. The four small steps**

The numbers show where you are. A finished step shows a tick and your choice; tap it to go back.

**13. One species or several**

Choose one species, or several that grow well together. For several, the system suggests companions of your main species.

**14. Find a species**

Type part of a common or scientific name. The funnel next to it opens the filters.

**15. Filter by trait**

Narrow the list by a trait such as fruit-bearing, timber or ornamental, or to species the LGU nursery has. The traits are provisional.

**16. The species list**

Tick the species you want. The “i” opens its card. The badge says if it is in season, partly, or outside its best months for your dates.

**17. Where to look**

Look in the whole municipality, or only one barangay or one zone.

**18. Mark on the map**

Click corners on the map to draw the area where you want to plant, then finish it. Or use one point. The best places inside it are listed on the right.

**19. Create the plan**

The last small step lists your choices and takes you to Step 5, the plan.

#### Area (I have an area)

**20. Step 4: Area**

With “I have an area” you choose the area and the system ranks the species for it.

**21. Three ways to choose**

Click a point, pick a barangay or zone from a list, or draw a shape on the map.

**22. Draw an area**

Click corners on the map. Finish area closes the shape and locks it. Undo removes the last corner. Start again clears it.

**23. What the area holds**

This example area has been chosen for you. The summary counts its squares. A square is COUNTED when its centre is inside, or at least half of it is covered; a square only touched is listed apart.

*Watch for:* The dashed grey line on the map marks squares that were only touched.

#### Plan

**24. Step 5: Plan**

Turn your choices into a planting plan: how many trees, in which blocks. A block is one 100 m grid square planted at the species spacing.

**25. Campaign name**

The name of the planting event, saved with the plan.

**26. Assigned unit**

The team that will do the planting. Optional.

**27. Number of trees**

How many trees in total, 1 to 2000. Or give each species its own number if you chose your own species.

**28. What the plan will use**

The area, the dates and the species, and how many suitable squares are available.

**29. Create plan**

This button saves the plan on the server. The tour only shows it: it will not press it.

*Watch for:* After a plan is made, Make another plan starts again and the plan stays saved in Campaign Logs.

#### The More list

**30. More**

Known limits, data credits, the dataset version and the field checks live here.

**31. Known limits**

What the system does not know or does not do, in plain words. Read this before you trust a result.

*Watch for:* Distance to creeks and rivers is used as a soft wetness factor (50 metres), but MENRO has not answered the waterways question, so this layer is not checked.

**32. Data credits**

Where each kind of data comes from, with its licence.

**33. Dataset version**

The version of the species data. It is a review release: the agriculturist has not signed it off.

**34. Field checks**

What the field team saw on the ground: counts, a download of all checks, and an import of a filled sheet.

### Studio: the map

Search, zoom, my location, layers, legend, colours, right-click.

#### Search

**1. Search the map**

Type a barangay, a species, a point number, or coordinates such as 14.69, 121.12. Press Ctrl and K to jump here. Choosing a result moves the map and opens its panel.

*Watch for:* Places such as streets only work if the online place search is switched on.

#### Map controls

**2. Zoom**

Plus and minus zoom the map. You can also pinch with two fingers, or scroll with the mouse. Zoom in far enough to see single 100 m squares.

**3. My location**

Moves the map to where you are, with a blue dot. It needs a secure (HTTPS) page and your permission. Your position stays in this browser and is never sent anywhere.

**4. Set my location on the map**

If your device cannot find you, tap this and then tap the map where you are.

**5. Map view**

Opens the map options: Simple or Detailed, the map type, and the extra layers.

**6. Layers and detail**

Simple shows coloured squares, outlines and names. Detailed adds every field-check symbol, the tree codes and the grey squares. You can also switch the satellite picture, the zoning colours and the ground-cover layer.

**7. The legend button**

Opens the legend: what the colours of the map mean.

**8. Hide the control panel**

Hides or shows the left panel so the map has the whole screen. Your choices stay.

#### Colours and symbols

**9. What the colours mean**

Each square is a 100 m by 100 m piece of planting zone. Green (Good) means the species match is 55% or more, orange (Moderate) 35% to 55%, red (Poor) below 35%. Grey means not suitable here, or no value.

*Watch for:* A colour is advice about the land, not a promise that trees will live.

**10. The coloured squares**

Zoom in and the colours become squares. Hover or tap one to see its barangay, its score and its best species. Click it to open its panel on the right.

**11. Barangay names and outlines**

The thin lines are the barangay boundaries and the names sit inside them. The thick outline is the edge of the municipality.

**12. Field-check symbols**

When people check a square on the ground, a mark is drawn on it. Every mark is the same violet; the SHAPE tells the status: a tick: planted, a ring: marked plantable, a question mark: needs recheck, a cross: not plantable. The words are always written next to it.

**13. Planned blocks**

After you make a plan, its blocks are drawn as shapes with the number of trees, one shape for each species. A dotted ring marks land outside the zoning map.

#### Right-click menu

**14. Right-click or press and hold**

A menu opens for the square you pressed: where it is, its zone, the species here, and the field-check buttons. This is the example point.

*Watch for:* The tour only shows the menu. It never presses a field-check button.

### Studio: the point panel

What a clicked square tells you (uses the Example point).

#### The simple view

**1. The Example point**

This panel opens when you click a square. The tour uses a fixed Example point where many species fit, so it never depends on what you selected.

**2. Simple or Detailed**

Simple uses plain words. Detailed shows the numbers, the month strips and where every value comes from.

**3. Where this is**

The barangay of the square, with a short note about its land when there is one.

**4. The verdict**

One sentence: how good this place is for the top species, the overall match in percent, and whether it is in its planting months. “Overall match” combines how well the site suits the species with how well the species suits your purpose.

**5. Field check**

What the field team saw here, if anyone has checked it: planted, marked plantable, needs recheck, or not plantable. The button opens the menu to record a check.

*Watch for:* A not-plantable mark can leave the square out of rankings and plans; the other marks never change a score.

**6. Best species for this spot**

The species that suit this square, best first, and how many of the 45 suit it. Each row has a colour bar for the match, a season badge and a pH icon.

**7. One species**

Name (tap it for the species card), the match as Good, Moderate or Poor with its percent, and the season: In season, Partly, or Outside best months. Outside the best months you can still plant, but expect more watering and more losses.

**8. Details**

Opens the extra lines of this species: the numbers, the month strip, the flags, and why the score is what it is.

#### The detailed view

**9. Land details**

Coordinates, elevation, slope, zoning, soil and satellite ground cover for the square. Anything that needs a permit or care is flagged.

**10. Soil pH (an estimate)**

The pH of the soil here comes from SoilGrids, a world map with 250 m pixels. It is an ESTIMATE and “not certain”: measure on site with a pH kit before you rely on it. It is advice only and never changes a score.

**11. The numbers**

S is site suitability, P is purpose fit, W is the overall score (S times P, and 0 when S is below 0.50). Confidence says how many of the facts behind it are sourced.

**12. The month strip**

Twelve letters from January to December. Filled letters are the best planting months of this species; a ring marks the months of your dates.

**13. Why this score?**

Opens the breakdown: each term, its weight and its source.

**14. The Random Forest line**

The site suitability comes from a Random Forest, a computer model that learned from the expert rules. Hard limits such as zone, elevation and steep slope always apply first. It does not measure real survival.

#### The species card

**15. The species card**

Opens from any species name. It lists what is known about one species, each value with its source link and rank. A missing value says Data Unavailable.

**16. Planting stage and timing**

Germination, propagation, depth, method and spacing, and the planting months with a month strip for your dates.

**17. Works well with**

Species that grow well beside this one, with the reason in one line. A partner named in the sources says so; the rules are provisional.

**18. Ways to improve survival**

Short advice for this species, for example about watering, shade or grafted stock. It is advice only, still to be confirmed by the agriculturist.

### Studio: a saved plan

The plan panel: Plan, Field kit, Progress (opens your latest saved plan).

#### Plan

**1. The plan in three numbers**

Trees, blocks and hectares. A block is one 100 m square planted at the species spacing.

**2. Three tabs**

Plan shows what to plant where. Field kit builds the files and the planter link for the team. Progress counts what has been planted.

**3. Good to know**

Short notes that need attention: zoning, steep slopes, satellite ground cover, the season.

#### Field kit

**4. The field kit**

Build the kit to get points for a GPS app, a Google Earth file, the point list, a printed map and instructions. The tour only shows it: it will not build anything.

**5. Planter link**

A page for the planting team to open on a phone. The link works for a limited time and can be switched off. A QR code appears once the link exists.

#### Progress

**6. Progress**

Counted from the saved field checks of this plan: planted, partly done, problem and to do, with a button to plan a top-up for trees that could not be planted.

### Weather

The week ahead at one place, with advice for planting days.

#### Place and purpose

**1. The Weather page**

The next seven days at one place, a plain verdict for planting this week, and the species that suit the week. It is a planning aid, not a guarantee.

**2. Where**

Pick the place: the centre of San Mateo, a barangay, the last point you clicked, or the middle of a plan.

**3. Planting purpose**

The purpose orders the species lists below.

**4. Simple or Detailed**

Simple gives short lines. Detailed adds each species’ drought tolerance, months and sources.

#### The week

**5. Today at a glance**

The sky picture shows today’s rain amount and the temperatures. Only rain, the highest and lowest temperature are forecast; there is no wind or chance of rain here.

**6. The seven days**

One column per day: the rain amount in millimetres, and the highest and lowest temperature.

**7. Day words**

Dry is under 1 mm, light rain 1 to 10 mm, rainy 10 mm or more. Heavy rain above the limit shown makes the week “avoid”.

**8. The verdict**

Good to plant, Plant with care, or Avoid this week, with the reasons and the numbers behind them. A dry week under 20 mm needs watering.

**9. The week in numbers**

Rain over seven days, the wettest and hottest day, and the limits the verdict uses. These limits are provisional.

#### Species for the week

**10. In their best months**

Species that are in their planting months this week and are not hit by a weather warning, best match first.

**11. Only if you can water**

Outside their best months but with High drought tolerance. You can plant them only if you are able to water.

**12. Source and last update**

Where the forecast comes from. When the service is busy the page shows a saved copy and says “Last updated …, may be out of date”; Try again loads it afresh.

### Campaign Logs

Your saved plans, their status and progress.

#### The list of plans

**1. Campaign Logs**

Every plan you saved, newest first, with its dates, status and field kit. Nothing here changes a plan.

**2. Filter by status**

Active, Upcoming, Concluded, or No dates: worked out from the dates saved with each plan.

**3. Search**

Type part of a campaign name, a unit or a plan id.

**4. Your plans**

One card per saved plan. When there is none, this says so and offers a button to go and make one.

**5. One plan**

The name, unit, dates and status chip, the plan id, whether a field kit was built, and a weather card for the planting days.

**6. Open on map**

Opens the plan in Active Studio, with its blocks on the map. Progress and top-up counts what the field team has planted.

**7. Go to Active Studio**

With no plans yet, this button takes you to the studio to make the first one.

### System Analytics

Counts of what exists, how to read each chart.

#### Filters and numbers

**1. System Analytics**

Counts of what exists: suitable squares, soil pH estimates, plans and field checks. Nothing here is forecast and nothing here changes a score.

**2. Filters**

Narrow the charts by barangay or species, and the activity by dates. Clear filters shows everything again.

**3. Six big numbers**

Squares scored, species, suitable squares, plans, trees planned and field checks. A suitable square has a site score of 0.50 or more for at least one species.

#### The charts

**4. Site scores**

Bars of how many square-and-species pairs fall in each score range. A tall bar at zero means many pairs that the land rules out.

**5. By barangay**

Suitable squares compared with all squares of each barangay. Longer is more.

**6. By species**

How many squares suit each species (top ten).

**7. Soil pH estimates**

How the estimated soil pH is spread over the squares. It is an estimate from SoilGrids, not a measurement.

**8. pH verdicts**

For each species and square: inside its pH range, outside, or “not certain”. Most are not certain because the estimate has a wide margin.

**9. By zone**

Squares by land-use zone, and how many are outside the zoning map or have no soil data.

**10. Activity by week**

Plans and field checks made each week. Empty until people use the system.

**11. Trees planned by week**

How many trees the plans of each week hold.

**12. Planned and planted by barangay**

Trees planned beside trees the field teams marked as planted.

**13. Planned and planted by species**

The same comparison for each species.

#### Tables and download

**14. View table**

Shows the numbers behind the chart as a table, for reading with a screen reader or copying.

**15. Download CSV**

Saves the numbers of that chart as a spreadsheet file.

**16. No forecast**

No future is drawn here: forecasting needs survival records, and none exist yet.

### Help and the user guide

Questions, glossary, printing the guide.

#### The Help page

**1. Tour of this page**

Starts the tour of the page you came from. Each page has its own tour.

**2. All tours**

Opens the list of every tour, with a short tour for each section.

**3. Print this guide**

Prints the whole guide on A4 sheets: the tours, the questions and the glossary.

**4. Search the questions**

Type a word such as pH, check code or nursery to find the answer.

**5. Questions and answers**

Tap a question to read its answer. They are grouped by topic.

**6. Glossary**

The words this system uses, in plain language.

## Questions and answers

### Map

**Why is a point grey?**

A grey dot means no species suits that square for your purpose. A faint grey square that is not a dot is land that is never scored: cemetery and quarry land. Click it to see the reason.

**Why does a part of the map have no squares?**

Squares in the cemetery and quarry zones are never scored, so they are not coloured. Land outside the zoning map is scored but flagged. You can switch it off with “Include land outside the zoning map”.

**What do the colours mean?**

They show the overall match. Green is Good (55% or more). Orange is Moderate (35% up to 55%). Red is Poor (under 35%). Grey means not suitable here. Open the Legend button on the map to see them.

**What are site match, purpose fit and overall match?**

Site match says how well the land suits a species. Purpose fit says how well the species suits what you want, such as shade or watershed. Overall match combines the two. If the site match is under 50%, the overall match is zero. Detailed view shows the numbers. Site suitability is predicted by a Random Forest trained on the expert rules. These are saved scores; the model is not run in the app, and it is not an independent measurement of survival. Hard limits (zone, elevation, steep slope) always apply first.

**How do I show the zoning colours?**

Open Map view at the top right of the map and tick Zoning. A list shows the zones, the colours and how many squares each has. The colours follow the LGU style file. Untick it to hide the layer.

**What is in the Map view menu?**

Simple or Detailed map, the map type (satellite or street map), the field-checked points, the planned trees, the Zoning layer, the satellite ground cover layer, and the faint squares that are not planting zones. Detailed adds every field-check symbol and the tree codes.

**Is a dot an exact planting spot?**

No. Each square is 100 metres wide, so a point means “this square”. The field team checks the real spot on the ground.

### Warnings

**What does the steep slope caution mean?**

Each tree has a usual limit for how steep the land can be. A square a little steeper than that limit is not thrown out. It gets a lower score, and it only shows when it still passes. Plant on terraces or use contour planting, or choose another tree. A square much steeper is still left out. This rule is provisional until the adviser confirms it.

**What does Needs permission mean?**

The zone has a condition from the MPDC form. For example, private land needs the owner’s consent, a landfill needs DENR permission, and the Forest Reserve needs a MENRO and DENR permit. Get the permit before planting.

**What does “outside the zoning map” mean?**

About 1,279 squares lie outside our zoning map. The CLUP 2021-2031 shows that land as Forest Reserve (Watershed). They are scored but flagged. Coordinate with MENRO and DENR before planting there.

**Why does July to September look worse in Maly, Dulong Bayan or Santa Ana?**

The MAO advised that heavy rain and flooding in the Habagat months can wash out seedlings in Maly, Dulong Bayan I and II, and Santa Ana. When your dates touch July to September, the overall match there is lowered by 20%. The site match does not change. This is provisional.

**Why is there a heavy metals note?**

Food-bearing trees on a landfill or a special reserved square may take up heavy metals. The note asks you to test the produce before anyone eats or sells it. No tree is left out because of it.

**What does Check first mean?**

It lists planned trees on squares that look bare, built-up or wet in the satellite picture, or that are outside the zoning map. Press “Show these on the map” to circle them, and look at them before the team goes out.

**How reliable are the soil and ground cover lines?**

The soil comes from the LGU soil map that we digitized from a scan, so it is provisional, and there is no soil data for part of the north-east. The ground cover is a 2021 satellite picture that is about 77% accurate worldwide. Both are guides only.

### Search

**What can I type in the search box?**

A barangay (for example Santa Ana), a species name, a point number (for example 832), a plan point code from a saved plan, or map coordinates. Choosing a barangay shows its best species. Choosing a species shows where it grows. Choosing a point or coordinates opens that spot.

**Which coordinates can I type?**

Latitude and longitude such as 14.69 121.12, with or without N and E, or UTM zone 51N numbers such as 296799 1625091. If the numbers cannot be read, you get a reason and nothing is guessed.

### Using the system

**Which goal should I choose?**

Choose “I have species” when you already know what you want to plant and need to know where. Choose “I have an area” when you know the place and need to know what to plant there.

**What are the three purposes?**

Urban greening is for shade, lower root-damage risk and low upkeep in town. Tree planting is for conservation and livelihood. Watershed is for holding soil on slopes and by waterways. The purpose changes how species are scored.

**Why are some species not in their best months?**

The dates only add a label to each species (In season, Partly, Outside best months). They never hide a species and never change a score. Outside the best months you can still plant, but expect more watering and more losses.

**What does Outside best months mean?**

The sources give planting months for each species. You can still plant outside them, but expect more watering and more losses.

**How do I find a good planting time?**

In the Planting window step, press “Jump to the next planting season”. It picks the 60 days in the next year when the most species are in their planting months.

**What is the difference between Suits all and Suits at least one?**

Suits all means every species you chose must grow there, and the score is the lowest of theirs. Suits at least one means one species is enough, and the score is the highest.

**What is the difference between Simple and Detailed?**

Simple is the short view in plain words. Detailed shows every number, such as site match, purpose fit and overall match, the month strip and the sources. The map has its own Simple or Detailed choice in the Map view menu.

**What if the top bar says the service is not connected?**

The page cannot reach the data service, so the map and results cannot load. Ask the person who runs the system to start it, then reload the page.

**What are Campaign Logs and System Analytics?**

Campaign Logs lists every saved plan with its status, progress and top-up. System Analytics shows counts: the squares, the field checks and the plans, and the dataset version.

**Where do I find this help again?**

Press Help at the top right of any screen. A small question mark next to a main control opens the matching answer.

### Species

**What is on the species card?**

The planting months, how the tree grows, where it grows, its uses, partner species, notes from the agriculturist and the source of each fact. A fact with no source says Data Unavailable.

**What is Ways to improve survival?**

A short list of tips for a species or for a plan, such as mulching, a windbreak, or asking for grafted stock. A tip only appears when it applies, for example when a species has Low drought tolerance. Simple shows a few tips and Detailed shows them all.

**Does the advice change the scores?**

No. The advice is only text. The site match, the purpose fit and the overall match stay exactly the same.

**Where does the advice come from?**

Some tips come from the MAO interview. Others are general practice. Each tip shows its source. All of it is advice that the agriculturist still has to confirm.

**What is "Puwedeng samahan" when I choose many species?**

You first choose a main species. "Puwedeng samahan" then lists species that are suitable on at least half of the same squares of your area (or of the whole municipality when no area is chosen). It is only about the land. It does not yet consider canopy size, roots or shade.

**What is Works well with?**

A short list of species that can grow together with the main species, from simple starting rules about height, shade, water and roots. A label “Named in sources, check conditions” means the sources name the pair but our rules found that the conditions differ. These rules are provisional.

**What does Available in LGU nursery mean?**

The species is on the nursery list the LGU gave us. The list does not say how many seedlings are ready, so stock quantities are unknown. Kape is on the list but the variety is unknown, so Robusta is not marked.

**What are the purpose tags?**

Short labels such as fruit-bearing, timber, ornamental or biodiversity. They only help you filter the species list. They do not change any score. They are provisional.

**What are the notes from the agriculturist?**

Short advice from the MAO interview, shown on a species card and marked Provisional. They are not part of the scores.

### Plans

**How do I make a plan?**

Work down the five steps on the left: Goal, Purpose, Planting window, Species or Area, and Plan. In step 5, name the campaign, say how many trees, and press Create plan.

**How do I choose the number of trees for each species?**

With “I have species”, step 5 has one row per species with a number box. With “I have an area”, press “Choose my own species and counts”. Exactly your numbers are placed. A plan with one species, or mostly one species, shows a pest-risk warning.

**What is a block?**

A block is one 100 metre grid square planted close together at the spacing of its species. The planted area sits in the middle of the square, with an equal margin on every side for paths and rocks.

**What do Trees, Blocks and Hectares mean?**

Trees is how many trees were placed. Blocks is how many 100 metre squares are used. Hectares is the land those squares cover.

**Why were fewer trees placed than I asked for?**

There were not enough suitable squares for that species in the area, or other species took them. The result says which. Try a bigger area or other species.

### Field work

**What is in the field kit?**

A printed map (PDF), blocks.csv to fill in, point-list.csv (the older list format), points.gpx and points.kml for a map app, and a README. Each file carries the plan name and the check code.

**What is the check code?**

It is eight characters made from the plan itself. Every file of the kit carries it. When you bring a filled sheet back, the dashboard compares the code with the plan, and refuses the sheet if they differ. That stops a sheet of one plan from being saved on another.

**How does the team use the kit on the ground?**

Walk to the START point of a block and put in a stake. Plant tree 1 half a spacing east and north of it. Plant the rows from west to east, then move north one spacing. Leave the empty places empty. Count the trees really planted and write the number down.

**How do I record that trees were planted?**

Two ways. In the dashboard, right-click the block (press and hold on a phone), type your name once, press Planted and enter how many trees. Or fill blocks.csv in the field, then press “Import field checks (CSV)” under More, Field checks. Importing the same file twice adds nothing.

**What do the field-check colours and symbols mean?**

Every field-check mark is the same violet; only the shape differs. Planted is a check. Marked plantable by an observer is a ring: the mark of one person who typed a name; it is not an expert check and it never changes a score. Needs recheck is a question mark. Not plantable is a cross; the reason (water, paved, built or rock) is written in words next to it. The shape is always shown with words.

**What are the reasons for Not plantable?**

Paved, Building, Rock or ledge, Creek bank or waterlogged, Too steep, Existing tree, Owner refused, and Other. A reason is always needed.

**Why is a square marked Not plantable removed from plans?**

The field team found that it cannot be planted. New plans and suggestions leave it out. A new check with a note can clear the mark. Scores are not changed.

**How are the planted trees counted?**

Each block counts by its latest saved check. A block marked Planted counts the number of trees written. A partly planted block counts only those trees. Trees planned minus trees planted is Remaining. Trees of blocks with a problem are Problem.

**What is a top-up plan?**

A new plan for the trees lost to problem blocks, with the same campaign, dates and settings. It never uses a square of the first plan or a square marked Not plantable. You can also ask it to include the trees not yet planted.

**What if two people record different results?**

The latest check counts. If the last two come from different people and disagree, the point is shown as disputed so someone can look again.

### Weather

**What does the Weather tab show?**

The coming week for the place you choose. It gives a verdict (Good to plant, Plant with care or Avoid this week) with the rain numbers, and lists the species that suit the week. The forecast covers about 16 days.

**How does the weather affect planting months?**

It does not change a score or a best month. It only tells you if this week is good, and it lists the species that are in their best months and not hit by a warning. Species outside their best months are listed apart as Only if you can water.

### Data

**What does Provisional mean?**

It marks information that comes from an interview, a form or our own rules and has not yet been confirmed by the licensed agriculturist or the LGU. Use it as a guide, not as a final answer.

**Which data is signed off?**

The zoning rules come from answers written on a form by the MPDC (provisional), and the warnings and notes come from the MAO interview, but they are still provisional. The species data (release v1.0-review) has not been signed off by the licensed agriculturist. Distance to creeks and rivers is used as a soft wetness factor (50 metres), but MENRO has not answered the waterways question, so this layer is not checked.

**Does the system decide where to plant?**

No. It suggests. People decide, the field team checks every spot, and permits from MENRO, DENR or the owner are still needed. It does not replace the agriculturist.

**What does Data Unavailable mean?**

The information does not exist in our sources, so the system shows nothing. It never fills a missing value with a guess.

## Glossary

- **Site match**: How well the land of a square suits a species: slope, height, soil, zone and distance to creeks and rivers (a soft wetness factor, 50 metres; the waterways map is not yet validated by MENRO). It is a number from 0 to 1. A square a little steeper than the tree's usual limit can still pass, with a lower score and a slope caution.
- **Purpose fit**: How well a species suits what you want the trees for: shade in town, tree planting or watershed.
- **Overall match**: Site match combined with purpose fit. It is zero if the site match is under 50%. The map colours show it.
- **Block**: One 100 metre square planted close together at the spacing of its species. The planted area sits in the middle of the square.
- **Check code**: Eight characters made from a plan. Every file of its field kit carries it, so a sheet cannot be saved on the wrong plan.
- **Provisional**: Not yet confirmed by the licensed agriculturist or the LGU. Use as a guide.
- **Field check**: What the field team saw at a spot: planted, plantable, needs recheck or not plantable. It is saved and never edited.
- **Top-up**: A new plan for the trees lost to problem blocks.
- **Planting window**: The dates you plan to plant. Each species has its own best months.
- **Zoning map**: The land-use zones of the LGU. Land outside it is scored but flagged.
