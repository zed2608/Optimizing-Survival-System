import { guideTours } from '../tours/guideText.js'
// ALL the tutorial text of the dashboard, in ONE file (round 16). The guided tour, the Help page, the "?" tips and the printable guide (docs/USER_GUIDE.md,
// built by scripts/build_user_guide.mjs) all read from here, so a wording fix is made once.
// Rules for the text: plain words for a non-technical LGU staff member, short sentences, no underscores, no equals signs, no codes. Only what the system does today.

// The screens of the dashboard. A tour step belongs to one of them; "Quick tour of this screen" runs only the steps of the open one.
export const SCREENS = {
  studio: { tab: 'Active Studio', name: 'the map screen' },
  weather: { tab: 'Weather', name: 'the Weather tab' },
  history: { tab: 'Campaign Logs', name: 'Campaign Logs' },
  analytics: { tab: 'System Analytics', name: 'System Analytics' },
}

// The example point the tour opens (Santa Ana). If the first is not available after a zoning change, the next one is tried. tests/test_advice.py checks that they exist.
export const EXAMPLE_POINTS = [832, 830, 828, 826]

// Questions and answers of the Help page. id is used by the "?" tips. Short, plain, true to the system today.
export const FAQ = [
  { id: 'grey-point', topic: 'Map', q: 'Why is a point grey?', a: 'A grey dot means no species suits that square for your purpose. A faint grey square that is not a dot is land that is never scored: cemetery and quarry land. Click it to see the reason.', words: 'grey gray no data not suitable cemetery quarry excluded' },
  { id: 'empty-area', topic: 'Map', q: 'Why does a part of the map have no squares?', a: 'Squares in the cemetery and quarry zones are never scored, so they are not coloured. Land outside the zoning map is scored but flagged. You can switch it off with “Include land outside the zoning map”.', words: 'empty missing gap zoning outside map forest reserve' },
  { id: 'colours', topic: 'Map', q: 'What do the colours mean?', a: 'They show the overall match. Green is Good (55% or more). Orange is Moderate (35% up to 55%). Red is Poor (under 35%). Grey means not suitable here. Open the Legend button on the map to see them.', words: 'colour color good moderate poor legend green orange red' },
  { id: 'scores', topic: 'Map', q: 'What are site match, purpose fit and overall match?', a: 'Site match says how well the land suits a species. Purpose fit says how well the species suits what you want, such as shade or watershed. Overall match combines the two. If the site match is under 50%, the overall match is zero. Detailed view shows the numbers. Site suitability is predicted by a Random Forest trained on the expert rules. These are saved scores; the model is not run in the app, and it is not an independent measurement of survival. Hard limits (zone, elevation, steep slope) always apply first.', aRules: 'Site match says how well the land suits a species. Purpose fit says how well the species suits what you want, such as shade or watershed. Overall match combines the two. If the site match is under 50%, the overall match is zero. Detailed view shows the numbers. Right now the Random Forest scores are not loaded, so site suitability comes from the expert rules themselves. Hard limits (zone, elevation, steep slope) always apply first.', words: 'score S P W site fit purpose overall match 50 random forest expert rules hard limits' },
  { id: 'zoning-layer', topic: 'Map', q: 'How do I show the zoning colours?', a: 'Open Map view at the top right of the map and tick Zoning. A list shows the zones, the colours and how many squares each has. The colours follow the LGU style file. Untick it to hide the layer.', words: 'zoning layer colours map view toggle legend' },
  { id: 'map-view', topic: 'Map', q: 'What is in the Map view menu?', a: 'Simple or Detailed map, the map type (satellite or street map), the field-checked points, the planned trees, the Zoning layer, the satellite ground cover layer, and the faint squares that are not planting zones. Detailed adds every field-check symbol and the tree codes.', words: 'map view menu simple detailed satellite street layers' },
  { id: 'slope-caution', topic: 'Warnings', q: 'What does the steep slope caution mean?', a: 'Each tree has a usual limit for how steep the land can be. A square a little steeper than that limit is not thrown out. It gets a lower score, and it only shows when it still passes. Plant on terraces or use contour planting, or choose another tree. A square much steeper is still left out. This rule is provisional until the adviser confirms it.', words: 'slope steep limit terraces contour graded caution' },
  { id: 'square', topic: 'Map', q: 'Is a dot an exact planting spot?', a: 'No. Each square is 100 metres wide, so a point means “this square”. The field team checks the real spot on the ground.', words: '100 m grid cell exact spot' },
  { id: 'search', topic: 'Search', q: 'What can I type in the search box?', a: 'A barangay (for example Santa Ana), a species name, a point number (for example 832), a plan point code from a saved plan, or map coordinates. Choosing a barangay shows its best species. Choosing a species shows where it grows. Choosing a point or coordinates opens that spot.', words: 'search find barangay species point coordinates' },
  { id: 'coordinates', topic: 'Search', q: 'Which coordinates can I type?', a: 'Latitude and longitude such as 14.69 121.12, with or without N and E, or UTM zone 51N numbers such as 296799 1625091. If the numbers cannot be read, you get a reason and nothing is guessed.', words: 'coordinates latitude longitude utm gps' },
  { id: 'two-ways', topic: 'Using the system', q: 'Which goal should I choose?', a: 'Choose “I have species” when you already know what you want to plant and need to know where. Choose “I have an area” when you know the place and need to know what to plant there.', words: 'goal mode species area find choose' },
  { id: 'purpose', topic: 'Using the system', q: 'What are the three purposes?', a: 'Urban greening is for shade, lower root-damage risk and low upkeep in town. Tree planting is for conservation and livelihood. Watershed is for holding soil on slopes and by waterways. The purpose changes how species are scored.', words: 'purpose urban greening planting watershed' },
  { id: 'dates', topic: 'Using the system', q: 'Why are some species not in their best months?', a: 'The dates only add a label to each species (In season, Partly, Outside best months). They never hide a species and never change a score. Outside the best months you can still plant, but expect more watering and more losses.', words: 'season dates months missing hidden only species filter' },
  { id: 'best-months', topic: 'Using the system', q: 'What does Outside best months mean?', a: 'The sources give planting months for each species. You can still plant outside them, but expect more watering and more losses.', words: 'season best months outside planting' },
  { id: 'jump', topic: 'Using the system', q: 'How do I find a good planting time?', a: 'In the Planting window step, press “Jump to the next planting season”. It picks the 60 days in the next year when the most species are in their planting months.', words: 'jump next planting season dates window' },
  { id: 'suits-all', topic: 'Using the system', q: 'What is the difference between Suits all and Suits at least one?', a: 'Suits all means every species you chose must grow there, and the score is the lowest of theirs. Suits at least one means one species is enough, and the score is the highest.', words: 'suits all at least one combine several species' },
  { id: 'simple-detailed', topic: 'Using the system', q: 'What is the difference between Simple and Detailed?', a: 'Simple is the short view in plain words. Detailed shows every number, such as site match, purpose fit and overall match, the month strip and the sources. The map has its own Simple or Detailed choice in the Map view menu.', words: 'simple detailed view switch numbers' },
  { id: 'needs-permission', topic: 'Warnings', q: 'What does Needs permission mean?', a: 'The zone has a condition from the MPDC form. For example, private land needs the owner’s consent, a landfill needs DENR permission, and the Forest Reserve needs a MENRO and DENR permit. Get the permit before planting.', words: 'permission permit zone condition mpdc denr private land' },
  { id: 'outside-map', topic: 'Warnings', q: 'What does “outside the zoning map” mean?', a: 'About 1,279 squares lie outside our zoning map. The CLUP 2021-2031 shows that land as Forest Reserve (Watershed). They are scored but flagged. Coordinate with MENRO and DENR before planting there.', words: 'outside zoning map forest reserve watershed unconfirmed ring' },
  { id: 'habagat', topic: 'Warnings', q: 'Why does July to September look worse in Maly, Dulong Bayan or Santa Ana?', a: 'The MAO advised that heavy rain and flooding in the Habagat months can wash out seedlings in Maly, Dulong Bayan I and II, and Santa Ana. When your dates touch July to September, the overall match there is lowered by 20%. The site match does not change. This is provisional.', words: 'habagat rain flood jul sep july september maly dulong bayan santa ana lower' },
  { id: 'heavy-metals', topic: 'Warnings', q: 'Why is there a heavy metals note?', a: 'Food-bearing trees on a landfill or a special reserved square may take up heavy metals. The note asks you to test the produce before anyone eats or sells it. No tree is left out because of it.', words: 'heavy metals landfill rehabilitation food fruit warning test' },
  { id: 'check-first', topic: 'Warnings', q: 'What does Check first mean?', a: 'It lists planned trees on squares that look bare, built-up or wet in the satellite picture, or that are outside the zoning map. Press “Show these on the map” to circle them, and look at them before the team goes out.', words: 'check first bare built up water ground cover warning' },
  { id: 'soil-ground', topic: 'Warnings', q: 'How reliable are the soil and ground cover lines?', a: 'The soil comes from the LGU soil map that we digitized from a scan, so it is provisional, and there is no soil data for part of the north-east. The ground cover is a 2021 satellite picture that is about 77% accurate worldwide. Both are guides only.', words: 'soil ground cover satellite accuracy provisional data unavailable' },
  { id: 'species-card', topic: 'Species', q: 'What is on the species card?', a: 'The planting months, how the tree grows, where it grows, its uses, partner species, notes from the agriculturist and the source of each fact. A fact with no source says Data Unavailable.', words: 'species card info months uses sources data unavailable' },
  { id: 'advice-what', topic: 'Species', q: 'What is Ways to improve survival?', a: 'A short list of tips for a species or for a plan, such as mulching, a windbreak, or asking for grafted stock. A tip only appears when it applies, for example when a species has Low drought tolerance. Simple shows a few tips and Detailed shows them all.', words: 'advice tips improve survival mulch windbreak grafted shade' },
  { id: 'advice-score', topic: 'Species', q: 'Does the advice change the scores?', a: 'No. The advice is only text. The site match, the purpose fit and the overall match stay exactly the same.', words: 'advice score change site match purpose fit overall' },
  { id: 'advice-source', topic: 'Species', q: 'Where does the advice come from?', a: 'Some tips come from the MAO interview. Others are general practice. Each tip shows its source. All of it is advice that the agriculturist still has to confirm.', words: 'advice source mao interview general practice agriculturist confirm' },
  { id: 'companions', topic: 'Species', q: 'What is "Puwedeng samahan" when I choose many species?', a: 'You first choose a main species. "Puwedeng samahan" then lists species that are suitable on at least half of the same squares of your area (or of the whole municipality when no area is chosen). It is only about the land. It does not yet consider canopy size, roots or shade.', words: 'puwedeng samahan companion main species many one same squares' },
  { id: 'partners', topic: 'Species', q: 'What is Works well with?', a: 'A short list of species that can grow together with the main species, from simple starting rules about height, shade, water and roots. A label “Named in sources, check conditions” means the sources name the pair but our rules found that the conditions differ. These rules are provisional.', words: 'partner works well with companion intercrop named in sources' },
  { id: 'nursery', topic: 'Species', q: 'What does Available in LGU nursery mean?', a: 'The species is on the nursery list the LGU gave us. The list does not say how many seedlings are ready, so stock quantities are unknown. Kape is on the list but the variety is unknown, so Robusta is not marked.', words: 'nursery stock seedlings lgu available kape coffee' },
  { id: 'purpose-tags', topic: 'Species', q: 'What are the purpose tags?', a: 'Short labels such as fruit-bearing, timber, ornamental or biodiversity. They only help you filter the species list. They do not change any score. They are provisional.', words: 'purpose tags fruit timber ornamental filter' },
  { id: 'agri-notes', topic: 'Species', q: 'What are the notes from the agriculturist?', a: 'Short advice from the MAO interview, shown on a species card and marked Provisional. They are not part of the scores.', words: 'agriculturist notes interview mao advice provisional' },
  { id: 'make-plan', topic: 'Plans', q: 'How do I make a plan?', a: 'Work down the five steps on the left: Goal, Purpose, Planting window, Species or Area, and Plan. In step 5, name the campaign, say how many trees, and press Create plan.', words: 'plan create campaign trees steps' },
  { id: 'counts', topic: 'Plans', q: 'How do I choose the number of trees for each species?', a: 'With “I have species”, step 5 has one row per species with a number box. With “I have an area”, press “Choose my own species and counts”. Exactly your numbers are placed. A plan with one species, or mostly one species, shows a pest-risk warning.', words: 'trees per species counts number choose own' },
  { id: 'block', topic: 'Plans', q: 'What is a block?', a: 'A block is one 100 metre grid square planted close together at the spacing of its species. The planted area sits in the middle of the square, with an equal margin on every side for paths and rocks.', words: 'block 100 m square spacing hectare planting area' },
  { id: 'plan-numbers', topic: 'Plans', q: 'What do Trees, Blocks and Hectares mean?', a: 'Trees is how many trees were placed. Blocks is how many 100 metre squares are used. Hectares is the land those squares cover.', words: 'trees blocks hectares numbers result' },
  { id: 'why-fewer', topic: 'Plans', q: 'Why were fewer trees placed than I asked for?', a: 'There were not enough suitable squares for that species in the area, or other species took them. The result says which. Try a bigger area or other species.', words: 'fewer placed requested not enough squares unplaced' },
  { id: 'field-kit', topic: 'Field work', q: 'What is in the field kit?', a: 'A printed map (PDF), blocks.csv to fill in, point-list.csv (the older list format), points.gpx and points.kml for a map app, and a README. Each file carries the plan name and the check code.', words: 'field kit files pdf csv gpx kml readme download' },
  { id: 'check-code', topic: 'Field work', q: 'What is the check code?', a: 'It is eight characters made from the plan itself. Every file of the kit carries it. When you bring a filled sheet back, the dashboard compares the code with the plan, and refuses the sheet if they differ. That stops a sheet of one plan from being saved on another.', words: 'check code plan id match import refused fingerprint' },
  { id: 'use-kit', topic: 'Field work', q: 'How does the team use the kit on the ground?', a: 'Walk to the START point of a block and put in a stake. Plant tree 1 half a spacing east and north of it. Plant the rows from west to east, then move north one spacing. Leave the empty places empty. Count the trees really planted and write the number down.', words: 'ground use start block rows plant stake spacing' },
  { id: 'record-planted', topic: 'Field work', q: 'How do I record that trees were planted?', a: 'Two ways. In the dashboard, right-click the block (press and hold on a phone), type your name once, press Planted and enter how many trees. Or fill blocks.csv in the field, then press “Import field checks (CSV)” under More, Field checks. Importing the same file twice adds nothing.', words: 'record planted trees import blocks csv field check' },
  { id: 'status-colours', topic: 'Field work', q: 'What do the field-check colours and symbols mean?', a: 'Every field-check mark is the same violet; only the shape differs. Planted is a check. Marked plantable by an observer is a ring: the mark of one person who typed a name; it is not an expert check and it never changes a score. Needs recheck is a question mark. Not plantable is a cross; the reason (water, paved, built or rock) is written in words next to it. The shape is always shown with words.', words: 'status colours icons planted verified recheck not plantable water paved' },
  { id: 'reasons', topic: 'Field work', q: 'What are the reasons for Not plantable?', a: 'Paved, Building, Rock or ledge, Creek bank or waterlogged, Too steep, Existing tree, Owner refused, and Other. A reason is always needed.', words: 'reason not plantable paved building rock creek steep tree owner' },
  { id: 'removed', topic: 'Field work', q: 'Why is a square marked Not plantable removed from plans?', a: 'The field team found that it cannot be planted. New plans and suggestions leave it out. A new check with a note can clear the mark. Scores are not changed.', words: 'not plantable removed left out excluded plans' },
  { id: 'progress', topic: 'Field work', q: 'How are the planted trees counted?', a: 'Each block counts by its latest saved check. A block marked Planted counts the number of trees written. A partly planted block counts only those trees. Trees planned minus trees planted is Remaining. Trees of blocks with a problem are Problem.', words: 'progress count planted remaining problem partly blocks' },
  { id: 'top-up', topic: 'Field work', q: 'What is a top-up plan?', a: 'A new plan for the trees lost to problem blocks, with the same campaign, dates and settings. It never uses a square of the first plan or a square marked Not plantable. You can also ask it to include the trees not yet planted.', words: 'top up plan lost shortfall problem remaining' },
  { id: 'dispute', topic: 'Field work', q: 'What if two people record different results?', a: 'The latest check counts. If the last two come from different people and disagree, the point is shown as disputed so someone can look again.', words: 'disputed different observers disagree' },
  { id: 'weather', topic: 'Weather', q: 'What does the Weather tab show?', a: 'The coming week for the place you choose. It gives a verdict (Good to plant, Plant with care or Avoid this week) with the rain numbers, and lists the species that suit the week. The forecast covers about 16 days.', words: 'weather forecast week rain verdict' },
  { id: 'weather-months', topic: 'Weather', q: 'How does the weather affect planting months?', a: 'It does not change a score or a best month. It only tells you if this week is good, and it lists the species that are in their best months and not hit by a warning. Species outside their best months are listed apart as Only if you can water.', words: 'weather months season held back water' },
  { id: 'provisional', topic: 'Data', q: 'What does Provisional mean?', a: 'It marks information that comes from an interview, a form or our own rules and has not yet been confirmed by the licensed agriculturist or the LGU. Use it as a guide, not as a final answer.', words: 'provisional draft not confirmed' },
  { id: 'signed-off', topic: 'Data', q: 'Which data is signed off?', a: 'The zoning rules come from answers written on a form by the MPDC (provisional), and the warnings and notes come from the MAO interview, but they are still provisional. The species data (release v1.0-review) has not been signed off by the licensed agriculturist. Distance to creeks and rivers is used as a soft wetness factor (50 metres), but MENRO has not answered the waterways question, so this layer is not checked.', words: 'signed off agriculturist mpdc mao interview validated waterways wetness creeks rivers 50 metres' },
  { id: 'decides', topic: 'Data', q: 'Does the system decide where to plant?', a: 'No. It suggests. People decide, the field team checks every spot, and permits from MENRO, DENR or the owner are still needed. It does not replace the agriculturist.', words: 'decide replace agriculturist permit suggest' },
  { id: 'unavailable', topic: 'Data', q: 'What does Data Unavailable mean?', a: 'The information does not exist in our sources, so the system shows nothing. It never fills a missing value with a guess.', words: 'data unavailable missing no value guess' },
  { id: 'service-offline', topic: 'Using the system', q: 'What if the top bar says the service is not connected?', a: 'The page cannot reach the data service, so the map and results cannot load. Ask the person who runs the system to start it, then reload the page.', words: 'not connected api error cannot load service' },
  { id: 'logs-analytics', topic: 'Using the system', q: 'What are Campaign Logs and System Analytics?', a: 'Campaign Logs lists every saved plan with its status, progress and top-up. System Analytics shows counts: the squares, the field checks and the plans, and the dataset version.', words: 'campaign logs analytics saved plans counts history' },
  { id: 'where-help', topic: 'Using the system', q: 'Where do I find this help again?', a: 'Press Help at the top right of any screen. A small question mark next to a main control opens the matching answer.', words: 'help where find tour again' },
]

