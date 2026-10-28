// The tour registry (R1 W3): every tour of the dashboard, one per page, each made of sections ("Explain this" mini-tours). One engine (tourController.js, TourHost.jsx) runs them all.
// A step: { id, target (the data-tour="..." id of a real element, or null for a centred card), title, text, watch?, setup?, teardown?, optional?, page? } with texts as { en, tl } (English is the default).
// setup() may only use the bridge (navigation: page, step, mode ...) and ui.toggle(id) (open / close a menu or panel). Nothing here creates a plan, a link or a field check.
// Wording rule: plain words for a novice; explain the terms (Good / Moderate / Poor, overall match, pH "not certain", counted squares, field check).
import { EXAMPLE_SPECIES_ID } from './tourExample.js'

const T = (en, tl) => ({ en, tl })
const S = (id, target, title, text, watch = null, extra = {}) => ({ id, target, title, text, watch, ...extra })

// ---------------------------------------------------------------------------------------------------------------------------------------------------------------- helpers for setup()
const menuOpen = async ({ ui }) => {
  if (!ui.exists('set-theme')) await ui.toggle('h-settings')
}
const menuClose = async ({ ui }) => {
  if (ui.exists('set-theme')) await ui.toggle('h-settings')
}
const studio = (stepId, extra = {}) => async ({ bridge }) => {
  await bridge.setSidebar(true)
  if (extra.mode) await bridge.setMode(extra.mode)
  await bridge.setStep(stepId)
}

// ---------------------------------------------------------------------------------------------------------------------------------------------------------------- GLOBAL (every page)
const GLOBAL = {
  id: 'global',
  page: 'any',
  title: T('Header and settings', 'Header at mga setting'),
  blurb: T('The top bar: pages, settings, connection.', 'Ang itaas na bar: mga pahina, setting, koneksyon.'),
  sections: [
    {
      id: 'header',
      title: T('Top bar', 'Itaas na bar'),
      steps: [
        S('brand', 'h-brand', T('Whose tool this is', 'Kaninong tool ito'), T('This is the LGU San Mateo badge. The tool was made to help MENRO decide which trees to plant, and where.', 'Ito ang badge ng LGU San Mateo. Ginawa ang tool para tulungan ang MENRO na magpasya kung anong puno ang itatanim, at saan.')),
        S('tabs', 'h-tabs', T('Four pages', 'Apat na pahina'), T('Plan & Map is the map where you plan. The cloud shows the Weather for the week. The clipboard lists your saved plans (Campaign Logs). The bars count what exists (System Analytics).', 'Ang Plan & Map ang mapa kung saan ka nagpaplano. Ang ulap ay ang Panahon sa linggo. Ang clipboard ay ang listahan ng mga naka-save na plano (Campaign Logs). Ang mga bar ay nagbibilang ng mga meron (System Analytics).'), T('A tour always explains the page you are on.', 'Ang tour ay laging nagpapaliwanag ng pahinang kinaroroonan mo.')),
        S('settings', 'h-settings', T('Settings', 'Mga setting'), T('This button opens one menu: theme, language, animations, and the Welcome, Tours and Help links.', 'Binubuksan ng button na ito ang iisang menu: tema, wika, animation, at ang mga link na Welcome, Tours at Help.')),
        S('theme', 'set-theme', T('Light or dark', 'Maliwanag o madilim'), T('Choose the light or the dark look. Dark is easier on the eyes at night and saves battery on some phones.', 'Piliin ang maliwanag o madilim na itsura. Mas magaan sa mata ang dark sa gabi at nakatitipid ng baterya sa ilang phone.'), null, { setup: menuOpen, teardown: menuClose }),
        S('lang', 'set-lang', T('Language', 'Wika'), T('English is the default. Pick Taglish to read the whole screen in Filipino.', 'English ang default. Piliin ang Taglish para mabasa ang buong screen sa Filipino.'), null, { setup: menuOpen, teardown: menuClose }),
        S('anim', 'set-anim', T('Animations', 'Mga animation'), T('Auto follows your device. On always shows motion. Off removes every animation and blur: use it on a slow phone.', 'Sinusunod ng Auto ang device mo. Ang On ay laging may galaw. Inaalis ng Off ang lahat ng animation at blur: gamitin sa mabagal na phone.'), null, { setup: menuOpen, teardown: menuClose }),
        S('welcome', 'set-welcome', T('Welcome', 'Welcome'), T('Plays the short introduction slides again.', 'Pinapalabas muli ang maikling panimulang slide.'), null, { setup: menuOpen, teardown: menuClose }),
        S('tours', 'set-tours', T('Tours', 'Mga tour'), T('Opens the list of tours: one for every page and a short one for every section.', 'Binubuksan ang listahan ng mga tour: isa para sa bawat pahina at maikli para sa bawat seksyon.'), null, { setup: menuOpen, teardown: menuClose }),
        S('help', 'set-help', T('Help', 'Tulong'), T('Questions and answers, a glossary of the words used, and a guide you can print.', 'Mga tanong at sagot, glossary ng mga salita, at gabay na puwedeng i-print.'), null, { setup: menuOpen, teardown: menuClose }),
        S('api', 'h-api', T('Connection', 'Koneksyon'), T('Green means the planning service answers. If it says offline, check your connection: the map keeps what it already loaded.', 'Berde: sumasagot ang planning service. Kung offline, tingnan ang koneksyon: nananatili sa mapa ang na-load na.')),
        S('banner', 'h-banner', T('Demo notice', 'Paunawa sa demo'), T('This public demo uses provisional data that the agriculturist has not signed off. What you enter here is reset regularly.', 'Gumagamit ang pampublikong demo na ito ng pansamantalang datos na hindi pa pirmado ng agriculturist. Regular na nire-reset ang inilalagay mo rito.'), null, { optional: true }),
      ],
    },
  ],
}

