// The field pack MAP in headless Edge at 360 x 640: markers equal the page's coordinates (every tree of every block), the tile requests (Referer, levels, attribution), the position dot with its accuracy circle
// and cone, the line to the target, follow / re-centre / drag, the "No background map (no signal)" fallback, and the satellite layer only when it was built in. All tile requests are intercepted: no map server is contacted.
//   node tests/browser/fieldpack_map_check.mjs <address of the pack page> <folder for pictures> [<address of a pack built with --satellite>]
import { launch } from './cdp_lib.mjs'

const PAGE = process.argv[2]
const SAT_PAGE = process.argv[4] || ''
const b = await launch({ out: process.argv[3] })
const { ev, text, click, tap, check, sleep, waitFor, waitExpr, gps, noBadText } = b
await b.viewport(360, 640)
const ENGLISH = `sessionStorage.clear(); localStorage.clear(); localStorage.setItem('fieldpack:prefs', JSON.stringify({ v: 1, observer: '', trees: {}, prefs: { lang: 'en', introDone: true } }))`
await b.open(PAGE)
await ev(ENGLISH)
await b.open(PAGE)
await tap('Start')
await sleep(250)
const pack = JSON.parse(await ev("document.getElementById('pack-data').textContent"))
const origin = new URL(PAGE).origin
await noBadText('the home screen')

// ---- 1. markers on the map = the coordinates in the page, every tree of every block; the grid square and the planted area are drawn
let allOk = true, checked = 0, badExample = ''
for (const blk of pack.blocks) {
  await tap(blk.ref)
  await waitExpr(`document.querySelectorAll('#map .treeicon').length === ${blk.n}`)
  const got = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('#map .treeicon')].map((e) => [Number(e.dataset.k), Number(e.dataset.lat), Number(e.dataset.lon)]))`))
  const same = got.length === blk.n && blk.trees.every((t) => got.some((g) => g[0] === t[0] && g[1] === t[1] && g[2] === t[2]))
  if (!same) { allOk = false; badExample = blk.ref }
  checked += got.length
  if ((await ev(`document.querySelectorAll('#map svg path').length`)) < 2) { allOk = false; badExample = blk.ref + ' (grid square and planted area not drawn)' }
  await tap('Back')
  await sleep(150)
}
check(`every tree marker equals the page's coordinates (${checked} trees, ${pack.blocks.length} blocks) and the grid square and planted area are drawn`, allOk && checked === pack.blocks.reduce((s, x) => s + x.n, 0), badExample)

