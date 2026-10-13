// Browser check of the field pack (Stage A1): headless Edge at 360 px wide with a FAKE GPS (CDP geolocation override). Not run by pytest.
//   node tests/browser/fieldpack_check.mjs <page.html or http://... address> <folder for pictures>
// It walks the whole flow: pick a block, start GPS, see distance / bearing / accuracy, "arrived", mark planted, skip with a reason, reload (the marks stay), export the results file.
// It says whether GPS worked for the way the page was opened (file or http address): this is a DESKTOP browser, so it is only a hint for phones, not a phone test.
import { spawn } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const EDGE = process.env.EDGE || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const target = process.argv[2]
const OUT = process.argv[3] || tmpdir()
const URL_ = /^https?:/.test(target) ? target : pathToFileURL(resolve(target)).href
const PORT = 9400 + Math.floor(Math.random() * 400)
const edge = spawn(EDGE, [`--remote-debugging-port=${PORT}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), 'edge_fp_'))}`, '--headless=new', '--disable-gpu', '--no-first-run', 'about:blank'], { stdio: 'ignore' })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
let tgt
for (let i = 0; i < 60; i++) { try { tgt = (await (await fetch(`http://127.0.0.1:${PORT}/json`)).json()).find((t) => t.type === 'page'); if (tgt) break } catch {} await sleep(300) }
const ws = new WebSocket(tgt.webSocketDebuggerUrl)
await new Promise((r) => (ws.onopen = r))
let id = 0
const pending = new Map()
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id) } }
const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })) })
const ev = async (expr) => { const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }); if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400)); return r.result?.result?.value }
const shot = async (n) => writeFileSync(join(OUT, n + '.png'), Buffer.from((await send('Page.captureScreenshot', { format: 'png' })).result.data, 'base64'))
const text = () => ev('document.body.innerText')
const click = (label) => ev(`(() => { const b = [...document.querySelectorAll('button')].find((x) => x.textContent.includes(${JSON.stringify(label)})); if (!b) return false; b.click(); return true })()`)
const fakeGps = (lat, lon, accuracy) => send('Emulation.setGeolocationOverride', { latitude: lat, longitude: lon, accuracy })
const waitFor = async (re, ms = 6000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (re.test(await text())) return true; await sleep(150) } return false }
const log = []
const check = (name, ok, extra = '') => { log.push({ name, ok: !!ok, extra }); console.log((ok ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : '')) }

await send('Page.enable')
await send('Network.enable')
await send('Network.setBlockedURLs', { urls: ['*tile.openstreetmap.org*', '*arcgisonline.com*'] }) // this check never contacts a tile server (the map has its own check)
await send('Emulation.setDeviceMetricsOverride', { width: 360, height: 740, deviceScaleFactor: 2, mobile: true })
await send('Emulation.setTouchEmulationEnabled', { enabled: true })
const origin = URL_.startsWith('file:') ? 'file://' : new globalThis.URL(URL_).origin
await send('Browser.grantPermissions', { permissions: ['geolocation'], origin }).catch(() => {})
await send('Page.navigate', { url: URL_ })
await sleep(1500)

const pack = JSON.parse(await ev("document.getElementById('pack-data').textContent"))
const b = pack.blocks[0]
const t1 = b.trees[0]
check('page opens and shows the banner', (await text()).includes('Prototype. GPS accuracy not yet field-tested.'))
check('secure context (needed for GPS)', true, 'isSecureContext=' + (await ev('window.isSecureContext')) + ' protocol=' + (await ev('location.protocol')))
const layout = await ev(`JSON.stringify({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, small: [...document.querySelectorAll('button, input')].filter((e) => { const r = e.getBoundingClientRect(); return r.width && (r.height < 44 || r.width < 44) }).length, minFont: Math.min(...[...document.querySelectorAll('#app *, #banner')].filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())).map((e) => parseFloat(getComputedStyle(e).fontSize))) })`)
const L = JSON.parse(layout)
check('home: no sideways scroll at 360 px', L.sw <= L.cw, layout)
check('home: tap targets at least 44 px, text at least 16 px', L.small === 0 && L.minFont >= 16)
await shot('fp_1_home')

await ev("(() => { const i = document.getElementById('observer'); i.value = 'Test Planter'; i.dispatchEvent(new Event('input', { bubbles: true })) })()")
await click(b.ref)
await sleep(300)
check('block screen lists trees 1..N and the START corner', (await text()).includes('START corner') && (await ev(`document.querySelectorAll('.tree').length`)) === b.n)
await shot('fp_2_block_before_gps')