// ---------------------------------------------------------------------------------------------------------------------------------------------------------------- ACTIVE STUDIO: the left panel
const STUDIO_LEFT = {
  id: 'studio-panel',
  page: 'studio',
  title: T('Plan & Map: the control panel', 'Plan & Map: ang control panel'),
  blurb: T('Goal, purpose, dates, species or area, plan.', 'Layunin, gamit, petsa, species o lugar, plano.'),
  sections: [
    {
      id: 'goal',
      title: T('Goal and purpose', 'Layunin at gamit'),
      steps: [
        S('panel', 's-panel', T('The control panel', 'Ang control panel'), T('You work from top to bottom: goal, purpose, planting window, species or area, plan. One step is open at a time and a closed step shows your choice in one line.', 'Mula taas pababa ang gawa: layunin, gamit, panahon ng pagtatanim, species o lugar, plano. Isang hakbang lang ang bukas at ang saradong hakbang ay nagpapakita ng pinili mo sa isang linya.'), null, { setup: studio('goal') }),
        S('hints', 's-hints', T('Show hints', 'Ipakita ang hints'), T('Turn this on to see a small ? next to the main controls. Each ? explains that control in a sentence.', 'I-on ito para makita ang maliit na ? sa tabi ng mga pangunahing control. Ipinapaliwanag ng bawat ? ang control na iyon sa isang pangungusap.')),
        S('goal', 's-step-goal', T('Step 1: Goal', 'Hakbang 1: Layunin'), T('Choose what you want to know. This is the first question of the system.', 'Piliin kung ano ang gusto mong malaman. Ito ang unang tanong ng sistema.'), null, { setup: studio('goal') }),
        S('modes', 's-modes', T('Two ways in', 'Dalawang paraan'), T('“I have species” shows where the species you pick can grow. “I have an area” ranks the best species for an area you choose.', 'Ipinapakita ng “I have species” kung saan puwedeng tumubo ang piniling species. Niraranggo naman ng “I have an area” ang pinakamahusay na species para sa lugar na pipiliin mo.'), null, { setup: studio('goal') }),
        S('purpose', 's-step-purpose', T('Step 2: Planting purpose', 'Hakbang 2: Layunin ng pagtatanim'), T('The purpose changes which species rank best.', 'Binabago ng layunin kung aling species ang pinakamataas ang ranggo.'), null, { setup: studio('purpose') }),
        S('purposes', 's-purposes', T('Three purposes', 'Tatlong layunin'), T('Urban greening: shade and low root-damage risk. Tree planting: conservation and livelihood. Watershed: holding soil on slopes and by waterways.', 'Urban greening: lilim at mababang panganib na masira ng ugat. Tree planting: konserbasyon at kabuhayan. Watershed: paghawak ng lupa sa mga dalisdis at tabi ng tubig.'), null, { setup: studio('purpose') }),
      ],
    },
    {
      id: 'window',
      title: T('Planting window', 'Panahon ng pagtatanim'),
      steps: [
        S('window', 's-step-window', T('Step 3: Planting window', 'Hakbang 3: Panahon ng pagtatanim'), T('Your start and end dates. They never remove a species and never change a score: they only add a label (In season, Outside best months) and the order.', 'Ang simula at katapusang petsa mo. Hindi nila inaalis ang species at hindi binabago ang iskor: nagdaragdag lang sila ng label (In season, Outside best months) at ayos.'), null, { setup: studio('window') }),
        S('dates', 's-dates', T('Start and end', 'Simula at katapusan'), T('Pick the first and last day you could plant. Up to 366 days, and the start cannot be in the past.', 'Piliin ang una at huling araw na puwede kang magtanim. Hanggang 366 na araw, at hindi puwedeng nasa nakaraan ang simula.'), null, { setup: studio('window') }),
        S('months', 's-months', T('The month strip', 'Ang month strip'), T('Twelve letters, January to December. A ring marks the months your dates touch. Species list their own best months, so you can compare.', 'Labindalawang titik, Enero hanggang Disyembre. Minamarkahan ng bilog ang mga buwang sakop ng petsa mo. May sariling pinakamainam na buwan ang bawat species para maihambing.'), null, { setup: studio('window') }),
        S('jump', 's-jump', T('Jump to the next season', 'Lumundag sa susunod na panahon'), T('Sets the dates to the 60 days with the most species in their best months. Most species are in season from May to September.', 'Itinatakda ang petsa sa 60 araw na may pinakamaraming species sa pinakamainam na buwan. Karamihan ng species ay in season mula Mayo hanggang Setyembre.'), null, { setup: studio('window') }),
      ],
    },
    {
      id: 'species',
      title: T('Species (I have species)', 'Species (I have species)'),
      steps: [
        S('pick', 's-step-pick', T('Step 4: Species', 'Hakbang 4: Species'), T('With “I have species” this step has four small steps: choose species, where to look, mark on the map, create the plan.', 'Sa “I have species”, may apat na maliit na hakbang ito: pumili ng species, saan hahanapin, markahan sa mapa, gumawa ng plano.'), null, { setup: studio('pick', { mode: 'species' }) }),
        S('flow', 's-flow-steps', T('The four small steps', 'Ang apat na maliit na hakbang'), T('The numbers show where you are. A finished step shows a tick and your choice; tap it to go back.', 'Ipinapakita ng mga numero kung nasaan ka. Ang tapos na hakbang ay may tsek at ang pinili mo; i-tap para bumalik.'), null, { setup: async (c) => { await studio('pick', { mode: 'species' })(c); await c.bridge.setSpeciesSub(1) } }),
        S('ask', 's-ask', T('One species or several', 'Isa o ilang species'), T('Choose one species, or several that grow well together. For several, the system suggests companions of your main species.', 'Pumili ng isang species, o ilang species na magkakasundo. Kung marami, magmumungkahi ang sistema ng kasama ng pangunahin mong species.'), null, { setup: async (c) => { await studio('pick', { mode: 'species' })(c); await c.bridge.setSpeciesSub(1); await c.bridge.setHow('') } }),
        S('search', 's-species-search', T('Find a species', 'Maghanap ng species'), T('Type part of a common or scientific name. The funnel next to it opens the filters.', 'Mag-type ng bahagi ng pangalan o siyentipikong pangalan. Binubuksan ng funnel sa tabi nito ang mga filter.'), null, { setup: async (c) => { await studio('pick', { mode: 'species' })(c); await c.bridge.setSpeciesSub(1); await c.bridge.setHow('one') } }),
        S('trait', 's-trait-filter', T('Filter by trait', 'Salain ayon sa katangian'), T('Narrow the list by a trait such as fruit-bearing, timber or ornamental, or to species the LGU nursery has. The traits are provisional.', 'Paliitin ang listahan ayon sa katangian tulad ng namumunga, troso o pampaganda, o sa species na nasa nursery ng LGU. Pansamantala ang mga katangian.'), null, { setup: async (c) => { await studio('pick', { mode: 'species' })(c); await c.bridge.setSpeciesSub(1); await c.bridge.setHow('one') } }),
        S('list', 's-species-list', T('The species list', 'Ang listahan ng species'), T('Tick the species you want. The “i” opens its card. The badge says if it is in season, partly, or outside its best months for your dates.', 'I-tsek ang species na gusto mo. Binubuksan ng “i” ang card nito. Sinasabi ng badge kung in season, bahagya, o labas sa pinakamainam na buwan para sa petsa mo.'), null, { setup: async (c) => { await studio('pick', { mode: 'species' })(c); await c.bridge.setSpeciesSub(1); await c.bridge.setHow('one') } }),
        S('where', 's-where', T('Where to look', 'Saan hahanapin'), T('Look in the whole municipality, or only one barangay or one zone.', 'Maghanap sa buong munisipyo, o sa isang barangay o isang zone lang.'), null, { setup: async (c) => { await studio('pick', { mode: 'species' })(c); await c.bridge.setSpeciesSub(2) } }),
        S('mark', 's-mark', T('Mark on the map', 'Markahan sa mapa'), T('Click corners on the map to draw the area where you want to plant, then finish it. Or use one point. The best places inside it are listed on the right.', 'Mag-click ng mga sulok sa mapa para iguhit ang lugar na tatamnan, tapos tapusin. O gumamit ng isang punto. Nakalista sa kanan ang pinakamagagandang lugar sa loob nito.'), null, { setup: async (c) => { await studio('pick', { mode: 'species' })(c); await c.bridge.setSpeciesSub(3) } }),
        S('flowplan', 's-flow-plan', T('Create the plan', 'Gumawa ng plano'), T('The last small step lists your choices and takes you to Step 5, the plan.', 'Inililista ng huling maliit na hakbang ang mga pinili mo at dadalhin ka sa Hakbang 5, ang plano.'), null, { setup: async (c) => { await studio('pick', { mode: 'species' })(c); await c.bridge.setSpeciesSub(4) } }),
      ],
    },
    {
      id: 'area',
      title: T('Area (I have an area)', 'Lugar (I have an area)'),
      steps: [
        S('pick-area', 's-step-pick', T('Step 4: Area', 'Hakbang 4: Lugar'), T('With “I have an area” you choose the area and the system ranks the species for it.', 'Sa “I have an area”, ikaw ang pipili ng lugar at ira-rank ng sistema ang mga species para rito.'), null, { setup: studio('pick', { mode: 'area' }) }),
        S('how', 'a-how', T('Three ways to choose', 'Tatlong paraan ng pagpili'), T('Click a point, pick a barangay or zone from a list, or draw a shape on the map.', 'Mag-click ng punto, pumili ng barangay o zone sa listahan, o gumuhit ng hugis sa mapa.'), null, { setup: studio('pick', { mode: 'area' }) }),
        S('draw', 'a-draw', T('Draw an area', 'Gumuhit ng lugar'), T('Click corners on the map. Finish area closes the shape and locks it. Undo removes the last corner. Start again clears it.', 'Mag-click ng mga sulok sa mapa. Isinasara at nilo-lock ng Finish area ang hugis. Inaalis ng Undo ang huling sulok. Binubura ng Start again.'), null, { setup: async (c) => { await studio('pick', { mode: 'area' })(c); await c.bridge.setTool('draw') } }),
        S('summary', 'a-summary', T('What the area holds', 'Ano ang laman ng lugar'), T('This example area has been chosen for you. The summary counts its squares. A square is COUNTED when its centre is inside, or at least half of it is covered; a square only touched is listed apart.', 'Pinili para sa iyo ang halimbawang lugar na ito. Binibilang ng buod ang mga parisukat nito. BILANG ang parisukat kapag nasa loob ang gitna nito, o hindi bababa sa kalahati ang sakop; ang nahipo lang ay hiwalay na nakalista.'), T('The dashed grey line on the map marks squares that were only touched.', 'Ang putol-putol na abuhing linya sa mapa ay nagmamarka ng mga parisukat na nahipo lang.'), { setup: async (c) => { await studio('pick', { mode: 'area' })(c); await c.bridge.setExampleArea() } }),
      ],
    },
    {
      id: 'plan',
      title: T('Plan', 'Plano'),
      steps: [
        S('plan', 's-step-plan', T('Step 5: Plan', 'Hakbang 5: Plano'), T('Turn your choices into a planting plan: how many trees, in which blocks. A block is one 100 m grid square planted at the species spacing.', 'Gawing plano ng pagtatanim ang mga pinili mo: ilang puno, sa anong block. Ang block ay isang 100 m na parisukat na tinatamnan ayon sa layo ng species.'), null, { setup: studio('plan') }),
        S('name', 'p-name', T('Campaign name', 'Pangalan ng kampanya'), T('The name of the planting event, saved with the plan.', 'Ang pangalan ng event ng pagtatanim, naka-save kasama ng plano.'), null, { setup: studio('plan') }),
        S('unit', 'p-unit', T('Assigned unit', 'Itinalagang yunit'), T('The team that will do the planting. Optional.', 'Ang pangkat na magtatanim. Opsyonal.'), null, { setup: studio('plan') }),
        S('trees', 'p-trees', T('Number of trees', 'Bilang ng puno'), T('How many trees in total, 1 to 2000. Or give each species its own number if you chose your own species.', 'Ilang puno lahat, 1 hanggang 2000. O bigyan ang bawat species ng sariling bilang kung ikaw ang pumili ng species.'), null, { setup: studio('plan') }),
        S('plan-summary', 'p-summary', T('What the plan will use', 'Ang gagamitin ng plano'), T('The area, the dates and the species, and how many suitable squares are available.', 'Ang lugar, petsa at species, at kung ilang angkop na parisukat ang magagamit.'), null, { setup: studio('plan') }),
        S('create', 'p-create', T('Create plan', 'Gumawa ng plano'), T('This button saves the plan on the server. The tour only shows it: it will not press it.', 'Sine-save ng button na ito ang plano sa server. Ipinapakita lang ito ng tour: hindi nito ito pipindutin.'), T('After a plan is made, Make another plan starts again and the plan stays saved in Campaign Logs.', 'Pagkatapos magawa ang plano, ang Make another plan ay magsisimula muli at nananatiling naka-save ang plano sa Campaign Logs.'), { setup: studio('plan') }),
      ],
    },
    {
      id: 'more',
      title: T('The More list', 'Ang More list'),
      steps: [
        S('more', 's-more', T('More', 'Dagdag'), T('Known limits, data credits, the dataset version and the field checks live here.', 'Narito ang mga kilalang limitasyon, kredito ng datos, bersyon ng dataset at mga field check.'), null, { setup: async ({ bridge, ui }) => { await bridge.setSidebar(true); await bridge.setStep('plan'); if (!ui.exists('s-more-limits')) await ui.toggle('s-more-toggle') } }),
        S('limits', 's-more-limits', T('Known limits', 'Mga kilalang limitasyon'), T('What the system does not know or does not do, in plain words. Read this before you trust a result.', 'Ang hindi alam o hindi ginagawa ng sistema, sa simpleng salita. Basahin bago magtiwala sa resulta.'), T('Distance to creeks and rivers is used as a soft wetness factor (50 metres), but MENRO has not answered the waterways question, so this layer is not checked.', 'Ginagamit ang layo sa mga sapa at ilog bilang malambot na salik ng halumigmig (50 metro), pero hindi pa sumasagot ang MENRO sa tanong tungkol sa mga daluyan ng tubig, kaya hindi pa nasusuri ang layer na ito.'), { setup: async ({ bridge, ui }) => { await bridge.setSidebar(true); if (!ui.exists('s-more-limits')) await ui.toggle('s-more-toggle') } }),
        S('credits', 's-more-credits', T('Data credits', 'Kredito ng datos'), T('Where each kind of data comes from, with its licence.', 'Kung saan galing ang bawat uri ng datos, kasama ang lisensya.'), null, { setup: async ({ bridge, ui }) => { await bridge.setSidebar(true); if (!ui.exists('s-more-credits')) await ui.toggle('s-more-toggle') } }),
        S('dataset', 's-more-dataset', T('Dataset version', 'Bersyon ng dataset'), T('The version of the species data. It is a review release: the agriculturist has not signed it off.', 'Ang bersyon ng datos ng species. Review release ito: hindi pa pirmado ng agriculturist.'), null, { setup: async ({ bridge, ui }) => { await bridge.setSidebar(true); if (!ui.exists('s-more-dataset')) await ui.toggle('s-more-toggle') } }),
        S('field', 's-more-field', T('Field checks', 'Mga field check'), T('What the field team saw on the ground: counts, a download of all checks, and an import of a filled sheet.', 'Ang nakita ng field team sa lupa: bilang, download ng lahat ng check, at import ng napunan na sheet.'), null, { setup: async ({ bridge, ui }) => { await bridge.setSidebar(true); if (!ui.exists('s-more-field')) await ui.toggle('s-more-toggle') } }),
      ],
    },
  ],
}