// ---- 2. the tiles: Referer (origin only), nothing else requested, no level above 19, attribution
const b0 = pack.blocks[0]
await ev("document.getElementById('observer').value = 'Map Tester'; document.getElementById('observer').dispatchEvent(new Event('input', { bubbles: true }))")
await tap(b0.ref)
await waitExpr(`document.querySelectorAll('#map .treeicon').length === ${b0.n}`)
await sleep(800)
await noBadText('the block screen with the map, before GPS')
for (let i = 0; i < 5; i++) { await tap('Zoom in'); await sleep(250) }
await sleep(1200)
const osm = b.tiles.filter((x) => x.url.includes('tile.openstreetmap.org'))
check('tiles come from the standard OpenStreetMap server and nothing else is requested', osm.length > 0 && b.tiles.every((x) => x.url.includes('tile.openstreetmap.org')), `${osm.length} tile requests`)
check('every tile request carries a valid Referer, the origin only (not the secret path)', osm.every((x) => x.referer === origin + '/'), 'Referer seen: ' + [...new Set(osm.map((x) => x.referer))].join(' , '))
const zs = osm.map((x) => Number(x.url.match(/openstreetmap\.org\/(\d+)\//)[1]))
check('zooming in past the native level asks for tiles of level 19 or lower only (the picture is enlarged)', Math.max(...zs) <= 19 && Math.max(...zs) >= 18, 'levels ' + [...new Set(zs)].sort().join(','))
check('attribution to OpenStreetMap contributors is visible, above the sheet and not hidden', await ev(`(() => { const a = document.querySelector('.attrib'); if (!a) return false; const r = a.getBoundingClientRect(); const e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return a.innerText.includes('OpenStreetMap') && a.innerText.includes('contributors') && (e === a || a.contains(e)) })()`))

// ---- 3. GPS: position dot with accuracy circle, line to START, arrival at START, then the trees
await tap('Start GPS')
const ST = b0.start, t5 = b0.trees[Math.min(4, b0.n - 1)]
await gps(ST[0] + 0.00036, ST[1], 6)
await waitFor(/about 40 m/)
await waitExpr(`document.querySelector('.linelabel')`)
const label = await ev(`document.querySelector('.linelabel')?.innerText`)
check('step 1: the line goes to the START corner, with its distance on the map', /about 40 m to START/.test(label || ''), label)
check('your position (blue dot) and the circle of how sure the phone is are drawn', await ev(`!!document.querySelector('#map .me .dot') && !!document.querySelector('#map svg path[stroke-dasharray="4 4"]')`))
check('the START corner has its own mark on the map', await ev(`!!document.querySelector('#map .starticon')`))
await noBadText('the block screen with a GPS reading and the map line')
await gps(ST[0], ST[1], 3)
await waitFor(/You are at START/)
check('"you are at START" only inside how sure the phone is (3 m)', (await text()).includes('You are at START'))
await ev(`document.querySelector('#map .treeicon[data-k="${t5[0]}"]').click()`)
await waitFor(new RegExp(`Next: tree ${t5[0]} of ${b0.n}`))
check('tapping a tree number on the map goes to step 3 with that tree as the next one', (await text()).includes('Step 3 of 4') && (await ev(`document.querySelector('.nextline').textContent`)).startsWith(`Next: tree ${t5[0]} of ${b0.n}`) && (await ev(`document.querySelector('#map .treeicon.st-active')?.dataset.k`)) === String(t5[0]))
check('step 3: no line to the tree (GPS is not trusted to find a tree) and the sheet says the map is approximate', !(await ev(`!!document.querySelector('.linelabel')`)) && (await text()).includes('approximate place'))
await tap('Planted')
await sleep(600)
check('planted: the marker turns green', (await ev(`document.querySelector('#map .treeicon[data-k="${t5[0]}"]')?.className`)).includes('st-planted'))
await tap('Next step'); await sleep(300)
await tap(`Tree ${t5[0]}`)
check('step 4: tapping a chip selects the same tree on the map', (await ev(`document.querySelector('.chip.active')?.dataset.k`)) === String(t5[0]) && (await ev(`document.querySelector('#map .treeicon.st-active')?.dataset.k`)) === String(t5[0]))
await tap('Previous step'); await sleep(300)
await b.shot('map_1_step3')

// ---- 4. follow, drag, centre on me
const offCentre = () => ev(`(() => { const st = document.querySelector('.stage').getBoundingClientRect(); const sh = document.querySelector('.sheet').getBoundingClientRect(); const u = document.querySelector('#map .me .dot'); if (!u) return 9999; const r = u.getBoundingClientRect(); return Math.hypot(r.x + r.width / 2 - (st.x + st.width / 2), r.y + r.height / 2 - (st.y + (st.height - sh.height) / 2)) })()`)
await tap('Follow me')
await gps(t5[1] + 0.00012, t5[2] + 0.00012, 3)
await sleep(1500)
check('follow on: the map keeps your position in the middle of the part the sheet does not cover', (await offCentre()) < 30, 'distance ' + Math.round(await offCentre()) + ' px')
check('the follow button shows it is on (pressed) and says what it does', (await ev(`document.querySelector('.rbtn[aria-label^="Follow me"]').getAttribute('aria-pressed')`)) === 'true' && (await ev(`document.querySelector('.rbtn[aria-label^="Follow me"]').getAttribute('aria-label')`)) === 'Follow me: on')
const mr = JSON.parse(await ev(`JSON.stringify(document.getElementById('map').getBoundingClientRect())`))
const sheetTop = await ev(`document.querySelector('.sheet').getBoundingClientRect().top`)
const sx = Math.round(mr.x + mr.width * 0.6), sy = Math.round(Math.max(mr.y + 40, sheetTop - 40)) // a spot of the map the sheet does not cover
await b.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: sx, y: sy }] })
for (let i = 1; i <= 10; i++) { await b.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: sx - i * 12, y: sy - i * 3 }] }); await sleep(30) }
await b.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
await sleep(600)
check('dragging the map switches follow off', (await ev(`document.querySelector('.rbtn[aria-label^="Follow me"]').getAttribute('aria-label')`)) === 'Follow me: off')
const afterDrag = await offCentre()
check('the dragged map really moved away from your position', afterDrag > 50, Math.round(afterDrag) + ' px')
await tap('Centre on me')
await sleep(900)
check('"Centre on me" brings your position back to the middle', (await offCentre()) < 30, Math.round(await offCentre()) + ' px')

