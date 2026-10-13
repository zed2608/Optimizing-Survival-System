// Heading, rotation, relative cue and wake lock of the field pack in headless Edge at 360 x 640 and 390 x 844. Orientation events are SIMULATED (Android: deviceorientationabsolute with alpha / beta / gamma;
// iOS: webkitCompassHeading after a stubbed DeviceOrientationEvent.requestPermission); the GPS is fake; the Screen Wake Lock is a stub that counts calls. No map server is contacted.
// A real phone's compass, the real iOS permission dialog and a real wake lock are NOT tested here.
//   node tests/browser/fieldpack_heading_check.mjs <address of the pack page> <folder for pictures>
import { launch } from './cdp_lib.mjs'

const PAGE = process.argv[2]
const b = await launch({ out: process.argv[3] })
const { ev, text, tap, check, sleep, waitFor, waitExpr, gps, noBadText } = b
const away = (a, c) => Math.abs((((c - a) % 360) + 540) % 360 - 180)
const cone = async () => { const r = await ev(`(() => { const c = document.querySelector('.cone'); return c ? JSON.stringify({ hdg: parseFloat(c.dataset.hdg), half: parseFloat(c.dataset.half), src: c.dataset.source, shown: c.style.display !== 'none' }) : null })()`); return r ? JSON.parse(r) : null }
const cue = () => ev(`(() => { const c = document.querySelector('.cue'); return c && !c.hidden ? c.textContent : '' })()`)
const settle = async (deg, n = 30) => { for (let i = 0; i < n; i++) { await b.androidHeading((360 - deg) % 360); await sleep(20) } await sleep(120) }
const net = (sel) => ev(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); if (!el) return null; let a = 0; for (let e = el; e && e.nodeType === 1; e = e.parentElement) { const tr = getComputedStyle(e).transform; if (tr && tr !== 'none') { const m = new DOMMatrixReadOnly(tr); a += Math.atan2(m.b, m.a) * 180 / Math.PI } } return ((a % 360) + 540) % 360 - 180 })()`)
const WAKE_MISSING = "Object.defineProperty(navigator, 'wakeLock', { value: undefined, configurable: true })"
const WAKE_STUB = "window.__wl = { req: 0, rel: 0, on: [] }; Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: { request: async () => { window.__wl.req++; return { release: async () => { window.__wl.rel++ }, addEventListener: (t, f) => window.__wl.on.push(f) } } } })"
const IOS_GRANT = "window.__perm = 0; DeviceOrientationEvent.requestPermission = async () => { window.__perm++; return 'granted' }"
const IOS_DENY = "window.__perm = 0; DeviceOrientationEvent.requestPermission = async () => { window.__perm++; return 'denied' }"

async function fresh(url, script) {
  const ids = []
  if (script) ids.push((await b.addScript(script)).result.identifier)
  await b.open(url)
  await ev('sessionStorage.clear(); localStorage.clear()')
  await b.open(url)
  return ids
}
const unscript = (ids) => Promise.all(ids.map((identifier) => b.send('Page.removeScriptToEvaluateOnNewDocument', { identifier })))

for (const [W, H] of [[360, 640], [390, 844]]) {
  const tag = `${W}x${H}: `
  await b.viewport(W, H)

  // ======== A. no wake lock in this browser, no heading at all, then the Android compass
  let ids = await fresh(PAGE, WAKE_MISSING)
  const pack = JSON.parse(await ev("document.getElementById('pack-data').textContent"))
  const blk = pack.blocks[0], t1 = blk.trees[0]
  await tap(blk.ref)
  await waitExpr(`document.querySelectorAll('#map .treeicon').length === ${blk.n}`)
  await tap('Start GPS')
  await gps(t1[1] + 0.00036, t1[2], 6) // 40 m north of tree 1: the tree is due south (bearing 180)
  await waitFor(/about 40 m/)
  check(tag + 'no Screen Wake Lock in the browser: nothing breaks (no error)', b.events.length === 0 && (await text()).includes('about 40 m'))
  check(tag + 'no heading yet: the cone is hidden, no turn cue, and the page says "Heading not available"', (await cone())?.shown === false && (await cue()) === '' && (await ev(`document.querySelector('.sheet').textContent`)).includes('Heading not available'))
  await tap('Map: north up')
  await sleep(300)
  check(tag + 'turning the map to heading-up without a heading is refused with a plain message, the map stays north up', (await text()).includes('Heading not available yet') && (await ev(`document.getElementById('maprot').dataset.rot === undefined`)))
  await noBadText(tag + 'the block screen with no heading')

  await settle(0)
  let c = await cone()
  check(tag + 'compass (Android deviceorientationabsolute): the cone shows, pointing at the heading (0°)', c && c.shown && c.src === 'compass' && away(c.hdg, 0) <= 3, JSON.stringify(c))
  check(tag + 'compass cone is the wide one (28°) when the compass is steady', c && c.half === 28)
  check(tag + 'relative cue, target due south while facing north: "Turn around"', (await cue()) === 'Turn around', await cue())
  await settle(180)
  c = await cone()
  check(tag + 'the cone turned with the heading (180°)', c && away(c.hdg, 180) <= 3, JSON.stringify(c))
  check(tag + 'relative cue, facing the target: "Straight ahead"', (await cue()) === 'Straight ahead', await cue())
  await settle(90)
  check(tag + 'relative cue, target 90° to the right: "Turn right 90°"', (await cue()) === 'Turn right 90°', await cue())
  await settle(270)
  check(tag + 'relative cue, target 90° to the left: "Turn left 90°"', (await cue()) === 'Turn left 90°', await cue())
  await settle(210)
  check(tag + 'relative cue, 30° off to the left: "Turn left 30°"', (await cue()) === 'Turn left 30°', await cue())
  await settle(150)
  check(tag + 'relative cue, 30° off to the right: "Turn right 30°"', (await cue()) === 'Turn right 30°', await cue())

  // wrap-around: 355 -> 359 -> 1 -> 7 must go through north, never the long way round
  await settle(355, 40)
  const seen = []
  for (const raw of [357, 359, 1, 3, 5, 7]) for (let i = 0; i < 6; i++) { await b.androidHeading((360 - raw) % 360); await sleep(40); seen.push((await cone()).hdg) }
  let maxStep = 0
  for (let i = 1; i < seen.length; i++) maxStep = Math.max(maxStep, away(seen[i - 1], seen[i]))
  check(tag + 'heading across north (359 to 1) does not spin: biggest step ' + maxStep.toFixed(1) + '°, always within 25° of north', maxStep < 10 && seen.every((x) => away(x, 0) < 25), seen.map((x) => x.toFixed(0)).join(' '))
  // an unsteady compass gives a wider cone
  for (const raw of [0, 50, 330, 80, 290, 20, 340, 70, 300, 30, 350, 60]) { await b.androidHeading((360 - raw) % 360); await sleep(25) }
  await sleep(150)
  c = await cone()
  check(tag + 'an unsteady compass widens the cone (50°)', c && c.half === 50, JSON.stringify(c))
  await settle(0, 40)
  await sleep(3200) // the compass goes quiet: after a few seconds the page lets go of it
  c = await cone()
  check(tag + 'a compass that goes quiet is dropped (no stale arrow)', c && c.shown === false, JSON.stringify(c))
  // GPS heading while walking (about 1 m/s or faster), narrower cone
  await gps(t1[1] + 0.00037, t1[2], 5, { heading: 45, speed: 2.0 })
  await waitExpr(`document.querySelector('.cone') && document.querySelector('.cone').dataset.source === 'gps'`, 5000)
  c = await cone()
  check(tag + 'GPS heading while walking: the cone points at it (45°) and is narrower than the compass cone (12°)', c && c.src === 'gps' && away(c.hdg, 45) <= 3 && c.half === 12, JSON.stringify(c))
  await tap('Details')
  check(tag + 'Details name the heading source and give the figure-8 hint for the compass', (await ev(`document.querySelector('.sheet').innerText`)).includes('Heading: GPS, while you walk'))
  await tap('Details')
  await gps(t1[1] + 0.00036, t1[2], 5, { heading: 45, speed: 0.3 }) // too slow for a GPS heading
  await sleep(6500)
  check(tag + 'GPS heading at walking pace below 1 m/s is not used', (await cone())?.shown === false)

  // ======== rotation: heading-up turns the map, the markers stay upright, the cone points up
  await settle(90)
  await tap('Map: north up')
  await sleep(500)
  const rot = parseFloat(await ev(`document.getElementById('maprot').dataset.rot`))
  check(tag + 'heading-up: the map is turned by minus the heading (-90°)', Math.abs(rot + 90) <= 3, String(rot))
  check(tag + 'heading-up: the button says so (pressed) and follow is switched on', (await ev(`document.querySelector('.rbtn[aria-label^="Map: heading up"]')?.getAttribute('aria-pressed')`)) === 'true' && (await ev(`document.querySelector('.rbtn[aria-label^="Follow me"]').getAttribute('aria-label')`)) === 'Follow me: on')
  const nets = { tree: await net('#map .treeicon'), label: await net('.linelabel'), cone: await net('.cone') }
  check(tag + 'heading-up: tree numbers, the distance label and the cone stay upright on the screen (net turn 0°)', Object.values(nets).every((x) => x !== null && Math.abs(x) < 2), JSON.stringify(nets))
  await settle(200)
  check(tag + 'heading-up: the map follows a changing heading (200° gives -200°)', Math.abs(parseFloat(await ev(`document.getElementById('maprot').dataset.rot`)) + 200) <= 3)
  const covered = await ev(`(() => { const st = document.querySelector('.stage').getBoundingClientRect(); const pts = [[4, st.y + 4], [st.x + st.width / 2, st.y + 4], [4, st.y + 60], [14, st.y + (st.height - document.querySelector('.sheet').getBoundingClientRect().height) - 6]]; return pts.every(([x, y]) => { const e = document.elementFromPoint(x, y); return e && e.closest('#maprot') }) })()`)
  check(tag + 'heading-up: the turned map still covers the whole screen (no empty corners)', covered)
  check(tag + 'heading-up: no sideways scroll, no page scroll', await ev('document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight + 1'))
  await noBadText(tag + 'the block screen in heading-up mode')
  await b.shot(`head_${W}_1_rotated`)
  await tap('Map: heading up')
  await sleep(400)
  check(tag + 'back to north-up: the map is not turned any more and fills the stage', (await ev(`document.getElementById('maprot').dataset.rot === undefined`)) && (await ev(`Math.abs(document.getElementById('maprot').getBoundingClientRect().width - document.querySelector('.stage').getBoundingClientRect().width) < 2`)))
  await unscript(ids)

  // ======== B. a stubbed Screen Wake Lock
  ids = await fresh(PAGE, WAKE_STUB)
  await tap(blk.ref)
  await waitExpr(`document.querySelectorAll('.chip').length === ${blk.n}`)
  check(tag + 'wake lock: not asked for before the Start button', (await ev('window.__wl.req')) === 0)
  await tap('Start GPS')
  await sleep(500)
  check(tag + 'wake lock: asked for after the Start button', (await ev('window.__wl.req')) >= 1)
  await ev('window.__wl.on.forEach((f) => f())') // the browser released it (screen off, app switched)
  await ev(`document.dispatchEvent(new Event('visibilitychange'))`)
  await sleep(400)
  check(tag + 'wake lock: asked for again when the page becomes visible again', (await ev('window.__wl.req')) >= 2, 'requests ' + (await ev('window.__wl.req')))
  await tap('Back')
  await sleep(400)
  check(tag + 'wake lock: released when the block screen is left', (await ev('window.__wl.rel')) >= 1)
  await unscript(ids)

  // ======== C. iOS: the compass permission is asked inside the tap on Start; webkitCompassHeading
  ids = await fresh(PAGE, IOS_GRANT)
  await tap(blk.ref)
  await waitExpr(`document.querySelectorAll('.chip').length === ${blk.n}`)
  check(tag + 'iOS: the compass permission is not asked before the tap', (await ev('window.__perm')) === 0)
  await tap('Start GPS')
  await gps(t1[1] + 0.00036, t1[2], 6)
  await waitFor(/about 40 m/)
  check(tag + 'iOS: the compass permission is asked once, inside the tap on Start GPS', (await ev('window.__perm')) === 1)
  for (let i = 0; i < 30; i++) { await b.iosHeading(120); await sleep(20) }
  await sleep(150)
  c = await cone()
  check(tag + 'iOS (webkitCompassHeading): the cone points at the heading (120°)', c && c.shown && c.src === 'compass' && away(c.hdg, 120) <= 3, JSON.stringify(c))
  check(tag + 'iOS: relative cue from webkitCompassHeading (target due south, facing 120°): "Turn right 60°"', (await cue()) === 'Turn right 60°', await cue())
  for (const raw of [350, 355, 359, 2, 6]) { for (let i = 0; i < 6; i++) { await b.iosHeading(raw); await sleep(20) } }
  await unscript(ids)
  ids = await fresh(PAGE, IOS_DENY)
  await tap(blk.ref)
  await waitExpr(`document.querySelectorAll('.chip').length === ${blk.n}`)
  await tap('Start GPS')
  await gps(t1[1] + 0.00036, t1[2], 6)
  await waitFor(/about 40 m/)
  await tap('Details')
  check(tag + 'iOS permission refused: a plain message, no cone, the page keeps working', (await ev(`document.querySelector('.sheet').innerText`)).includes('Compass permission was refused.') && (await cone())?.shown === false)
  await noBadText(tag + 'the block screen after the compass permission was refused')
  await unscript(ids)
}
check('no uncaught page errors during the whole run', b.events.length === 0, b.events.length ? JSON.stringify(b.events[0].params.exceptionDetails).slice(0, 200) : '')
await b.done('heading_report')