// ---------------------------------------------------------------------------------------------------------------------------------------------------------------- ACTIVE STUDIO: the map
// on a phone the left panel covers the map controls: the map tour closes it first
const mapOnly = async ({ bridge }) => { if (window.innerWidth < 900) await bridge.setSidebar(false) }
const legendOpen = async (c) => { await mapOnly(c); await c.bridge.setLegend(true) }
const legendClosed = async (c) => { await mapOnly(c); await c.bridge.setLegend(false) }
const STUDIO_MAP = {
  id: 'studio-map',
  page: 'studio',
  title: T('Plan & Map: the map', 'Plan & Map: ang mapa'),
  blurb: T('Search, zoom, my location, layers, legend, colours, right-click.', 'Hanapin, zoom, aking lokasyon, layers, legend, kulay, right-click.'),
  sections: [
    {
      id: 'search',
      title: T('Search', 'Paghahanap'),
      steps: [
        S('search', 'm-search', T('Search the map', 'Hanapin sa mapa'), T('Type a barangay, a species, a point number, or coordinates such as 14.69, 121.12. Press Ctrl and K to jump here. Choosing a result moves the map and opens its panel.', 'Mag-type ng barangay, species, numero ng punto, o koordinato tulad ng 14.69, 121.12. Pindutin ang Ctrl at K para mapunta rito. Ililipat ng napili ang mapa at bubuksan ang panel nito.'), T('Places such as streets only work if the online place search is switched on.', 'Gumagana lang ang mga lugar tulad ng kalye kapag naka-on ang online na paghahanap ng lugar.'), { setup: async (c) => { await mapOnly(c) } }),
      ],
    },
    {
      id: 'controls',
      title: T('Map controls', 'Mga control ng mapa'),
      steps: [
        S('zoom', 'm-zoom', T('Zoom', 'Zoom'), T('Plus and minus zoom the map. You can also pinch with two fingers, or scroll with the mouse. Zoom in far enough to see single 100 m squares.', 'Ang plus at minus ay nagza-zoom ng mapa. Puwede ring i-pinch ng dalawang daliri, o mag-scroll gamit ang mouse. Mag-zoom nang malapit para makita ang bawat 100 m na parisukat.'), null, { setup: mapOnly }),
        S('locate', 'm-locate', T('My location', 'Aking lokasyon'), T('Moves the map to where you are, with a blue dot. It needs a secure (HTTPS) page and your permission. Your position stays in this browser and is never sent anywhere.', 'Inililipat ang mapa sa kinaroroonan mo, may asul na tuldok. Kailangan ng ligtas (HTTPS) na pahina at ng pahintulot mo. Nananatili sa browser na ito ang posisyon mo at hindi ipinapadala kahit saan.'), null, { setup: mapOnly }),
        S('locateset', 'm-locate-set', T('Set my location on the map', 'Itakda ang lokasyon ko sa mapa'), T('If your device cannot find you, tap this and then tap the map where you are.', 'Kung hindi ka mahanap ng device mo, i-tap ito at i-tap ang mapa kung nasaan ka.'), null, { optional: true, setup: mapOnly }),
        S('mapview', 'm-mapview', T('Map view', 'Map view'), T('Opens the map options: Simple or Detailed, the map type, and the extra layers.', 'Binubuksan ang mga opsyon ng mapa: Simple o Detailed, uri ng mapa, at mga dagdag na layer.'), null, { setup: async (c) => { await mapOnly(c); if (c.ui.exists('m-mapview-menu')) await c.ui.toggle('m-mapview') } }),
        S('mapviewmenu', 'm-mapview-menu', T('Layers and detail', 'Mga layer at detalye'), T('Simple shows coloured squares, outlines and names. Detailed adds every field-check symbol, the tree codes and the grey squares. You can also switch the satellite picture, the zoning colours and the ground-cover layer.', 'Ang Simple ay may kulay na parisukat, outline at pangalan. Dinadagdagan ito ng Detailed ng bawat simbolo ng field check, code ng puno at abuhing parisukat. Puwede ring palitan ang satellite, kulay ng zoning at ground-cover layer.'), null, { setup: async (c) => { await mapOnly(c); if (!c.ui.exists('m-mapview-menu')) await c.ui.toggle('m-mapview') }, teardown: async ({ ui }) => { if (ui.exists('m-mapview-menu')) await ui.toggle('m-mapview') } }),
        S('legendbtn', 'm-legend-btn', T('The legend button', 'Ang legend button'), T('Opens the legend: what the colours of the map mean.', 'Binubuksan ang legend: ang ibig sabihin ng mga kulay ng mapa.'), null, { setup: legendClosed }),
        S('collapse', 'm-collapse', T('Hide the control panel', 'Itago ang control panel'), T('Hides or shows the left panel so the map has the whole screen. Your choices stay.', 'Itinatago o ipinapakita ang kaliwang panel para ang mapa ang sumakop sa buong screen. Nananatili ang mga pinili mo.'), null, { setup: mapOnly }),
      ],
    },
    {
      id: 'colours',
      title: T('Colours and symbols', 'Mga kulay at simbolo'),
      steps: [
        S('legend', 'm-legend', T('What the colours mean', 'Ang ibig sabihin ng mga kulay'), T('Each square is a 100 m by 100 m piece of planting zone. Green (Good) means the species match is 55% or more, orange (Moderate) 35% to 55%, red (Poor) below 35%. Grey means not suitable here, or no value.', 'Ang bawat parisukat ay 100 m by 100 m na bahagi ng planting zone. Berde (Good): 55% pataas ang tugma ng species, kahel (Moderate): 35% hanggang 55%, pula (Poor): mas mababa sa 35%. Abo: hindi angkop dito, o walang halaga.'), T('A colour is advice about the land, not a promise that trees will live.', 'Ang kulay ay payo tungkol sa lupa, hindi pangako na mabubuhay ang mga puno.'), { setup: legendOpen }),
        S('squares', 'm-map', T('The coloured squares', 'Ang mga kulay na parisukat'), T('Zoom in and the colours become squares. Hover or tap one to see its barangay, its score and its best species. Click it to open its panel on the right.', 'Mag-zoom in at magiging mga parisukat ang mga kulay. I-hover o i-tap ang isa para makita ang barangay, iskor at pinakamahusay na species nito. I-click para buksan ang panel nito sa kanan.'), null, { region: { x: 0.45, y: 0.5, w: 0.22, h: 0.22 }, setup: legendClosed }),
        S('labels', 'm-map', T('Barangay names and outlines', 'Pangalan at outline ng barangay'), T('The thin lines are the barangay boundaries and the names sit inside them. The thick outline is the edge of the municipality.', 'Ang manipis na linya ay hangganan ng barangay at nasa loob nila ang pangalan. Ang makapal na outline ay gilid ng munisipyo.'), null, { region: { x: 0.55, y: 0.45, w: 0.25, h: 0.2 }, setup: legendClosed }),
        S('fieldmarks', 'm-legend', T('Field-check symbols', 'Mga simbolo ng field check'), T('When people check a square on the ground, a mark is drawn on it. Every mark is the same violet; the SHAPE tells the status: a tick: planted, a ring: marked plantable, a question mark: needs recheck, a cross: not plantable. The words are always written next to it.', 'Kapag sinuri ng tao ang parisukat sa lupa, may marka itong iginuguhit. Iisang violet ang lahat ng marka; ang HUGIS ang nagsasabi ng katayuan: tsek: naitanim na, bilog: maaaring taniman, tandang pananong: kailangang suriin muli, ekis: hindi maaaring taniman. Laging nakasulat ang salita sa tabi.'), null, { setup: legendOpen }),
        S('planblocks', 'm-legend', T('Planned blocks', 'Mga planong block'), T('After you make a plan, its blocks are drawn as shapes with the number of trees, one shape for each species. A dotted ring marks land outside the zoning map.', 'Pagkatapos gumawa ng plano, ang mga block nito ay iginuguhit bilang hugis na may bilang ng puno, isang hugis para sa bawat species. Ang may tuldok na bilog ay nagmamarka ng lupang labas sa zoning map.'), null, { setup: legendOpen }),
      ],
    },
    {
      id: 'menu',
      title: T('Right-click menu', 'Right-click menu'),
      steps: [
        S('ctx', 'm-ctxmenu', T('Right-click or press and hold', 'Right-click o pindutin nang matagal'), T('A menu opens for the square you pressed: where it is, its zone, the species here, and the field-check buttons. This is the example point.', 'May menu para sa parisukat na pinindot mo: nasaan ito, ang zone nito, ang species dito, at ang mga button ng field check. Ito ang halimbawang punto.'), T('The tour only shows the menu. It never presses a field-check button.', 'Ipinapakita lang ng tour ang menu. Hindi nito pipindutin ang anumang button ng field check.'), { setup: async ({ bridge }) => { await bridge.setSidebar(true); await bridge.openExampleMenu() }, teardown: async ({ bridge }) => { await bridge.closeMenu() } }),
      ],
    },
  ],
}