// ---- 5. no background map: tiles fail, and then the phone says it is offline
b.tileMode = 'fail'
b.tiles.length = 0
await b.send('Page.reload')
await sleep(1500)
await tap('Start')
await sleep(250)
await tap(b0.ref)
await waitExpr(`document.querySelectorAll('#map .treeicon').length === ${b0.n}`)
await tap('Previous step'); await tap('Previous step'); await sleep(300)
await tap('Start GPS')
await gps(ST[0] + 0.0002, ST[1], 8)
await waitExpr(`document.querySelector('.nobase') && !document.querySelector('.nobase').hidden`, 9000)
check('tiles failing: the map says "No background map (no signal)"', await ev(`document.querySelector('.nobase') && !document.querySelector('.nobase').hidden && document.querySelector('.nobase').innerText.includes('No background map (no signal)')`))
await waitFor(/\d+ m/)
check('...and still shows the grid square, the trees and your position', await ev(`document.querySelectorAll('#map .treeicon').length === ${b0.n} && document.querySelectorAll('#map svg path').length >= 3 && !!document.querySelector('#map .me .dot') && !!document.querySelector('.linelabel')`))
await tap('I am at START'); await tap('I put the stake'); await sleep(300)
await tap('Planted')
await sleep(500)
check('...and the page works (a tree can still be marked)', (await ev(`document.querySelector('#map .treeicon.st-planted')`)) !== null)
await noBadText('the block screen with no background map')
await b.shot('map_2_no_tiles')
b.tileMode = 'ok'
check('no uncaught page errors during the whole run', b.events.length === 0, b.events.length ? JSON.stringify(b.events[0].params.exceptionDetails).slice(0, 200) : '')

// ---- 6. the satellite layer exists only when the page was built with --satellite
check('a normal page has no satellite button and mentions no Esri address', !(await ev(`!!document.querySelector('.rbtn[aria-label="Map: standard"], .rbtn[aria-label="Map: satellite"]')`)) && !(await ev('document.documentElement.outerHTML')).includes('arcgisonline'))
if (SAT_PAGE) {
  b.tiles.length = 0
  await b.open(SAT_PAGE)
  await tap('Start')
  await sleep(250)
  await tap(b0.ref)
  await waitExpr(`document.querySelectorAll('#map .treeicon').length === ${b0.n}`)
  const hasButton = await tap('Map: standard')
  await sleep(1200)
  for (let i = 0; i < 5; i++) { await tap('Zoom in'); await sleep(200) }
  await sleep(1000)
  const esri = b.tiles.filter((x) => x.url.includes('server.arcgisonline.com'))
  check('satellite built in: the button switches to Esri World Imagery tiles in {z}/{y}/{x} order, never above level 19', hasButton && esri.length > 0 && esri.every((x) => /\/tile\/(\d+)\/(\d+)\/(\d+)$/.test(x.url) && Number(x.url.match(/\/tile\/(\d+)\//)[1]) <= 19), `${esri.length} Esri tile requests`)
  check('the satellite layer shows its source line', (await ev(`document.querySelector('.attrib')?.innerText`)).includes('Esri'))
  check('the button says which map is on', (await ev(`document.querySelector('.rbtn[aria-label="Map: satellite"]')`)) !== null)
  await b.shot('map_3_satellite')
}
await b.done('map_report')
