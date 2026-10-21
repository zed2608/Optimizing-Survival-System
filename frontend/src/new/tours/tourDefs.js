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
        S('tabs', 'h-tabs', T('Four pages', 'Apat na pahina'), T('Active Studio is the map where you plan. The cloud shows the Weather for the week. The clipboard lists your saved plans (Campaign Logs). The bars count what exists (System Analytics).', 'Ang Active Studio ang mapa kung saan ka nagpaplano. Ang ulap ay ang Panahon sa linggo. Ang clipboard ay ang listahan ng mga naka-save na plano (Campaign Logs). Ang mga bar ay nagbibilang ng mga meron (System Analytics).'), T('A tour always explains the page you are on.', 'Ang tour ay laging nagpapaliwanag ng pahinang kinaroroonan mo.')),
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
  title: T('Studio: the control panel', 'Studio: ang control panel'),
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
        S('pick', 's-step-pick', T('Step 4: Area', 'Hakbang 4: Lugar'), T('With “I have an area” you choose the area and the system ranks the species for it.', 'Sa “I have an area”, ikaw ang pipili ng lugar at ira-rank ng sistema ang mga species para rito.'), null, { setup: studio('pick', { mode: 'area' }) }),
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
        S('summary', 'p-summary', T('What the plan will use', 'Ang gagamitin ng plano'), T('The area, the dates and the species, and how many suitable squares are available.', 'Ang lugar, petsa at species, at kung ilang angkop na parisukat ang magagamit.'), null, { setup: studio('plan') }),
        S('create', 'p-create', T('Create plan', 'Gumawa ng plano'), T('This button saves the plan on the server. The tour only shows it: it will not press it.', 'Sine-save ng button na ito ang plano sa server. Ipinapakita lang ito ng tour: hindi nito ito pipindutin.'), T('After a plan is made, Make another plan starts again and the plan stays saved in Campaign Logs.', 'Pagkatapos magawa ang plano, ang Make another plan ay magsisimula muli at nananatiling naka-save ang plano sa Campaign Logs.'), { setup: studio('plan') }),
      ],
    },
    {
      id: 'more',
      title: T('The More list', 'Ang More list'),
      steps: [
        S('more', 's-more', T('More', 'Dagdag'), T('Known limits, data credits, the dataset version and the field checks live here.', 'Narito ang mga kilalang limitasyon, kredito ng datos, bersyon ng dataset at mga field check.'), null, { setup: async ({ bridge, ui }) => { await bridge.setSidebar(true); await bridge.setStep('plan'); if (!ui.exists('s-more-limits')) await ui.toggle('s-more-toggle') } }),
        S('limits', 's-more-limits', T('Known limits', 'Mga kilalang limitasyon'), T('What the system does not know or does not do, in plain words. Read this before you trust a result.', 'Ang hindi alam o hindi ginagawa ng sistema, sa simpleng salita. Basahin bago magtiwala sa resulta.'), null, { setup: async ({ bridge, ui }) => { await bridge.setSidebar(true); if (!ui.exists('s-more-limits')) await ui.toggle('s-more-toggle') } }),
        S('credits', 's-more-credits', T('Data credits', 'Kredito ng datos'), T('Where each kind of data comes from, with its licence.', 'Kung saan galing ang bawat uri ng datos, kasama ang lisensya.'), null, { setup: async ({ bridge, ui }) => { await bridge.setSidebar(true); if (!ui.exists('s-more-credits')) await ui.toggle('s-more-toggle') } }),
        S('dataset', 's-more-dataset', T('Dataset version', 'Bersyon ng dataset'), T('The version of the species data. It is a review release: the agriculturist has not signed it off.', 'Ang bersyon ng datos ng species. Review release ito: hindi pa pirmado ng agriculturist.'), null, { setup: async ({ bridge, ui }) => { await bridge.setSidebar(true); if (!ui.exists('s-more-dataset')) await ui.toggle('s-more-toggle') } }),
        S('field', 's-more-field', T('Field checks', 'Mga field check'), T('What the field team saw on the ground: counts, a download of all checks, and an import of a filled sheet.', 'Ang nakita ng field team sa lupa: bilang, download ng lahat ng check, at import ng napunan na sheet.'), null, { setup: async ({ bridge, ui }) => { await bridge.setSidebar(true); if (!ui.exists('s-more-field')) await ui.toggle('s-more-toggle') } }),
      ],
    },
  ],
}

export const TOURS = [GLOBAL, STUDIO_LEFT]
export const getTour = (id) => TOURS.find((t) => t.id === id) ?? null
export const tourSteps = (tour) => tour.sections.flatMap((s) => s.steps)
// the tour that explains a page (the "?" and Help always start this one)
export const PAGE_TOUR = { studio: 'studio-panel', weather: 'weather', history: 'logs', analytics: 'analytics', help: 'help' }
export { EXAMPLE_SPECIES_ID }
