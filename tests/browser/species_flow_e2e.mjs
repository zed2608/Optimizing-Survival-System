// UX round 5 (B): the whole "I have species" walk with real clicks in a real browser, from step 1 to "Create plan", and the plan is created.
// Usage: node tests/browser/species_flow_e2e.mjs <width> <height> <base url> <out dir> <point|area>
// The scratch server must serve the built dashboard and the API (public mode, a temporary state folder: it saves a plan). Needs Edge; nothing else.
import { launch } from './cdp_lib.mjs'
const [W, H, BASE, OUT, KIND = 'area'] = process.argv.slice(2)
const w = Number(W)
const b = await launch({ out: OUT })
const { ev, sleep } = b
await b.viewport(w, Number(H))
await b.open(`${BASE}/#/new`); await sleep(2500)
await ev(`localStorage.setItem('nw_help_banner_off','1'); localStorage.setItem('nw_tour_done','1'); localStorage.setItem('nw_legend_open','0'); localStorage.setItem('nw_lang','en')`)
await b.open(`${BASE}/#/new`); await sleep(3000)
const clickText = (re, sel = 'button') => ev(`(() => { const e = [...document.querySelectorAll(${JSON.stringify(sel)})].find((x) => ${re}.test(x.innerText) && x.getBoundingClientRect().width > 0 && !x.disabled); if (!e) return false; e.click(); return true })()`)
const must = async (what, ok) => { if (!ok) { await b.shot(`e2e_${KIND}_${W}_FAIL_${what.replace(/\W+/g, '_')}`); throw new Error(`blocked at: ${what}`) } }
const shot = (n) => b.shot(`e2e_${KIND}_${W}_${n}`)
const flow = () => ev(`JSON.stringify({ sub: document.querySelector('[data-role="species-flow"]')?.dataset.sub, next: document.querySelector('[data-role="flow-next"]')?.innerText, nextDisabled: document.querySelector('[data-role="flow-next"]')?.disabled, why: document.querySelector('[data-role="flow-why"]')?.innerText ?? null })`).then(JSON.parse)
const log = []
const step = async (name) => { const f = await flow(); log.push({ step: name, ...f }); await shot(name) }

// the dates of today have no species in season: show all species, as the page offers
await clickText('/Show all species/'); await sleep(600)
await clickText('/Species/', '.nw-step-toggle'); await sleep(600)
await clickText('/Show all species/'); await sleep(500)
await must('step 1 the species question', await clickText('/^Isang species lang$/'))
await sleep(600)
await step('1_species')
await must('choose a species', await ev(`(() => { const c = document.querySelector('.nw-checklist input[type=checkbox]'); if (!c) return false; c.click(); return true })()`))
await sleep(500)
await must('Next from step 1', await clickText('/^Next: Where to look/'))
await sleep(500)
await step('2_where')
await must('Next from step 2', await clickText('/^Next: Mark on the map/'))
await sleep(700)
await step('3_mark_empty')
if (w <= 800) { await must('open the map', await clickText('/^Open the map to mark/')); await sleep(700) }
const rect = await ev(`JSON.stringify(document.querySelector('.leaflet-container').getBoundingClientRect())`).then(JSON.parse)
const cx = rect.left + rect.width * 0.5, cy = rect.top + rect.height * 0.45
const click = async (x, y) => { await b.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 }); await b.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 }); await sleep(600) }
if (KIND === 'point') {
  await click(cx, cy)
  if (w <= 800) await clickText('/^Open Control Panel/', '.nw-toggle'); await sleep(500)
  await step('3_one_point')
  await must('Plan on this one square', await clickText('/^Plan on this one square/'))
} else {
  await click(cx, cy); await click(cx + 60, cy + 10); await click(cx + 30, cy + 70)
  await shot('3_three_points')
  if (w <= 800) await must('finish from the bar', await ev(`(() => { const e = document.querySelector('[data-role="mark-bar-finish"]'); if (!e || e.disabled) return false; e.click(); return true })()`))
  else await must('Finish area', await clickText('/^Finish area/'))
}
await sleep(2500)
await step('3_area_locked')
await must('Next from step 3', await clickText('/^Next: Create plan/'))
await sleep(500)
await step('4_create')
await must('Create plan (step 4)', await clickText('/^Create plan$/'))
await sleep(800)
// the Plan step of the sidebar
await ev(`(() => { const set = (el, v) => { const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; s.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true })) }; set(document.querySelector('#nw-campaign-name'), 'E2E walk ${KIND} ${W}'); })()`)
await sleep(400)
await ev(`document.querySelector('#nw-campaign-name').scrollIntoView({ block: 'start' })`)
const counts = await ev(`document.querySelectorAll('.nw-counts input, input[inputmode="numeric"]').length`)
await shot('5_plan_step')
await ev(`document.querySelector('.nw-btn-go.nw-btn-wide:not([data-role])')?.scrollIntoView({ block: 'center' })`)
const created = await clickText('/^Create plan$/', '.nw-btn-wide')
const reason = await ev(`[...document.querySelectorAll('button')].filter((x) => /^Create plan$/.test(x.innerText.trim()) && x.disabled).map((x) => x.title || x.getAttribute('aria-describedby') || 'disabled').join('|')`)
await must(`press Create plan in the Plan step (reason when off: ${reason})`, created)
let done = false
for (let i = 0; i < 40 && !done; i++) { await sleep(1000); done = await ev(`/Blocks/.test(document.body.innerText) && /Hectares/.test(document.body.innerText) && !!document.querySelector('.nw-planhead')`) }
await must('the plan result appears', done)
await sleep(800)
const result = await ev(`JSON.stringify({ text: (document.querySelector('.nw-planhead')?.innerText ?? '').replace(/\s+/g, ' ').slice(0, 300), planOnMap: document.querySelectorAll('.leaflet-container canvas').length })`).then(JSON.parse)
await shot('6_plan_created')
console.log(JSON.stringify({ kind: KIND, width: W, steps: log, counts, result }, null, 1))
await b.done(`species_flow_e2e_${KIND}_${W}`)