// ---------------------------------------------------------------------------------------------------------------------------------------------------------------- ACTIVE STUDIO: the point panel and the species card
const examplePoint = async ({ bridge }) => { await bridge.setSidebar(true); await bridge.setMode('species'); await bridge.openExamplePoint() }
const STUDIO_POINT = {
  id: 'studio-point',
  page: 'studio',
  title: T('Plan & Map: the point panel', 'Plan & Map: ang panel ng punto'),
  blurb: T('What a clicked square tells you (uses the Example point).', 'Ang sinasabi ng pinindot na parisukat (gamit ang Halimbawang punto).'),
  sections: [
    {
      id: 'simple',
      title: T('The simple view', 'Ang simpleng view'),
      steps: [
        S('panel', 'r-panel', T('The Example point', 'Ang Halimbawang punto'), T('This panel opens when you click a square. The tour uses a fixed Example point where many species fit, so it never depends on what you selected.', 'Bumubukas ang panel na ito kapag nag-click ka ng parisukat. Gumagamit ang tour ng nakatakdang Halimbawang punto kung saan maraming species ang angkop, kaya hindi ito umaasa sa pinili mo.'), null, { setup: async (c) => { await examplePoint(c); await c.bridge.setView('compact') } }),
        S('view', 'r-view', T('Simple or Detailed', 'Simple o Detailed'), T('Simple uses plain words. Detailed shows the numbers, the month strips and where every value comes from.', 'Simpleng salita ang Simple. Ipinapakita ng Detailed ang mga numero, month strip at kung saan galing ang bawat halaga.'), null, { setup: async (c) => { await examplePoint(c); await c.bridge.setView('compact') } }),
        S('header', 'r-header', T('Where this is', 'Kung nasaan ito'), T('The barangay of the square, with a short note about its land when there is one.', 'Ang barangay ng parisukat, may maikling tala tungkol sa lupa nito kung meron.'), null, { setup: examplePoint }),
        S('verdict', 'r-verdict', T('The verdict', 'Ang hatol'), T('One sentence: how good this place is for the top species, the overall match in percent, and whether it is in its planting months. “Overall match” combines how well the site suits the species with how well the species suits your purpose.', 'Isang pangungusap: gaano kaganda ang lugar para sa nangungunang species, ang kabuuang tugma sa porsiyento, at kung nasa buwan ng pagtatanim ito. Pinagsasama ng “overall match” kung gaano kabagay ang lugar sa species at kung gaano kabagay ang species sa layunin mo.'), null, { setup: examplePoint }),
        S('field', 'r-field', T('Field check', 'Field check'), T('What the field team saw here, if anyone has checked it: planted, marked plantable, needs recheck, or not plantable. The button opens the menu to record a check.', 'Ang nakita ng field team dito, kung may nag-check na: naitanim na, maaaring taniman, kailangang suriin muli, o hindi maaaring taniman. Binubuksan ng button ang menu para magtala ng check.'), T('A not-plantable mark can leave the square out of rankings and plans; the other marks never change a score.', 'Ang marka na hindi maaaring taniman ay puwedeng mag-alis sa parisukat sa mga ranggo at plano; hindi binabago ng ibang marka ang iskor.'), { setup: examplePoint }),
        S('species', 'r-species', T('Best species for this spot', 'Pinakamahusay na species sa lugar na ito'), T('The species that suit this square, best first, and how many of the 45 suit it. Each row has a colour bar for the match, a season badge and a pH icon.', 'Ang mga species na angkop sa parisukat na ito, pinakamahusay muna, at ilan sa 45 ang angkop. May color bar ng tugma ang bawat row, season badge at pH icon.'), null, { setup: examplePoint }),
        S('row', 'r-row', T('One species', 'Isang species'), T('Name (tap it for the species card), the match as Good, Moderate or Poor with its percent, and the season: In season, Partly, or Outside best months. Outside the best months you can still plant, but expect more watering and more losses.', 'Pangalan (i-tap para sa species card), ang tugma bilang Good, Moderate o Poor at porsiyento, at ang panahon: In season, Partly, o Outside best months. Sa labas ng pinakamainam na buwan puwede pa ring magtanim, pero asahan ang mas maraming dilig at pagkalugi.'), null, { setup: examplePoint }),
        S('details', 'r-row-details', T('Details', 'Mga detalye'), T('Opens the extra lines of this species: the numbers, the month strip, the flags, and why the score is what it is.', 'Binubuksan ang dagdag na linya ng species na ito: mga numero, month strip, flag, at bakit ganoon ang iskor.'), null, { setup: examplePoint }),
      ],
    },
    {
      id: 'detailed',
      title: T('The detailed view', 'Ang detalyadong view'),
      steps: [
        S('land', 'r-land', T('Land details', 'Detalye ng lupa'), T('Coordinates, elevation, slope, zoning, soil and satellite ground cover for the square. Anything that needs a permit or care is flagged.', 'Koordinato, taas, tarik, zoning, lupa at satellite ground cover ng parisukat. Namarkahan ang anumang nangangailangan ng permiso o pag-iingat.'), null, { setup: async (c) => { await examplePoint(c); await c.bridge.setView('full'); await c.ui.openDetails('r-land') } }),
        S('ph', 'r-ph', T('Soil pH (an estimate)', 'pH ng lupa (tantiya)'), T('The pH of the soil here comes from SoilGrids, a world map with 250 m pixels. It is an ESTIMATE and “not certain”: measure on site with a pH kit before you rely on it. It is advice only and never changes a score.', 'Ang pH ng lupa rito ay galing sa SoilGrids, isang mapa ng mundo na may 250 m na pixel. TANTIYA lamang ito at “hindi tiyak”: sukatin sa mismong lugar gamit ang pH kit bago umasa. Payo lang ito at hindi nagbabago ng iskor.'), null, { setup: async (c) => { await examplePoint(c); await c.bridge.setView('full'); await c.ui.openDetails('r-land') } }),
        S('scores', 'r-scores', T('The numbers', 'Ang mga numero'), T('S is site suitability, P is purpose fit, W is the overall score (S times P, and 0 when S is below 0.50). Confidence says how many of the facts behind it are sourced.', 'Ang S ay pagiging angkop ng lugar, ang P ay tugma sa layunin, ang W ang kabuuang iskor (S beses P, at 0 kapag mas mababa sa 0.50 ang S). Sinasabi ng Confidence kung ilan sa mga datos sa likod nito ang may sanggunian.'), null, { setup: async (c) => { await examplePoint(c); await c.bridge.setView('full') } }),
        S('months', 'r-months', T('The month strip', 'Ang month strip'), T('Twelve letters from January to December. Filled letters are the best planting months of this species; a ring marks the months of your dates.', 'Labindalawang titik mula Enero hanggang Disyembre. Ang may kulay ay pinakamainam na buwan ng pagtatanim ng species; ang bilog ay ang mga buwan ng petsa mo.'), null, { setup: async (c) => { await examplePoint(c); await c.bridge.setView('full') } }),
        S('whybtn', 'r-why-btn', T('Why this score?', 'Bakit ganito ang iskor?'), T('Opens the breakdown: each term, its weight and its source.', 'Binubuksan ang breakdown: bawat termino, timbang at sanggunian.'), null, { setup: async (c) => { await examplePoint(c); await c.bridge.setView('full') } }),
        S('rf', 'r-rf', T('The Random Forest line', 'Ang linya ng Random Forest'), T('The site suitability comes from a Random Forest, a computer model that learned from the expert rules. Hard limits such as zone, elevation and steep slope always apply first. It does not measure real survival.', 'Ang pagiging angkop ng lugar ay galing sa Random Forest, isang computer model na natuto mula sa mga patakaran ng eksperto. Laging nauuna ang mahihigpit na limitasyon tulad ng zone, taas at matarik na dalisdis. Hindi nito sinusukat ang tunay na pagkabuhay.'), null, { setup: async (c) => { await examplePoint(c); await c.bridge.setView('full'); if (!c.ui.exists('r-rf')) await c.ui.toggle('r-why-btn') } }),
      ],
    },
    {
      id: 'card',
      title: T('The species card', 'Ang species card'),
      steps: [
        S('card', 'c-card', T('The species card', 'Ang species card'), T('Opens from any species name. It lists what is known about one species, each value with its source link and rank. A missing value says Data Unavailable.', 'Bumubukas mula sa pangalan ng anumang species. Inililista nito ang alam tungkol sa isang species, bawat halaga may link ng sanggunian at ranggo. Ang kulang na halaga ay nagsasabing Data Unavailable.'), null, { setup: async ({ bridge }) => { await bridge.openSpeciesCard(EXAMPLE_SPECIES_ID) }, teardown: async ({ bridge }) => { await bridge.closeSpeciesCard() } }),
        S('timing', 'c-timing', T('Planting stage and timing', 'Yugto at panahon ng pagtatanim'), T('Germination, propagation, depth, method and spacing, and the planting months with a month strip for your dates.', 'Pagsibol, pagpaparami, lalim, paraan at layo, at ang buwan ng pagtatanim na may month strip para sa petsa mo.'), null, { region: { x: 0, y: 0, w: 1, h: 0.4 }, setup: async ({ bridge }) => { await bridge.openSpeciesCard(EXAMPLE_SPECIES_ID) }, teardown: async ({ bridge }) => { await bridge.closeSpeciesCard() } }),
        S('partners', 'c-partners', T('Works well with', 'Kasamang species'), T('Species that grow well beside this one, with the reason in one line. A partner named in the sources says so; the rules are provisional.', 'Mga species na mahusay tumubo sa tabi nito, may dahilan sa isang linya. Sinasabi kapag pinangalanan ang kapartner sa mga sanggunian; pansamantala ang mga patakaran.'), null, { setup: async ({ bridge }) => { await bridge.openSpeciesCard(EXAMPLE_SPECIES_ID) }, teardown: async ({ bridge }) => { await bridge.closeSpeciesCard() } }),
        S('advice', 'c-advice', T('Ways to improve survival', 'Mga paraan para tumaas ang pagkabuhay'), T('Short advice for this species, for example about watering, shade or grafted stock. It is advice only, still to be confirmed by the agriculturist.', 'Maikling payo para sa species na ito, halimbawa tungkol sa pagdidilig, lilim o grafted na punla. Payo lang ito, kailangan pang kumpirmahin ng agriculturist.'), null, { setup: async ({ bridge }) => { await bridge.openSpeciesCard(EXAMPLE_SPECIES_ID) }, teardown: async ({ bridge }) => { await bridge.closeSpeciesCard() } }),
      ],
    },
  ],
}