await click('Start GPS')
await fakeGps(t1[1] + 0.00036, t1[2], 6) // about 40 m north of tree 1, accuracy 6 m
await waitFor(/Distance to the tree/)
let txt = await text()
const gpsWorked = /Distance to the tree/.test(txt)
check('GPS reading arrives and distance / direction / accuracy are shown', gpsWorked, gpsWorked ? txt.match(/Distance to the tree: [^\n]+/)[0] + ' | ' + txt.match(/Direction: [^\n]+/)[0] + ' | ' + txt.match(/Phone GPS accuracy[^\n]*/)[0] : txt.match(/(This page|GPS only|Location|The phone|No GPS)[^\n]*/)?.[0])
if (gpsWorked) {
  check('direction is south (target is south of the phone)', /Direction: S \(1[6-9]\d°/.test(txt))
  check('far away: not "arrived"', !txt.includes('You are at the tree position'))
  check('no compass: only degrees and letters, and it says so', txt.includes('No compass heading'))
  await shot('fp_3_gps_far')
  await fakeGps(t1[1], t1[2], 12) // right on the tree but accuracy 12 m (worse than a 7 m spacing for some species)
  await waitFor(/You are at the tree position/)
  txt = await text()
  check('on the point: arrived is claimed only within the reported accuracy', txt.includes('You are at the tree position'))
  check('accuracy worse than the spacing: says the point is only approximate', b.spacing_m < 12 ? txt.includes('only approximate') : true, 'spacing ' + b.spacing_m)
  await shot('fp_4_gps_arrived')
  await click('Planted here')
  await sleep(500)
  txt = await text()
  check('planted: the next tree becomes the target', txt.includes(`Tree 2 of ${b.n}`))
  await click('Skip this tree')
  await sleep(300)
  check('skip offers the README reasons', (await text()).includes('Rock or ledge') && (await text()).includes('Owner refused'))
  await click('Rock or ledge')
  await sleep(500)
  check('skipped: tree 3 is next and progress says 1 planted 1 skipped', (await text()).includes(`Tree 3 of ${b.n}`) && /1 planted, 1 skipped/.test(await text()))
  await shot('fp_5_after_marks')
}
await send('Page.reload')
await sleep(1500)
await click(b.ref)
await sleep(300)
if (gpsWorked) check('after reload the marks are still there (saved on the phone)', /1 planted, 1 skipped/.test(await text()))
await click('Back to all blocks')
await sleep(300)
await ev("window.__blobs = []; const o = URL.createObjectURL.bind(URL); URL.createObjectURL = (x) => { window.__blobs.push(x); return o(x) }")
await click('Save results file')
await sleep(500)
const csv = await ev('window.__blobs[0] ? window.__blobs[0].text() : null')
if (csv) {
  const lines = csv.replace(/^\uFEFF/, '').trim().split(/\r?\n/)
  check('results file has the blocks.csv columns first, one row per block', lines.length === pack.blocks.length + 1 && lines[0].startsWith(pack.columns.join(',')))
  const parse = (line) => { const out = []; let cur = '', q = false; for (let i = 0; i < line.length; i++) { const c = line[i]; if (q) { if (c === '"' && line[i + 1] === '"') { cur += '"'; i++ } else if (c === '"') q = false; else cur += c } else if (c === '"') q = true; else if (c === ',') { out.push(cur); cur = '' } else cur += c } out.push(cur); return out }
  const r1 = parse(lines[1])
  if (gpsWorked) check('results file: block 1 is planted with 1 tree (partly done), by the name typed', r1[pack.columns.indexOf('status')] === 'planted' && r1[pack.columns.indexOf('trees_planted')] === '1' && r1[pack.columns.length + 2] === 'Test Planter', r1.slice(pack.columns.indexOf('status'), pack.columns.indexOf('status') + 2).join('|') + ' observer=' + r1[pack.columns.length + 2])
  writeFileSync(join(OUT, 'fp_results.csv'), csv)
} else check('results file was made', false)
await shot('fp_6_home_after')

writeFileSync(join(OUT, 'fp_report.json'), JSON.stringify({ page: URL_, gpsWorked, log }, null, 1))
console.log(`\n${log.filter((l) => l.ok).length} passed, ${log.filter((l) => !l.ok).length} failed; GPS worked on this way of opening the page: ${gpsWorked}`)
ws.close(); spawn('taskkill', ['/PID', String(edge.pid), '/T', '/F'], { stdio: 'ignore' })
await sleep(500)
process.exit(log.some((l) => !l.ok) ? 1 : 0)
