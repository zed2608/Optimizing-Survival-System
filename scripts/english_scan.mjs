// English-mode scan (R1 W6): opens the dashboard screens in English and looks for Filipino words in the visible text. Exit code 1 when any is found.
//   node scripts/english_scan.mjs [base address]
import { launch, sleep } from '../tests/browser/cdp_lib.mjs'

const BASE = process.argv[2] ?? 'http://127.0.0.1:8001'
// Filipino stop words and common words that do not exist in English UI text (place and species names are not in this list).
const FIL = /\b(ng|mga|ang|ay|para sa|ito|ayon|hindi|lamang|nang|kung|po|maaaring|taniman|itanim|naitanim|layunin|pagtatanim|tamang|lugar|panahon|puno|lupa|mula|sa mapa|saan|ibang|bawat|kailangan|walang|datos|pumasok|laktawan|susunod|balik)\b/i
const b = await launch({ out: 'reports/overnight/r1_shots' })
const { ev } = b
const found = []
const scan = async (name) => {
  const text = await ev('document.body.innerText')
  for (const line of text.split('\n')) { const m = line.match(FIL); if (m && !/^(Sta|Sto)\b/.test(line)) found.push(`${name}: "${line.trim().slice(0, 90)}" (${m[0]})`) }
}
const click = (re, sel = 'button') => ev(`(() => { const e = [...document.querySelectorAll(${JSON.stringify(sel)})].find((x) => ${re}.test(x.innerText || '') && x.getBoundingClientRect().width > 0 && !x.disabled); if (e) e.click(); return !!e })()`)
for (const w of [1280, 360]) {
  await b.open(`${BASE}/#/new`); await b.viewport(w, 800)
  await ev(`localStorage.setItem('nw_last_visit', String(Date.now())); localStorage.setItem('nw_lang','en'); localStorage.setItem('nw_theme','light'); localStorage.setItem('nw_tour_done','1'); localStorage.setItem('nw_help_banner_off','1')`)
  await ev('location.reload()'); await sleep(3500)
  await scan(`studio ${w}`)
  for (const [n, re] of [['purpose', '/Planting purpose/'], ['window', '/Planting window/'], ['species', '/^Species/'], ['plan', '/^Plan(?!ting)/']]) { await click(re, '.nw-step-toggle'); await sleep(500); await scan(`step ${n} ${w}`) }
  await click('/Show all species/'); await sleep(400); await scan(`species list ${w}`)
  await ev(`[...document.querySelectorAll('.nw-more-toggle')][0]?.click()`); await sleep(400); await scan(`more ${w}`)
  await click('/Legend/'); await sleep(500); await scan(`legend ${w}`)
  for (const [n, i] of [['weather', 1], ['logs', 2], ['analytics', 3]]) { await ev(`document.querySelectorAll('[role=tab].cy-tab')[${i}].click()`); await sleep(3000); await scan(`${n} ${w}`) }
  await ev(`document.querySelectorAll('[role=tab].cy-tab')[0].click()`); await sleep(500)
  await ev(`document.querySelector('[data-role=settings-open]').click()`); await sleep(400); await scan(`settings ${w}`)
  await ev(`document.querySelector('[data-role=help-open]').click()`); await sleep(1200); await scan(`help ${w}`)
}
console.log(found.length ? [...new Set(found)].join('\n') : 'no Filipino words in the English-mode text of the screens checked')
b.log.push({ name: 'no Filipino in English mode', ok: found.length === 0, extra: '' })
await b.done('english_scan')
