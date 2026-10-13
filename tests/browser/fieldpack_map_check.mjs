// Browser check of the field pack MAP (stage A1b): headless Edge at 360 px wide, fake GPS, and ALL map-tile requests intercepted (answered with a small picture, or made to fail),
// so this test never contacts openstreetmap.org or arcgisonline.com. Not run by pytest by default (see tests/test_field_pack_browser.py).
//   node tests/browser/fieldpack_map_check.mjs <address of the pack page, e.g. http://127.0.0.1:8777/x.html> <folder for pictures> [<address of a pack built with --satellite>]
import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const EDGE = process.env.EDGE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const PAGE = process.argv[2]
const OUT = process.argv[3] || tmpdir()
const SAT_PAGE = process.argv[4] || ''
const PORT = 9400 + Math.floor(Math.random() * 400)
const PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
const edge = spawn(EDGE, [`--remote-debugging-port=${PORT}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), 'edge_fp_'))}`, '--headless=new', '--disable-gpu', '--no-first-run', 'about:blank'], { stdio: 'ignore' })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
let tgt
for (let i = 0; i < 60; i++) { try { tgt = (await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()).find((t) => t.type === 'page'); if (tgt) break } catch {} await sleep(300) }
const ws = new WebSocket(tgt.webSocketDebuggerUrl)
await new Promise((r) => (ws.onopen = r))
let id = 0
const pending = new Map()
const events = []
ws.onmessage = (m) => {
  const d = JSON.parse(m.data)
  if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id) } else if (d.method) events.push(d)
  if (d.method === 'Page.javascriptDialogOpening') send('Page.handleJavaScriptDialog', { accept: true })
  if (d.method === 'Fetch.requestPaused') onTile(d.params)
}
const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })) })
const ev = async (expr) => { const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }); if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 300)); return r.result?.result?.value }
const shot = async (n) => writeFileSync(join(OUT, n + '.png'), Buffer.from((await send('Page.captureScreenshot', { format: 'png' })).result.data, 'base64'))
const shotMap = async (n) => { await ev("document.getElementById('map')?.scrollIntoView({ block: 'center' })"); await sleep(250); await shot(n) }
const text = () => ev('document.body.innerText')
const click = (label) => ev(`(() => { const b = [...document.querySelectorAll('button')].find((x) => x.textContent.includes(${JSON.stringify(label)})); if (!b) return false; b.click(); return true })()`)
const fakeGps = (lat, lon, accuracy) => send('Emulation.setGeolocationOverride', { latitude: lat, longitude: lon, accuracy })
const waitFor = async (re, ms = 6000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (re.test(await text())) return true; await sleep(150) } return false }
const waitExpr = async (expr, ms = 6000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (await ev(expr)) return true; await sleep(150) } return false }
const log = []
const check = (name, ok, extra = '') => { log.push({ name, ok: !!ok, extra }); console.log((ok ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : '')) }

