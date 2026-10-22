// R1 FINAL QA: the demo route on the BUILT app in a real browser: landing -> Studio -> "I have species" -> pick a species -> one point with Detailed -> create plan -> Field kit -> Weather -> Analytics.
// Asserts: every step reached, no console error, no failed request (a fetch that answers 4xx/5xx or throws; the map tiles are faked by cdp_lib).
//   node scripts/demo_route_check.mjs [base] [width] [height]      (it SAVES one plan in the server it is pointed at: use the demo/phone-test server)
import { mkdirSync } from 'node:fs'
import { launch, sleep } from '../tests/browser/cdp_lib.mjs'
mkdirSync('reports/overnight/r1_shots/demo', { recursive: true })
const BASE = process.argv[2] || 'http://127.0.0.1:8001'
const w = Number(process.argv[3] || 1280), hgt = Number(process.argv[4] || 800)
const b = await launch({ out: 'reports/overnight/r1_shots/demo' })
const { ev, send } = b
await send('Page.addScriptToEvaluateOnNewDocument', { source: `(() => { window.__bad = []; const f = window.fetch; window.fetch = function (u, o) { const url = String(typeof u === 'string' ? u : u.url); return f.apply(this, arguments).then((r) => { if (!r.ok) window.__bad.push(r.status + ' ' + url); return r }, (e) => { if (!e || e.name !== 'AbortError') window.__bad.push('ERR ' + url); throw e }) } })()` })
await b.viewport(w, hgt)
await b.open(`${BASE}/#/new`)
await ev(`localStorage.clear(); localStorage.setItem('nw_lang','en'); localStorage.setItem('nw_legend_open','0')`)
await ev('location.reload()'); await sleep(3500)
const clickText = (re, sel = 'button') => ev(`(() => { const e = [...document.querySelectorAll(${JSON.stringify(sel)})].find((x) => ${re}.test(x.innerText.trim()) && x.getBoundingClientRect().width > 0 && !x.disabled); if (!e) return false; e.click(); return true })()`)
const must = async (what, ok) => { b.log.push({ name: what, ok: !!ok, extra: '' }); console.log((ok ? 'PASS ' : 'FAIL ') + what); if (!ok) { await b.shot('demo_FAIL_' + what.replace(/\W+/g, '_')).catch(() => {}); await finish() } }
const finish = async () => {
  const bad = JSON.parse(await ev('JSON.stringify(window.__bad || [])')).filter((x) => !/tile|openstreetmap|arcgisonline/i.test(x))
  b.log.push({ name: 'no failed requests', ok: bad.length === 0, extra: bad.slice(0, 5).join(' | ') })
  b.log.push({ name: 'no console errors', ok: b.consoleErrors.length === 0, extra: b.consoleErrors.slice(0, 3).join(' | ').slice(0, 300) })
  await b.done('demo_route'); process.exit(0)
}
await must('landing is shown', await ev(`!!document.querySelector('[data-role=ln-skip],[data-role=ln-enter]')`))
await ev(`document.querySelector('[data-role=ln-skip],[data-role=ln-enter]')?.click()`); await sleep(1500)
// the first-visit tour starts by itself: skip it
for (let k = 0; k < 30 && !(await ev(`!!document.querySelector('[data-role=tour]')`)); k++) await sleep(200)
await ev(`document.querySelector('[data-role=tour] .tr-skip, [data-role=tour] [data-tour-skip]')?.click() || document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`); await sleep(800)
await must('Studio is open', await ev(`!!document.querySelector('.nw-sidebar')`))
await clickText(/Show all species/); await sleep(500)
await clickText(/Species/, '.nw-step-toggle'); await sleep(600)
await clickText(/Show all species/)
await must('goal "I have species"', await clickText(/^One species$/)); await sleep(600)
await must('pick a species', await ev(`(() => { const c = document.querySelector('.nw-checklist input[type=checkbox]'); if (!c) return false; c.click(); return true })()`)); await sleep(500)
await must('Next: where to look', await clickText(/^Next: Where to look/)); await sleep(500)
await must('Next: mark on the map', await clickText(/^Next: Mark on the map/)); await sleep(700)
if (w <= 800) await clickText(/^Open the map to mark/)
await sleep(600)
const rect = JSON.parse(await ev(`JSON.stringify(document.querySelector('.leaflet-container').getBoundingClientRect())`))
// mark a square: try a few spots of the map until the page counts one marked point
const marked = () => ev(`[...document.querySelectorAll('button')].some((x) => /Plan on this one square/.test(x.textContent))`) // exactly one point marked: the sidebar then offers this button (a second tap would make an area and remove it)
for (const [fx, fy] of w <= 800 ? [[0.5, 0.62], [0.35, 0.7], [0.65, 0.7]] : [[0.5, 0.45], [0.45, 0.5], [0.55, 0.4]]) { // on a phone the notice card covers the upper middle of the map, so the taps go lower; one tap per spot, stop at the first that marks a square
  const x = rect.left + rect.width * fx, y = rect.top + rect.height * fy
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y })
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 }); await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 }); await sleep(1800)
  if (await marked()) break
}
if (w <= 800) { await clickText(/^Open Control Panel/, '.nw-toggle'); await sleep(1500) } // the phone path: the map was shown to mark the square, the panel is opened again
await must('the clicked square is offered for planning', await ev(`[...document.querySelectorAll('button')].some((x) => /^Plan on this one square/.test(x.innerText.trim()))`))
await must('Plan on this one square', await clickText(/^Plan on this one square/)); await sleep(2500)
await must('Next: create plan', await clickText(/^Next: Create plan/)); await sleep(500)
await clickText(/^Create plan$/); await sleep(800)
await ev(`(() => { const set = (el, v) => { const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; s.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true })) }; set(document.querySelector('#nw-campaign-name'), 'Demo route'); const u = document.querySelector('#nw-campaign-unit'); if (u) set(u, 'QA') })()`); await sleep(400)
await must('create the plan', await clickText(/^Create plan$/, '.nw-btn-wide'))
let done = false
for (let i = 0; i < 40 && !done; i++) { await sleep(1000); done = await ev(`!!document.querySelector('.nw-planhead')`) }
await must('the plan result appears', done)
await must('Field kit tab', await ev(`(() => { const t = [...document.querySelectorAll('[role=tab]')].find((x) => /Field kit/i.test(x.innerText)); if (!t) return false; t.click(); return true })()`)); await sleep(800)
await must('field kit controls are shown', await ev(`!!document.querySelector('[data-tour="r-kit"]')`))
// a ranked point with the Detailed view (searched by its grid number: the same panel a click on the map opens)
await ev(`(() => { const i = document.querySelector('[data-tour="m-search"] input, input[role=combobox]'); if (!i) return; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; i.focus(); set.call(i, '12176'); i.dispatchEvent(new Event('input', { bubbles: true })) })()`); await sleep(1500)
await must('search suggests the point', await ev(`(() => { const o = [...document.querySelectorAll('[role=option]')].find((x) => /12176/.test(x.innerText)); if (!o) return false; o.click(); return true })()`)); await sleep(2500)
await must('Detailed view of the point', await clickText(/^Detailed$/, '[role=radio], button')); await sleep(800)
const tab = async (name, re) => { await must(name + ' tab', await ev(`(() => { const t = [...document.querySelectorAll('[role=tab].cy-tab')].find((x) => ${re}.test((x.getAttribute('aria-label') || '') + ' ' + x.innerText)); if (!t) return false; t.click(); return true })()`)); await sleep(3500) }
await tab('Weather', /Weather/i)
await must('weather page content', await ev(`!!document.querySelector('[data-tour="w-where"]')`))
await tab('Analytics', /Analytics/i)
await must('analytics page content', await ev(`!!document.querySelector('[data-tour="an-kpis"]')`))
await finish()