export const GLOSSARY = [
  { term: 'Site match', meaning: 'How well the land of a square suits a species: slope, height, soil, zone and distance to creeks and rivers (a soft wetness factor, 50 metres; the waterways map is not yet validated by MENRO). It is a number from 0 to 1. A square a little steeper than the tree\'s usual limit can still pass, with a lower score and a slope caution.' },
  { term: 'Purpose fit', meaning: 'How well a species suits what you want the trees for: shade in town, tree planting or watershed.' },
  { term: 'Overall match', meaning: 'Site match combined with purpose fit. It is zero if the site match is under 50%. The map colours show it.' },
  { term: 'Block', meaning: 'One 100 metre square planted close together at the spacing of its species. The planted area sits in the middle of the square.' },
  { term: 'Check code', meaning: 'Eight characters made from a plan. Every file of its field kit carries it, so a sheet cannot be saved on the wrong plan.' },
  { term: 'Provisional', meaning: 'Not yet confirmed by the licensed agriculturist or the LGU. Use as a guide.' },
  { term: 'Field check', meaning: 'What the field team saw at a spot: planted, plantable, needs recheck or not plantable. It is saved and never edited.' },
  { term: 'Top-up', meaning: 'A new plan for the trees lost to problem blocks.' },
  { term: 'Planting window', meaning: 'The dates you plan to plant. Each species has its own best months.' },
  { term: 'Zoning map', meaning: 'The land-use zones of the LGU. Land outside it is scored but flagged.' },
]

