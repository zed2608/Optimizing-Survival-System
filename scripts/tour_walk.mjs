// Walks EVERY guided tour (R1 W3) in headless Edge through the DevTools protocol of tests/browser/cdp_lib.mjs, in light and dark, at 360 and 1280 px, and checks every step:
//   - its target (data-tour id) exists, is visible and lies fully inside the viewport (a target taller than the screen may fill it);
//   - the popover is inside the viewport and does not overlap the target;
//   - the page shown is the tour's page (the Weather tour never shows a Studio target);
//   - no step is skipped (window.__tourSkipped stays empty) - an `optional` step may be absent;
//   - after the tour the saved selections are back (the sidebar summaries, the active page, the planting dates) and no network WRITE happened (a POST / PUT / DELETE to anything but the read-only
//     computations listed in READ_ONLY_POSTS).
//   node scripts/tour_walk.mjs [--base http://127.0.0.1:8001] [--themes light,dark] [--widths 360,1280] [--tours id,id] [--shots reports/overnight/r1_shots/tours] [--no-shots]
// Pictures: <shots>/<page>/<tourId>_<section>_NN_<theme><width>.png (light 1280 and dark 360 by default). Exit code 1 when anything fails.
import { mkdirSync } from 'node:fs'
import { launch, sleep } from '../tests/browser/cdp_lib.mjs'

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d }
const BASE = arg('--base', 'http://127.0.0.1:8001')
const THEMES = arg('--themes', 'light,dark').split(',')
const WIDTHS = arg('--widths', '360,1280').split(',').map(Number)
const ONLY = arg('--tours', '') ? arg('--tours', '').split(',') : null
const SHOTS = process.argv.includes('--no-shots') ? null : arg('--shots', 'reports/overnight/r1_shots/tours')
const READ_ONLY_POSTS = [/\/rank\/area/, /\/areas\/rank/, /\/plan-event\/preview/, /\/companions/, /\/search\//, /\/squares\//, /\/grid\/diagnostic/]
const PAGE_TAB = { studio: 0, weather: 1, history: 2, analytics: 3 }

const b = await launch({ out: SHOTS ?? '.' })
const { ev, send } = b
const fails = []
const fail = (m) => { fails.push(m); console.log('FAIL', m) }
const results = []

await send('Page.addScriptToEvaluateOnNewDocument', { source: `(() => { window.__net = []; const f = window.fetch; window.fetch = function (u, o) { try { window.__net.push([((o && o.method) || 'GET').toUpperCase(), String(typeof u === 'string' ? u : u.url)]) } catch (e) {} return f.apply(this, arguments) } })()` })

const summary = () => ev(`(() => JSON.stringify({ tab: document.querySelector('[role=tab][aria-selected=true].cy-tab')?.innerText?.trim() ?? '', steps: [...document.querySelectorAll('.nw-step')].map((s) => (s.dataset.step || '') + ':' + (s.classList.contains('is-open') ? 'open' : (s.querySelector('.nw-step-sum')?.textContent || ''))), start: document.getElementById('nw-start')?.value ?? '', end: document.getElementById('nw-end')?.value ?? '', sidebar: !!document.querySelector('.nw-sidebar') }))()`)

async function gotoPage(page) {
  const i = PAGE_TAB[page] ?? 0
  await ev(`document.querySelectorAll('[role=tab].cy-tab')[${i}]?.click()`)
  await sleep(page === 'studio' ? 400 : 2500)
}

async function walk(theme, w, tour, section) {
  const name = `${tour.id}${section ? '/' + section : ''}`
  const tag = `${theme}/${w}/${name}`
  const steps = (section ? tour.sections.find((s) => s.id === section) : { steps: tour.sections.flatMap((s) => s.steps) }).steps
  await b.open(`${BASE}/#/new`); await b.viewport(w, w <= 500 ? 740 : 800)
  await ev(`localStorage.setItem('nw_last_visit', String(Date.now())); localStorage.setItem('nw_lang','en'); localStorage.setItem('nw_theme','${theme}'); localStorage.setItem('nw_tour_done','1'); localStorage.setItem('nw_help_banner_off','1'); localStorage.setItem('nw_hints','1')`)
  await ev('location.reload()'); await sleep(3500)
  const page = tour.page === 'any' ? 'studio' : tour.page
  if (page !== 'help') await gotoPage(page)
  const before = await summary()
  await ev('window.__net = []')
  await ev(`window.__tours.start(${JSON.stringify(tour.id)}, ${JSON.stringify(section ?? undefined)})`)
  let n = 0
  const seen = []
  for (let guard = 0; guard < steps.length + 4; guard++) {
    // wait for a step to be on screen
    let st = null
    for (let k = 0; k < 60; k++) { st = await ev(`(() => { const r = document.querySelector('[data-role=tour]'); if (!r) return null; return JSON.stringify({ step: r.dataset.step, target: r.dataset.target, placement: r.dataset.placement }) })()`); if (st) break; await sleep(100) }
    if (!st) break
    const s = JSON.parse(st)
    n += 1
    seen.push(s.step)
    const g = JSON.parse(await ev(`(() => {
      const t = '${s.target}' ? [...document.querySelectorAll('[data-tour="${s.target}"]')].find((e) => { const r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2 }) : null
      const pop = document.querySelector('.tr-pop').getBoundingClientRect()
      const out = { hasTarget: !!t, vw: innerWidth, vh: innerHeight, pop: [pop.left, pop.top, pop.right, pop.bottom] }
      if (t) { const r = t.getBoundingClientRect(); out.rect = [r.left, r.top, r.right, r.bottom]; out.inside = r.left >= -1 && r.top >= -1 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1; out.fills = r.height >= innerHeight - 20 || r.width >= innerWidth - 20 }
      const tab = document.querySelector('[role=tab][aria-selected=true].cy-tab')?.innerText?.trim() ?? ''
      out.tab = tab
      out.studioTarget = !!document.querySelector('.nw-sidebar') && ${JSON.stringify(tour.page)} !== 'studio'
      return JSON.stringify(out) })()`))
    const label = `${tag} step ${n} (${s.step})`
    if (s.target && !g.hasTarget) fail(`${label}: target ${s.target} is not on screen`)
    if (g.hasTarget && !g.inside && !g.fills) fail(`${label}: target ${s.target} is not fully inside the viewport ${JSON.stringify(g.rect)}`)
    const [pl, pt, pr, pb] = g.pop
    if (pl < -1 || pt < -1 || pr > g.vw + 1 || pb > g.vh + 1) fail(`${label}: popover leaves the screen ${JSON.stringify(g.pop)}`)
    if (g.rect && !(pr <= g.rect[0] || pl >= g.rect[2] || pb <= g.rect[1] || pt >= g.rect[3])) fail(`${label}: popover overlaps its target ${JSON.stringify([g.pop, g.rect])}`)
    if (tour.page !== 'any' && tour.page !== 'help' && PAGE_TAB[tour.page] !== undefined) {
      const want = ['Active Studio', 'Weather', 'Campaign Logs', 'System Analytics'][PAGE_TAB[tour.page]]
      const have = await ev(`document.querySelector('[role=tab][aria-selected=true].cy-tab')?.getAttribute('aria-label') || document.querySelector('[role=tab][aria-selected=true].cy-tab')?.innerText || ''`)
      if (have && !String(have).includes(want.split(' ')[0]) && !String(have).includes(want)) fail(`${label}: the page shown is "${have}", the tour is for ${want}`)
    }
    if (SHOTS && ((theme === 'light' && w === 1280) || (theme === 'dark' && w === 360))) {
      const dir = `${SHOTS}/${tour.page}`
      mkdirSync(dir, { recursive: true })
      const f = `${tour.id}${section ? '_' + section : ''}_${String(n).padStart(2, '0')}_${theme}${w}`
      await b.shot(`${tour.page}/${f}`).catch(() => {})
    }
    await ev(`document.querySelector('[data-tour-primary]').click()`)
    await sleep(350)
  }
  await sleep(500)
  const left = await ev(`!!document.querySelector('[data-role=tour]')`)
  if (left) fail(`${tag}: the tour did not end after ${n} steps`)
  const skipped = await ev('JSON.stringify(window.__tourSkipped || [])')
  const last = await ev('JSON.stringify(window.__tourLast || null)')
  const sk = JSON.parse(skipped)
  const lastInfo = JSON.parse(last)
  const sk2 = (lastInfo?.skipped ?? sk)
  for (const x of sk2) fail(`${tag}: step skipped, its target was not on screen: ${x}`)
  const expect = steps.length
  const optionalMissing = steps.filter((x) => x.optional).length
  if (n < expect - optionalMissing) fail(`${tag}: only ${n} of ${expect} steps were shown`)
  // state safety
  await gotoPage(page)
  const after = await summary()
  const a = JSON.parse(after)
  const bf = JSON.parse(before)
  if (a.tab !== bf.tab || a.start !== bf.start || a.end !== bf.end || JSON.stringify(a.steps) !== JSON.stringify(bf.steps)) fail(`${tag}: the selections were not restored: ${JSON.stringify(bf)} -> ${JSON.stringify(a)}`)
  const writes = JSON.parse(await ev('JSON.stringify(window.__net || [])')).filter(([m, u]) => m !== 'GET' && !READ_ONLY_POSTS.some((r) => r.test(u)))
  if (writes.length) fail(`${tag}: a network write happened during the tour: ${JSON.stringify(writes)}`)
  results.push({ tag, steps: n })
}

await b.open(`${BASE}/#/new`)
await ev(`localStorage.setItem('nw_last_visit', String(Date.now())); localStorage.setItem('nw_tour_done','1'); localStorage.setItem('nw_help_banner_off','1')`)
await ev('location.reload()'); await sleep(3500)
const list = JSON.parse(await ev('JSON.stringify(window.__tours.list())'))
for (const theme of THEMES) {
  for (const w of WIDTHS) {
    for (const tour of list) {
      if (ONLY && !ONLY.includes(tour.id)) continue
      await walk(theme, w, tour, null)
    }
  }
}
const total = results.reduce((a, r) => a + r.steps, 0)
console.log(`${results.length} tour runs, ${total} steps shown, ${fails.length} failures`)
for (const t of list) console.log(`  ${t.id} (${t.page}): ${t.sections.reduce((a, s) => a + s.steps.length, 0)} steps in ${t.sections.length} sections`)
b.log.push({ name: 'every tour step has its target, a clean popover and restores the page', ok: fails.length === 0, extra: '' })
await b.done('tour_walk')