// ---------------------------------------------------------------------------------------------------------------------------------------------------------------- ACTIVE STUDIO: a saved plan (needs one)
const planOpen = async ({ bridge, ui }) => { await bridge.setSidebar(true); if (!ui.exists('r-plan-tabs')) await bridge.openLatestPlan() }
const planTab = (tab, tabId = tab) => async (c) => { await planOpen(c); if (!c.ui.exists(`r-${tab}`)) await c.ui.toggle(`r-ptab-${tabId}`) }
const STUDIO_PLAN = {
  id: 'studio-plan',
  page: 'studio',
  requires: 'plan',
  title: T('Plan & Map: a saved plan', 'Plan & Map: isang naka-save na plano'),
  blurb: T('The plan panel: Plan, Field kit, Progress (opens your latest saved plan).', 'Ang plan panel: Plan, Field kit, Progress (binubuksan ang pinakabagong naka-save mong plano).'),
  sections: [
    {
      id: 'plan',
      title: T('Plan', 'Plano'),
      steps: [
        S('numbers', 'r-plan-numbers', T('The plan in three numbers', 'Ang plano sa tatlong numero'), T('Trees, blocks and hectares. A block is one 100 m square planted at the species spacing.', 'Mga puno, block at ektarya. Ang block ay isang 100 m na parisukat na tinatamnan ayon sa layo ng species.'), null, { setup: planOpen }),
        S('tabs', 'r-plan-tabs', T('Three tabs', 'Tatlong tab'), T('Plan shows what to plant where. Field kit builds the files and the planter link for the team. Progress counts what has been planted.', 'Ipinapakita ng Plan kung ano ang itatanim at saan. Gumagawa ang Field kit ng mga file at planter link para sa pangkat. Binibilang ng Progress ang naitanim na.'), null, { setup: planOpen }),
        S('notes', 'r-plan-notes', T('Good to know', 'Mabuting malaman'), T('Short notes that need attention: zoning, steep slopes, satellite ground cover, the season.', 'Mga maikling tala na kailangan ng pansin: zoning, matarik na dalisdis, satellite ground cover, panahon.'), null, { setup: planTab('plan-notes', 'plan'), optional: true }),
      ],
    },
    {
      id: 'kit',
      title: T('Field kit', 'Field kit'),
      steps: [
        S('kit', 'r-kit', T('The field kit', 'Ang field kit'), T('Build the kit to get points for a GPS app, a Google Earth file, the point list, a printed map and instructions. The tour only shows it: it will not build anything.', 'Buuin ang kit para makakuha ng mga punto para sa GPS app, Google Earth file, listahan ng punto, naka-print na mapa at tagubilin. Ipinapakita lang ito ng tour: wala itong bubuuin.'), null, { setup: planTab('kit') }),
        S('planter', 'r-planter', T('Planter link', 'Planter link'), T('A page for the planting team to open on a phone. The link works for a limited time and can be switched off. A QR code appears once the link exists.', 'Isang pahina para sa planting team na bubuksan sa phone. May limitadong oras ang link at puwedeng patayin. Lalabas ang QR code kapag may link na.'), null, { setup: planTab('kit') }),
      ],
    },
    {
      id: 'progress',
      title: T('Progress', 'Progreso'),
      steps: [
        S('progress', 'r-progress', T('Progress', 'Progreso'), T('Counted from the saved field checks of this plan: planted, partly done, problem and to do, with a button to plan a top-up for trees that could not be planted.', 'Binibilang mula sa mga naka-save na field check ng planong ito: naitanim, bahagya, may problema at gagawin pa, may button para magplano ng dagdag sa mga punong hindi naitanim.'), null, { setup: planTab('progress') }),
      ],
    },
  ],
}