// ---- every tile request is caught here: answered with a picture, or failed (mode 'fail')
const tiles = []
let tileMode = 'ok'
function onTile(p) {
  tiles.push({ url: p.request.url, referer: p.request.headers.Referer || p.request.headers.referer || null })
  if (tileMode === 'fail') send('Fetch.failRequest', { requestId: p.requestId, errorReason: 'InternetDisconnected' })
  else send('Fetch.fulfillRequest', { requestId: p.requestId, responseCode: 200, responseHeaders: [{ name: 'Content-Type', value: 'image/png' }], body: PNG })
}
// Words that must never be visible: a JavaScript null / undefined / NaN written into the page, a text key that was not found ("[gpsStart]"), or a value that was not filled in ("{lat}").
const badText = async () => JSON.parse(await ev(`(() => {
  const out = []
  const word = /\\b(null|undefined|NaN)\\b/
  const hole = /\\{[A-Za-z]+\\}|\\[[A-Za-z]+(_[A-Za-z]+)*\\]/
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  let n
  while ((n = w.nextNode())) {
    const p = n.parentElement
    if (!p || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(p.tagName)) continue
    if (word.test(n.textContent) || hole.test(n.textContent)) out.push(n.textContent.trim().slice(0, 50))
  }
  for (const e of document.querySelectorAll('[aria-label], [title]')) {
    const v = (e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('title') || '')
    if (word.test(v) || hole.test(v)) out.push('attribute: ' + v.trim().slice(0, 50))
  }
  return JSON.stringify(out)
})()`))
const noBadText = async (where) => { const bad = await badText(); check(`no "null", "undefined", "NaN" or missing text on ${where}`, bad.length === 0, bad.join(' | ')) }
await send('Page.enable')
await send('Runtime.enable')
await send('Fetch.enable', { patterns: [{ urlPattern: '*tile.openstreetmap.org*' }, { urlPattern: '*server.arcgisonline.com*' }] })
await send('Emulation.setDeviceMetricsOverride', { width: 360, height: 740, deviceScaleFactor: 2, mobile: true })
await send('Emulation.setTouchEmulationEnabled', { enabled: true })
const origin = new URL(PAGE).origin
await send('Browser.grantPermissions', { permissions: ['geolocation'], origin }).catch(() => {})
await send('Page.navigate', { url: PAGE })
await sleep(1500)
await noBadText('the home screen')
const pack = JSON.parse(await ev("document.getElementById('pack-data').textContent"))
const pagePath = new URL(PAGE).pathname

// ---- 1. markers on the map = the coordinates in the page, every tree of every block
let allOk = true, checked = 0, badExample = ''
for (const b of pack.blocks) {
  await click(b.ref)
  await waitExpr(`document.querySelectorAll('#map .treeicon').length === ${b.n}`)
  const got = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('#map .treeicon')].map((e) => [Number(e.dataset.k), Number(e.dataset.lat), Number(e.dataset.lon)]))`))
  const want = b.trees.map((t) => [t[0], t[1], t[2]])
  const same = got.length === want.length && want.every((w, i) => got.some((g) => g[0] === w[0] && g[1] === w[1] && g[2] === w[2]))
  if (!same) { allOk = false; badExample = b.ref }
  checked += got.length
  const paths = await ev(`document.querySelectorAll('#map svg path').length`)
  if (paths < 2) { allOk = false; badExample = b.ref + ' (grid square and planted area not drawn)' }
  await click('Back to all blocks')
  await sleep(150)
}
check(`every tree marker equals the page's coordinates (${checked} trees, ${pack.blocks.length} blocks) and the grid square and planted area are drawn`, allOk && checked === pack.blocks.reduce((s, b) => s + b.n, 0), badExample)