// The "?" tips next to the main controls: which Help answer each one opens.
export const ASK_TIPS = {
  search: 'search',
  legend: 'colours',
  zoning: 'zoning-layer',
  verdict: 'scores',
  permission: 'needs-permission',
  nursery: 'nursery',
  advice: 'advice-what',
  plan: 'make-plan',
  kit: 'field-kit',
  progress: 'progress',
  field: 'status-colours',
  weather: 'weather',
}

// The answer to show: when the app runs on the expert rules instead of the Random Forest (the scores are not loaded), an answer that talks about the forest has its own text (aRules).
export function faqAnswer(faq, usingRules = false) {
  return usingRules && faq.aRules ? faq.aRules : faq.a
}

// Every visible string of this file (the unit tests check them for underscores and equals signs).
export function allVisibleText() {
  const out = []
  for (const tour of guideTours()) {
    out.push(tour.title, tour.blurb)
    for (const sec of tour.sections) {
      out.push(sec.title)
      for (const x of sec.steps) out.push(x.title, x.text, x.watch)
    }
  }
  for (const f of FAQ) out.push(f.q, f.a, f.aRules ?? '')
  for (const g of GLOSSARY) out.push(g.term, g.meaning)
  for (const k of Object.values(SCREENS)) out.push(k.tab, k.name)
  return out.filter(Boolean)
}