// ---------------------------------------------------------------------------------------------------------------------------------------------------------------- WEATHER
const pageHead = (title, text) => S('head', 'p-head', title, text, null)
const WEATHER = {
  id: 'weather',
  page: 'weather',
  title: T('Weather', 'Panahon'),
  blurb: T('The week ahead at one place, with advice for planting days.', 'Ang linggong darating sa isang lugar, may payo para sa mga araw ng pagtatanim.'),
  sections: [
    {
      id: 'choose',
      title: T('Place and purpose', 'Lugar at layunin'),
      steps: [
        pageHead(T('The Weather page', 'Ang pahina ng Panahon'), T('The next seven days at one place, a plain verdict for planting this week, and the species that suit the week. It is a planning aid, not a guarantee.', 'Ang susunod na pitong araw sa isang lugar, simpleng hatol para sa pagtatanim ngayong linggo, at ang mga species na angkop sa linggo. Gabay sa pagpaplano ito, hindi garantiya.')),
        S('where', 'w-where', T('Where', 'Saan'), T('Pick the place: the centre of San Mateo, a barangay, the last point you clicked, or the middle of a plan.', 'Piliin ang lugar: gitna ng San Mateo, isang barangay, ang huling pinindot mong punto, o gitna ng plano.')),
        S('purpose', 'w-purpose', T('Planting purpose', 'Layunin ng pagtatanim'), T('The purpose orders the species lists below.', 'Inaayos ng layunin ang mga listahan ng species sa ibaba.')),
        S('view', 'w-view', T('Simple or Detailed', 'Simple o Detailed'), T('Simple gives short lines. Detailed adds each species\u2019 drought tolerance, months and sources.', 'Maikli ang Simple. Idinaragdag ng Detailed ang tolerance sa tagtuyot, mga buwan at sanggunian ng bawat species.')),
      ],
    },
    {
      id: 'week',
      title: T('The week', 'Ang linggo'),
      steps: [
        S('hero', 'w-hero', T('Today at a glance', 'Ngayon sa isang tingin'), T('The sky picture shows today\u2019s rain amount and the temperatures. Only rain, the highest and lowest temperature are forecast; there is no wind or chance of rain here.', 'Ipinapakita ng larawan ng langit ang dami ng ulan ngayon at mga temperatura. Ulan, pinakamataas at pinakamababang temperatura lang ang tinataya; walang hangin o tsansa ng ulan dito.')),
        S('strip', 'w-strip', T('The seven days', 'Ang pitong araw'), T('One column per day: the rain amount in millimetres, and the highest and lowest temperature.', 'Isang kolum bawat araw: ang dami ng ulan sa milimetro, at ang pinakamataas at pinakamababang temperatura.')),
        S('rules', 'w-rules', T('Day words', 'Mga salita sa araw'), T('Dry is under 1 mm, light rain 1 to 10 mm, rainy 10 mm or more. Heavy rain above the limit shown makes the week \u201Cavoid\u201D.', 'Ang tuyo ay mas mababa sa 1 mm, magaang ulan 1 hanggang 10 mm, maulan 10 mm pataas. Ang malakas na ulan na lampas sa ipinakitang limit ay gagawing \u201Cavoid\u201D ang linggo.')),
        S('verdict', 'w-verdict', T('The verdict', 'Ang hatol'), T('Good to plant, Plant with care, or Avoid this week, with the reasons and the numbers behind them. A dry week under 20 mm needs watering.', 'Good to plant, Plant with care, o Avoid this week, kasama ang dahilan at mga numero. Ang tuyong linggo na wala pang 20 mm ay kailangang diligan.')),
        S('numbers', 'w-numbers', T('The week in numbers', 'Ang linggo sa numero'), T('Rain over seven days, the wettest and hottest day, and the limits the verdict uses. These limits are provisional.', 'Ulan sa pitong araw, ang pinakamaulan at pinakamainit na araw, at ang mga limit na ginagamit ng hatol. Pansamantala ang mga limit na ito.')),
      ],
    },
    {
      id: 'species',
      title: T('Species for the week', 'Mga species para sa linggo'),
      steps: [
        S('best', 'w-best', T('In their best months', 'Nasa pinakamainam nilang buwan'), T('Species that are in their planting months this week and are not hit by a weather warning, best match first.', 'Mga species na nasa buwan ng pagtatanim ngayong linggo at hindi tinamaan ng babala ng panahon, pinakamataas ang tugma muna.')),
        S('water', 'w-water', T('Only if you can water', 'Kung kaya mo lang magdilig'), T('Outside their best months but with High drought tolerance. You can plant them only if you are able to water.', 'Labas sa pinakamainam na buwan pero may High na tolerance sa tagtuyot. Puwede mo lang silang itanim kung kaya mong magdilig.'), null, { region: { x: 0, y: 0, w: 1, h: 0.2 } }),
        S('source', 'w-source', T('Source and last update', 'Pinagmulan at huling update'), T('Where the forecast comes from. When the service is busy the page shows a saved copy and says \u201CLast updated \u2026, may be out of date\u201D; Try again loads it afresh.', 'Kung saan galing ang forecast. Kapag abala ang serbisyo, nagpapakita ang pahina ng naka-save na kopya at sinasabing \u201CLast updated \u2026, maaaring luma na\u201D; ang Try again ay nagloload ng bago.')),
      ],
    },
  ],
}

