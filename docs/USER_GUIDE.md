# Tree Planting Decision Support: user guide

San Mateo, Rizal. Municipal Environment and Natural Resources Office (MENRO).

This guide is built from the same text as the in-app tour and the Help page (`frontend/src/new/tutorial/tutorialContent.js`). Do not edit it by hand: change that file and run `node scripts/build_user_guide.mjs`.

## Contents

1. [The tour, step by step](#the-tour-step-by-step)
2. [Questions and answers](#questions-and-answers)
3. [Glossary](#glossary)

## The tour, step by step

### Welcome

**1. Welcome** (the map screen)

This system helps you decide which trees to plant, and where. It looks at the land, the soil, the zoning and the planting months, and it makes a plan you can print for the field team.

*Watch for:* It only suggests. People decide, and the field team checks every spot on the ground. It does not replace the agriculturist, MENRO or a DENR permit.

### The map and its dots

**2. The map and its dots** (the map screen)

Each coloured square is a 100 metre piece of San Mateo. Green is a Good match for the trees you are looking at. Orange is Moderate. Red is Poor. Grey means no tree suits that square.

*Watch for:* Some areas have no colour at all. Cemetery and quarry land is never scored. Land outside the zoning map is scored, but it carries a warning.

**3. The legend** (the map screen)

The Legend button explains the colours and the field-check symbols that are on the map right now.

*Watch for:* The colours follow the overall match: Good is 55% or more, Moderate is 35% up to 55%, Poor is under 35%.

**4. The Zoning layer** (the map screen)

Open Map view and tick Zoning to colour the land by its zone. A list shows each zone and how many squares it has.

*Watch for:* The colours follow the LGU style file. A zone that needs a permit says so when you click a point.

### Search

**5. Search** (the map screen)

Type a barangay, a species, a point number or map coordinates. Choose a barangay to see the best species for it. Choose a species to see where it grows. Choose a point number or coordinates to open that spot.

*Watch for:* Wait a moment after two letters for the suggestions. A bad coordinate is refused with a reason. It is never guessed.

### Two ways to use the system

**6. Two ways to use it** (the map screen)

Choose “I have species” to find where your species can grow. Choose “I have an area” to find which species suit an area you pick on the map.

*Watch for:* Everything else in the left panel follows from this first choice.

### Clicking a point

**7. Clicking a point** (the map screen)

Click any square to open its panel. The first card gives a short verdict, such as “Good place for Kamagong: overall match 77%”. Below it are the field check and the list of best species. Choose Detailed at the top for the numbers behind the verdict.

*Watch for:* The tour opens an example point for you. Check the card for warnings before you trust a spot.

**8. Zone, soil and warnings** (the map screen)

The top of the panel shows the zone and its condition. A small Needs permission badge means the land needs a permit or the owner’s consent. Under it you see the soil and what the satellite shows on the ground, such as grass, trees or bare soil.

*Watch for:* Soil and satellite ground cover are guides. Plain warnings, such as Check first or a heavy metals note, always come from a rule that is explained when you tap the question mark next to it.

### The species card

**9. The species card** (the map screen)

Tap the small i next to a species to open its card. It shows the months to plant, how the tree grows, and the source of every fact. It also shows a Works well with list of partner species, and notes from the agriculturist.

*Watch for:* Partner species and agriculturist notes are marked Provisional. They are starting guides, not final advice.

*You open a species card by tapping the small i next to a species in the Species step.*

**10. Ways to improve survival** (the map screen)

The species card and the plan result have a section called Ways to improve survival. It gives short tips, such as mulching, a windbreak, or asking the nursery for grafted stock. Press its title to open it.

*Watch for:* The tips never change a score. They come from the MAO interview or from general practice, and the agriculturist still has to confirm them.

*You see this section in the species card and in the plan result, when a tip applies.*

**11. Filter the species list** (the map screen)

In “I have species”, the species list has a Purpose filter, such as fruit-bearing or timber. It also has an Available in LGU nursery tick box that keeps only the species on the nursery list.

*Watch for:* The nursery list does not say how many seedlings are ready. Stock quantities are unknown.

*You see these filters in the Species step when you choose “I have species”.*

### Planning an event

**12. Planning an event: five steps** (the map screen)

The left panel has five steps: Goal, Purpose, Planting window, Species or Area, and Plan. Work down them in order. Each closed step shows a one-line summary of your choice.

*Watch for:* Each species has its own best months. Set your dates in step 3, or press “Jump to the next planting season”.

**13. Step 5: the Plan** (the map screen)

Name the campaign and say how many trees. With “I have species” you set the number of trees for each species. With “I have an area” the system picks a mix, or you press “Choose my own species and counts”. Then press Create plan.

*Watch for:* The button stays off and tells you why until the name, the area and the dates are fine. A plan with only one or two species carries a pest-risk warning.

### The plan result

**14. The plan result** (the map screen)

After you create a plan you see three big numbers: Trees, Blocks and Hectares. A block is one 100 metre square planted close together at the right spacing for its species.

*Watch for:* If fewer trees were placed than you asked for, the result says why.

*You see this after you press Create plan.*

**15. Check first and Good to know** (the map screen)

The Check first box lists trees on land that needs a closer look, such as ground that looks bare, built-up or wet from the satellite, or land outside the zoning map. “Show these on the map” circles them. Good to know lists up to three plain notes, each with a Why? tip.

*Watch for:* Two warnings can appear. A heavy metals note shows when food-bearing trees fall on landfill or mining land. A heavy rain note shows when your dates touch July to September in Maly, Dulong Bayan I and II, or Santa Ana.

*You see these boxes in the plan result, only when something needs your attention.*

### The field kit

**16. The field kit** (the map screen)

On the Field kit tab, press Build field kit, then Download kit. The kit has a printed map (PDF), a sheet to fill in (blocks), the same blocks in the older list format, and files for a map app (GPX and KML). A README explains how to lay out a block.

*Watch for:* Every file carries the plan name and a check code. The check code is eight characters made from the plan itself. A sheet with the wrong code is refused when you bring it back.

*You see the kit after you create a plan, on the Field kit tab.*

**17. Using the kit on the ground** (the map screen)

The team walks to the START point of a block. They plant the numbered trees row by row, from tree 1 up to the number written on the page, and leave the rest empty. Then they write down how many trees they really planted.

*Watch for:* If a house, road, creek or tree is in the way, move the block a little and write down the real position. Never plant on paved or built land.

### Field checks and progress

**18. Field checks** (the map screen)

On a point panel, the field check card records what the team saw. Every status has a colour and a symbol: Planted (green check), Plantable (green ring), Needs recheck (amber question mark) and Not plantable (red cross). A blue cross means water. A gray cross means paved, building or rock.

*Watch for:* You type your name once. A saved check is never edited. A change is a new check, and clearing a Not plantable mark needs a note.

*You see the field check card when you click a point.*

**19. Progress and top-up** (the map screen)

The Progress tab counts the trees planted, the trees remaining and the blocks with a problem. A block that is only partly planted counts only the trees really planted. If trees were lost to problem blocks, press Plan top-up to plan new blocks for them.

*Watch for:* A square marked Not plantable is left out of new plans, because the field team found it cannot be planted. A top-up never uses a square of the first plan.

*You see Progress after you create a plan, on the Progress tab.*

**20. Campaign Logs** (Campaign Logs)

Campaign Logs lists every saved plan, with its dates and its status: Active, Upcoming or Concluded. You can open a plan on the map, see its progress, and plan a top-up.

*Watch for:* Plans are saved on the server, so you can come back to them later.

### The Weather tab

**21. The Weather tab** (the Weather tab)

The Weather tab shows the coming week for San Mateo, a barangay, the last point you clicked or the middle of a plan. It says Good to plant, Plant with care, or Avoid this week, and it lists the species that suit the week.

*Watch for:* The weather never changes a score or a best month. Species outside their best months are listed apart, as Only if you can water. A species hit by a weather warning is held back.

### Data and limits

**22. System Analytics** (System Analytics)

System Analytics shows simple counts: how many map squares there are, how many field checks were saved, how many plans exist, and which version of the species data is in use.

*Watch for:* The plan totals use the newest 100 plans. The page says so when there are more.

**23. Data and limits** (the map screen)

Most of the data is Provisional. The zoning rules come from the MPDC form signed on 7 October 2026. The planting-month notes, the nursery list and the warnings come from the MAO interview. The species data is not yet signed off by the licensed agriculturist.

*Watch for:* The waterways form was signed blank, so creeks and the 50 metre wetness rule are not used. The system supports decisions. It does not replace the agriculturist, MENRO or a DENR permit.

### Finish

**24. You are ready** (the map screen)

You can open this help again at any time. Press Help at the top right. There you can search the questions, read the short glossary, take the tour again, or print the guide.

*Watch for:* Next to the main controls, a small question mark opens the matching answer.

## Questions and answers

### Map

**Why is a point grey?**

A grey dot means no species suits that square for your purpose. A faint grey square that is not a dot is land that is never scored: cemetery and quarry land. Click it to see the reason.

**Why does a part of the map have no squares?**

Squares in the cemetery and quarry zones are never scored, so they are not coloured. Land outside the zoning map is scored but flagged. You can switch it off with “Include land outside the zoning map”.

**What do the colours mean?**

They show the overall match. Green is Good (55% or more). Orange is Moderate (35% up to 55%). Red is Poor (under 35%). Grey means not suitable here. Open the Legend button on the map to see them.

**What are site match, purpose fit and overall match?**

Site match says how well the land suits a species. Purpose fit says how well the species suits what you want, such as shade or watershed. Overall match combines the two. If the site match is under 50%, the overall match is zero. Detailed view shows the numbers.

**How do I show the zoning colours?**

Open Map view at the top right of the map and tick Zoning. A list shows the zones, the colours and how many squares each has. The colours follow the LGU style file. Untick it to hide the layer.

**What is in the Map view menu?**

Simple or Detailed map, the map type (satellite or street map), the field-checked points, the planned trees, the Zoning layer, the satellite ground cover layer, and the faint squares that are not planting zones. Detailed adds every field-check symbol and the tree codes.

**Is a dot an exact planting spot?**

No. Each square is 100 metres wide, so a point means “this square”. The field team checks the real spot on the ground.

### Search

**What can I type in the search box?**

A barangay (for example Santa Ana), a species name, a point number (for example 832), a plan point code from a saved plan, or map coordinates. Choosing a barangay shows its best species. Choosing a species shows where it grows. Choosing a point or coordinates opens that spot.

**Which coordinates can I type?**

Latitude and longitude such as 14.69 121.12, with or without N and E, or UTM zone 51N numbers such as 296799 1625091. If the numbers cannot be read, you get a reason and nothing is guessed.

### Using the system

**Which goal should I choose?**

Choose “I have species” when you already know what you want to plant and need to know where. Choose “I have an area” when you know the place and need to know what to plant there.

**What are the three purposes?**

Urban greening is for shade, safe roots and low upkeep in town. Tree planting is for conservation and livelihood. Watershed is for holding soil on slopes and by waterways. The purpose changes how species are scored.

**Why are some species missing from the list?**

The box “Only species for my dates” hides species that are outside their best months in your dates. Press “Show all species” to see them all. Scores do not change with the dates.

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

### Warnings

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

### Species

**What is on the species card?**

The planting months, how the tree grows, where it grows, its uses, partner species, notes from the agriculturist and the source of each fact. A fact with no source says Data Unavailable.

**What is Ways to improve survival?**

A short list of tips for a species or for a plan, such as mulching, a windbreak, or asking for grafted stock. A tip only appears when it applies, for example when a species has Low drought tolerance. Simple shows a few tips and Detailed shows them all.

**Does the advice change the scores?**

No. The advice is only text. The site match, the purpose fit and the overall match stay exactly the same.

**Where does the advice come from?**

Some tips come from the MAO interview. Others are general practice. Each tip shows its source. All of it is advice that the agriculturist still has to confirm.

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

Two ways. In the dashboard, click the block, type your name once, press Planted and enter how many trees. Or fill blocks.csv in the field, then press “Import field checks (CSV)” under More, Field checks. Importing the same file twice adds nothing.

**What do the field-check colours and symbols mean?**

Planted is green with a check. Plantable (verified) is a green ring. Needs recheck is amber with a question mark. Not plantable is a red cross. Not plantable because of water is a blue cross. Not plantable because it is paved, built or rock is a gray cross. The colour is always shown with a symbol and words.

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

The zoning rules come from the MPDC form signed on 7 October 2026, and the warnings and notes come from the MAO interview, but they are still provisional. The species data (release v1.0-review) has not been signed off by the licensed agriculturist. The waterways form was signed blank, so creeks and the 50 metre wetness rule are not used.

**Does the system decide where to plant?**

No. It suggests. People decide, the field team checks every spot, and permits from MENRO, DENR or the owner are still needed. It does not replace the agriculturist.

**What does Data Unavailable mean?**

The information does not exist in our sources, so the system shows nothing. It never fills a missing value with a guess.

## Glossary

- **Site match**: How well the land of a square suits a species: slope, height, soil, zone and rain. It is a number from 0 to 1.
- **Purpose fit**: How well a species suits what you want the trees for: shade in town, tree planting or watershed.
- **Overall match**: Site match combined with purpose fit. It is zero if the site match is under 50%. The map colours show it.
- **Block**: One 100 metre square planted close together at the spacing of its species. The planted area sits in the middle of the square.
- **Check code**: Eight characters made from a plan. Every file of its field kit carries it, so a sheet cannot be saved on the wrong plan.
- **Provisional**: Not yet confirmed by the licensed agriculturist or the LGU. Use as a guide.
- **Field check**: What the field team saw at a spot: planted, plantable, needs recheck or not plantable. It is saved and never edited.
- **Top-up**: A new plan for the trees lost to problem blocks.
- **Planting window**: The dates you plan to plant. Each species has its own best months.
- **Zoning map**: The land-use zones of the LGU. Land outside it is scored but flagged.