// ---- 2. the tiles: Referer, no path leak, no zoom above the native level
const b0 = pack.blocks[0]
await ev("(() => { const i = document.getElementById('observer'); i.value = 'Map Tester'; i.dispatchEvent(new Event('input', { bubbles: true })) })()")
await click(b0.ref)
await waitExpr(`document.querySelectorAll('#map .treeicon').length === ${b0.n}`)
await sleep(800)
await noBadText('the block screen with the map, before GPS')
for (let i = 0; i < 4; i++) { await click('Zoom in'); await sleep(250) }
await sleep(1200)
const osm = tiles.filter((x) => x.url.includes('tile.openstreetmap.org'))
check('tiles come from the standard OpenStreetMap server and nothing else is requested', osm.length > 0 && tiles.every((x) => x.url.includes('tile.openstreetmap.org')), `${osm.length} tile requests`)
check('every tile request carries a valid Referer, the origin only (not the secret path)', osm.every((x) => x.referer === origin + '/') && osm.every((x) => !x.referer.includes(pagePath.replace(/index\.html$/, '').split('/').filter(Boolean)[0] || '@@')), 'Referer seen: ' + [...new Set(osm.map((x) => x.referer))].join(' , '))
const zs = osm.map((x) => Number(x.url.match(/openstreetmap\.org\/(\d+)\//)[1]))
check('zooming in past the native level asks for tiles of level 19 or lower only (the picture is enlarged)', Math.max(...zs) <= 19 && Math.max(...zs) >= 18, 'levels ' + [...new Set(zs)].sort().join(','))
check('attribution to OpenStreetMap contributors is visible on the map', (await ev(`document.querySelector('.leaflet-control-attribution')?.innerText`)).includes('OpenStreetMap'), '')
check('no sideways scroll at 360 px; our buttons are at least 44 px high', await ev(`document.documentElement.scrollWidth <= document.documentElement.clientWidth && [...document.querySelectorAll('button')].every((b) => b.getBoundingClientRect().height >= 44 || !b.getBoundingClientRect().width)`))

// ---- 3. GPS: position, accuracy circle, line to the target, target selection, arrival
await click('Start GPS')
await noBadText('the block screen just after tapping Start GPS')
const t1 = b0.trees[0], t5 = b0.trees[Math.min(4, b0.n - 1)]
await fakeGps(t1[1] + 0.00036, t1[2], 6) // 40 m north of tree 1
await waitFor(/Distance to the tree/)
await waitExpr(`document.querySelector('.linelabel')`)
const label = await ev(`document.querySelector('.linelabel')?.innerText`)
check('line to the active target with distance and bearing', /about 40 m · S 180°/.test(label || ''), label)
await noBadText('the block screen with a GPS reading and the map line')
check('your position (blue dot) and the accuracy circle are drawn', await ev(`!!document.querySelector('#map svg path[fill="#0033cc"][fill-opacity="1"]') && !!document.querySelector('#map svg path[stroke-dasharray="4 4"]')`))
await shotMap('map_1_far')
await ev(`document.querySelector('#map .treeicon[data-k="${t5[0]}"]').click()`)
await waitFor(new RegExp(`Tree ${t5[0]} of ${b0.n}`))
check('tapping a tree number on the map makes it the target', (await text()).includes(`Tree ${t5[0]} of ${b0.n}`) && (await ev(`document.querySelector('#map .treeicon.st-active')?.dataset.k`)) === String(t5[0]))
await fakeGps(t5[1], t5[2], 3)
await waitFor(/You are at the tree position/)
check('arrival is claimed only inside the reported accuracy', (await text()).includes('You are at the tree position'))
await click('Planted here')
await sleep(600)
check('planted: the marker turns green', (await ev(`document.querySelector('#map .treeicon[data-k="${t5[0]}"]')?.className`)).includes('st-planted'))
await shotMap('map_2_arrived')

// ---- 4. follow and re-centre
const offCentre = () => ev(`(() => { const m = document.getElementById('map').getBoundingClientRect(); const u = document.querySelector('#map svg path[fill="#0033cc"][fill-opacity="1"]'); if (!u) return 9999; const r = u.getBoundingClientRect(); return Math.hypot(r.x + r.width / 2 - (m.x + m.width / 2), r.y + r.height / 2 - (m.y + m.height / 2)) })()`)
await click('Follow me')
await fakeGps(t5[1] + 0.00012, t5[2] + 0.00012, 3)
await sleep(1500)
check('follow on: the map keeps your position in the middle', (await offCentre()) < 30, 'distance from the middle ' + Math.round(await offCentre()) + ' px')
check('the follow button says what it does', (await text()).includes('Follow me: on'))
await ev("document.getElementById('map').scrollIntoView({ block: 'center' })")
await sleep(300)
const mr = JSON.parse(await ev(`JSON.stringify(document.getElementById('map').getBoundingClientRect())`))
const sx = Math.round(mr.x + mr.width * 0.75), sy = Math.round(mr.y + mr.height * 0.5)
await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: sx, y: sy }] })
for (let i = 1; i <= 10; i++) { await send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: sx - i * 15, y: sy - i * 4 }] }); await sleep(30) }
await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
await sleep(600)
check('dragging the map switches follow off', (await text()).includes('Follow me: off'))
const afterDrag = await offCentre()
check('the dragged map really moved away from your position', afterDrag > 60, Math.round(afterDrag) + ' px')
await click('Centre on me')
await sleep(900)
check('"Centre on me" brings your position back to the middle', (await offCentre()) < 30, Math.round(await offCentre()) + ' px')