// ---------------------------------------------------------------------------------------------------------------------------------------------------------------- CAMPAIGN LOGS
const LOGS = {
  id: 'logs',
  page: 'history',
  title: T('Campaign Logs', 'Campaign Logs'),
  blurb: T('Your saved plans, their status and progress.', 'Ang mga naka-save mong plano, katayuan at progreso.'),
  sections: [
    {
      id: 'logs',
      title: T('The list of plans', 'Ang listahan ng plano'),
      steps: [
        pageHead(T('Campaign Logs', 'Campaign Logs'), T('Every plan you saved, newest first, with its dates, status and field kit. Nothing here changes a plan.', 'Lahat ng planong sine-save mo, pinakabago muna, may petsa, katayuan at field kit. Walang binabago sa plano rito.')),
        S('filters', 'l-filters', T('Filter by status', 'Salain ayon sa katayuan'), T('Active, Upcoming, Concluded, or No dates: worked out from the dates saved with each plan.', 'Active, Upcoming, Concluded, o No dates: kinukuwenta mula sa petsang naka-save sa bawat plano.'), null, { optional: true }),
        S('search', 'l-search', T('Search', 'Maghanap'), T('Type part of a campaign name, a unit or a plan id.', 'Mag-type ng bahagi ng pangalan ng kampanya, yunit o plan id.'), null, { optional: true }),
        S('list', 'l-list', T('Your plans', 'Ang mga plano mo'), T('One card per saved plan. When there is none, this says so and offers a button to go and make one.', 'Isang card bawat naka-save na plano. Kapag wala, sasabihin ito at may button para gumawa.'), null, { region: { x: 0, y: 0, w: 1, h: 0.06 } }),
        S('card', 'l-card', T('One plan', 'Isang plano'), T('The name, unit, dates and status chip, the plan id, whether a field kit was built, and a weather card for the planting days.', 'Ang pangalan, yunit, petsa at status chip, plan id, kung nagawa na ang field kit, at weather card para sa mga araw ng pagtatanim.'), null, { optional: true }),
        S('open', 'l-open', T('Open on map', 'Buksan sa mapa'), T('Opens the plan in Plan & Map, with its blocks on the map. Progress and top-up counts what the field team has planted.', 'Binubuksan ang plano sa Plan & Map, kasama ang mga block sa mapa. Binibilang ng Progress and top-up ang naitanim ng field team.'), null, { optional: true }),
        S('studio', 'l-studio', T('Go to Plan & Map', 'Pumunta sa Plan & Map'), T('With no plans yet, this button takes you to Plan & Map to make the first one.', 'Kung wala pang plano, dadalhin ka ng button na ito sa Plan & Map para gumawa ng una.'), null, { optional: true }),
      ],
    },
  ],
}

// ---------------------------------------------------------------------------------------------------------------------------------------------------------------- SYSTEM ANALYTICS
const ANALYTICS = {
  id: 'analytics',
  page: 'analytics',
  title: T('System Analytics', 'System Analytics'),
  blurb: T('Counts of what exists, how to read each chart.', 'Mga bilang ng mga meron, paano basahin ang bawat chart.'),
  sections: [
    {
      id: 'top',
      title: T('Filters and numbers', 'Mga filter at numero'),
      steps: [
        pageHead(T('System Analytics', 'System Analytics'), T('Counts of what exists: suitable squares, soil pH estimates, plans and field checks. Nothing here is forecast and nothing here changes a score.', 'Mga bilang ng mga meron: angkop na parisukat, tantiya ng pH ng lupa, plano at field check. Walang tinataya rito at walang binabago sa iskor.')),
        S('filters', 'an-filters', T('Filters', 'Mga filter'), T('Narrow the charts by barangay or species, and the activity by dates. Clear filters shows everything again.', 'Paliitin ang mga chart ayon sa barangay o species, at ang aktibidad ayon sa petsa. Ibinabalik ng Clear filters ang lahat.')),
        S('kpis', 'an-kpis', T('Six big numbers', 'Anim na malalaking numero'), T('Squares scored, species, suitable squares, plans, trees planned and field checks. A suitable square has a site score of 0.50 or more for at least one species.', 'Mga parisukat na na-score, species, angkop na parisukat, plano, planong puno at field check. Angkop ang parisukat kung 0.50 pataas ang site score nito sa kahit isang species.')),
      ],
    },
    {
      id: 'charts',
      title: T('The charts', 'Ang mga chart'),
      steps: [
        S('suit', 'an-c-suit', T('Site scores', 'Mga site score'), T('Bars of how many square-and-species pairs fall in each score range. A tall bar at zero means many pairs that the land rules out.', 'Mga bar ng dami ng pares ng parisukat-at-species sa bawat saklaw ng iskor. Ang mataas na bar sa zero ay maraming pares na hindi pinapayagan ng lupa.')),
        S('brgy', 'an-c-brgy', T('By barangay', 'Ayon sa barangay'), T('Suitable squares compared with all squares of each barangay. Longer is more.', 'Angkop na parisukat kumpara sa lahat ng parisukat ng bawat barangay. Mas mahaba ay mas marami.')),
        S('species', 'an-c-species', T('By species', 'Ayon sa species'), T('How many squares suit each species (top ten).', 'Ilang parisukat ang angkop sa bawat species (nangungunang sampu).')),
        S('ph', 'an-c-ph', T('Soil pH estimates', 'Mga tantiya ng pH ng lupa'), T('How the estimated soil pH is spread over the squares. It is an estimate from SoilGrids, not a measurement.', 'Kung paano kumalat ang tinatayang pH ng lupa sa mga parisukat. Tantiya ito mula sa SoilGrids, hindi sukat.')),
        S('verdict', 'an-c-verdict', T('pH verdicts', 'Mga hatol ng pH'), T('For each species and square: inside its pH range, outside, or \u201Cnot certain\u201D. Most are not certain because the estimate has a wide margin.', 'Para sa bawat species at parisukat: nasa saklaw ng pH, labas, o \u201Chindi tiyak\u201D. Karamihan ay hindi tiyak dahil malapad ang margin ng tantiya.')),
        S('zone', 'an-c-zone', T('By zone', 'Ayon sa zone'), T('Squares by land-use zone, and how many are outside the zoning map or have no soil data.', 'Mga parisukat ayon sa zone ng gamit ng lupa, at ilan ang labas sa zoning map o walang datos ng lupa.')),
        S('activity', 'an-c-activity', T('Activity by week', 'Aktibidad kada linggo'), T('Plans and field checks made each week. Empty until people use the system.', 'Mga planong ginawa at field check kada linggo. Walang laman hangga\u2019t hindi ginagamit ng tao ang sistema.')),
        S('trees', 'an-c-trees', T('Trees planned by week', 'Planong puno kada linggo'), T('How many trees the plans of each week hold.', 'Ilang puno ang laman ng mga plano ng bawat linggo.')),
        S('pvb', 'an-c-pvb', T('Planned and planted by barangay', 'Plano at naitanim ayon sa barangay'), T('Trees planned beside trees the field teams marked as planted.', 'Mga planong puno katabi ng mga puno na minarkahan ng field team bilang naitanim.')),
        S('pvs', 'an-c-pvs', T('Planned and planted by species', 'Plano at naitanim ayon sa species'), T('The same comparison for each species.', 'Ang parehong paghahambing para sa bawat species.')),
      ],
    },
    {
      id: 'data',
      title: T('Tables and download', 'Mga table at download'),
      steps: [
        S('table', 'an-c-suit-table', T('View table', 'Tingnan ang table'), T('Shows the numbers behind the chart as a table, for reading with a screen reader or copying.', 'Ipinapakita ang mga numero sa likod ng chart bilang table, para basahin gamit ang screen reader o kopyahin.')),
        S('csv', 'an-c-suit-csv', T('Download CSV', 'I-download ang CSV'), T('Saves the numbers of that chart as a spreadsheet file.', 'Sine-save ang mga numero ng chart na iyon bilang spreadsheet file.')),
        S('noforecast', 'an-noforecast', T('No forecast', 'Walang forecast'), T('No future is drawn here: forecasting needs survival records, and none exist yet.', 'Walang hinaharap na iginuguhit dito: kailangan ng talaan ng pagkabuhay para sa forecast, at wala pa nito.')),
      ],
    },
  ],
}

// ---------------------------------------------------------------------------------------------------------------------------------------------------------------- HELP
const HELP = {
  id: 'help',
  page: 'help',
  title: T('Help and the user guide', 'Tulong at gabay'),
  blurb: T('Questions, glossary, printing the guide.', 'Mga tanong, glossary, pag-print ng gabay.'),
  sections: [
    {
      id: 'help',
      title: T('The Help page', 'Ang Help page'),
      steps: [
        S('tour', 'help-tour', T('Tour of this page', 'Tour ng pahinang ito'), T('Starts the tour of the page you came from. Each page has its own tour.', 'Sinisimulan ang tour ng pahinang pinanggalingan mo. May sariling tour ang bawat pahina.')),
        S('alltours', 'help-alltours', T('All tours', 'Lahat ng tour'), T('Opens the list of every tour, with a short tour for each section.', 'Binubuksan ang listahan ng bawat tour, may maikling tour para sa bawat seksyon.')),
        S('print', 'help-print', T('Print this guide', 'I-print ang gabay'), T('Prints the whole guide on A4 sheets: the tours, the questions and the glossary.', 'Piniprint ang buong gabay sa A4: ang mga tour, mga tanong at glossary.')),
        S('search', 'help-search', T('Search the questions', 'Hanapin ang mga tanong'), T('Type a word such as pH, check code or nursery to find the answer.', 'Mag-type ng salita tulad ng pH, check code o nursery para mahanap ang sagot.')),
        S('faq', 'help-faq', T('Questions and answers', 'Mga tanong at sagot'), T('Tap a question to read its answer. They are grouped by topic.', 'I-tap ang tanong para mabasa ang sagot. Naka-grupo ayon sa paksa.'), null, { region: { x: 0, y: 0, w: 1, h: 0.08 } }),
        S('glossary', 'help-glossary', T('Glossary', 'Glossary'), T('The words this system uses, in plain language.', 'Ang mga salitang ginagamit ng sistemang ito, sa simpleng wika.')),
      ],
    },
  ],
}

export const TOURS = [GLOBAL, STUDIO_LEFT, STUDIO_MAP, STUDIO_POINT, STUDIO_PLAN, WEATHER, LOGS, ANALYTICS, HELP]
export const getTour = (id) => TOURS.find((t) => t.id === id) ?? null
export const tourSteps = (tour) => tour.sections.flatMap((s) => s.steps)
// the tour that explains a page (the "?" and Help always start this one)
export const PAGE_TOUR = { studio: 'studio-panel', weather: 'weather', history: 'logs', analytics: 'analytics', help: 'help' }
export { EXAMPLE_SPECIES_ID }