// ---- 5. no background map: tiles fail (and then the phone says it is offline)
tileMode = 'fail'
tiles.length = 0
await send('Page.reload')
await sleep(1500)
await click(b0.ref)
await waitExpr(`document.querySelectorAll('#map .treeicon').length === ${b0.n}`)
await click('Start GPS')
await fakeGps(t1[1] + 0.0002, t1[2], 8)
await waitExpr(`document.querySelector('.nobase') && !document.querySelector('.nobase').hidden`, 8000)
check('tiles failing: the map says "No background map (no signal)"', await ev(`document.querySelector('.nobase') && !document.querySelector('.nobase').hidden && document.querySelector('.nobase').innerText.includes('No background map (no signal)')`))
await waitFor(/Distance to the tree/)
check('...and still shows the grid square, the trees and your position', await ev(`document.querySelectorAll('#map .treeicon').length === ${b0.n} && document.querySelectorAll('#map svg path').length >= 3 && !!document.querySelector('.linelabel')`))
check('...and the page works (a tree can still be marked)', await (async () => { await click('Planted here'); await sleep(300); return (await ev(`document.querySelector('#map .treeicon.st-planted')`)) !== null })())
await shotMap('map_3_no_tiles')
tileMode = 'ok'
await send('Network.enable')
await send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 })
await sleep(500)
await send('Page.reload').catch(() => {})
await sleep(1500)
await send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 })
const errs = events.filter((e) => e.method === 'Runtime.exceptionThrown')
check('no uncaught page errors during the whole run', errs.length === 0, errs.length ? JSON.stringify(errs[0].params.exceptionDetails).slice(0, 200) : '')

// ---- 6. the satellite layer exists only when the page was built with --satellite
check('a normal page has no satellite button and mentions no Esri address', !(await text()).includes('Map: satellite') && !(await ev('document.documentElement.outerHTML')).includes('arcgisonline'))
if (SAT_PAGE) {
  tiles.length = 0
  await send('Page.navigate', { url: SAT_PAGE })
  await sleep(1500)
  await click(b0.ref)
  await waitExpr(`document.querySelectorAll('#map .treeicon').length === ${b0.n}`)
  const hasButton = await click('Map: standard')
  await sleep(1200)
  for (let i = 0; i < 4; i++) { await click('Zoom in'); await sleep(200) }
  await sleep(1000)
  const esri = tiles.filter((x) => x.url.includes('server.arcgisonline.com'))
  check('satellite built in: the button switches to Esri World Imagery tiles in {z}/{y}/{x} order, never above level 19', hasButton && esri.length > 0 && esri.every((x) => /\/tile\/(\d+)\/(\d+)\/(\d+)$/.test(x.url) && Number(x.url.match(/\/tile\/(\d+)\//)[1]) <= 19), `${esri.length} Esri tile requests`)
  check('the satellite layer shows its source line', (await ev(`document.querySelector('.leaflet-control-attribution')?.innerText`)).includes('Esri'))
  await shotMap('map_4_satellite')
}
writeFileSync(join(OUT, 'map_report.json'), JSON.stringify({ page: PAGE, log }, null, 1))
console.log(`\n${log.filter((l) => l.ok).length} passed, ${log.filter((l) => !l.ok).length} failed`)
ws.close(); spawn('taskkill', ['/PID', String(edge.pid), '/T', '/F'], { stdio: 'ignore' })
await sleep(500)
process.exit(log.some((l) => !l.ok) ? 1 : 0)
