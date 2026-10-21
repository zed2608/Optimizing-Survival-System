// Field Pack screens in headless Edge (tests/browser/cdp_lib.mjs): pictures of every screen in light and dark at 360 and 1280 px, plus the phone checks
// (no sideways scroll, every button 44 px or more). One Edge instance; the page address is a built pack (scripts/build_field_pack.py).
//   node scripts/fieldpack_shots.mjs <page address> <folder for pictures> [--lang en|fil]
import { mkdirSync } from 'node:fs'
import { launch, sleep } from '../tests/browser/cdp_lib.mjs'
import { pageAudit } from './contrast_lib.mjs'

const PAGE = process.argv[2]
const OUT = process.argv[3]
const LANG = process.argv.includes('--lang') ? process.argv[process.argv.indexOf('--lang') + 1] : 'en'
mkdirSync(OUT, { recursive: true })
const b = await launch({ out: OUT })
const { ev, send } = b
const problems = []
const audit = new Map() // selector -> { n, small, low, minRatio, e.g. }
const click = (q, text) => ev(`(() => { const e = [...document.querySelectorAll(${JSON.stringify(q)})].find((x) => ${text ? `new RegExp(${JSON.stringify(text)}, 'i').test(x.innerText || x.getAttribute('aria-label') || '')` : 'true'} && x.getBoundingClientRect().width > 0); if (!e) return false; e.click(); return true })()`)
const metrics = (tag) => ev(`(() => {
  const small = [...document.querySelectorAll('button, a, input, summary, [role=button]')].filter((e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && (r.height < 44 || r.width < 44) && !e.closest('.leaflet-container, .attrib') && !(e.type === 'checkbox') }).map((e) => (e.className || e.tagName) + ':' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height)).slice(0, 6)
  return { sideways: document.documentElement.scrollWidth > innerWidth + 1 || (document.getElementById('app') && document.getElementById('app').scrollWidth > document.getElementById('app').clientWidth + 1), small }
})()`).then((m) => { if (m.sideways) problems.push(`${tag}: sideways scroll`); if (m.small.length) problems.push(`${tag}: small targets ${m.small.join(', ')}`) })

for (const scheme of ['light', 'dark']) {
  for (const [W, H] of [[360, 740], [1280, 800]]) {
    await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: scheme }] })
    await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: W < 600 })
    await b.fresh(PAGE, { lang: LANG, tours: true })
    await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: scheme }] })
    await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: W < 600 })
    b.tileMode = 'ok'
    const tag = `${scheme}_${W}`
    const snap = async (name) => {
      await sleep(500); await b.shot(`${name}_${tag}`); await metrics(`${name} ${tag}`)
      for (const r of await ev(`(${pageAudit.toString()})()`)) {
        const need = r.large ? 3 : 4.5
        if (r.size >= 12 && r.ratio >= need) continue
        const g = audit.get(r.sel) ?? { n: 0, small: 0, low: 0, min: 99, text: r.text, where: new Set() }
        g.n++; if (r.size < 12) g.small++; if (r.ratio < need) { g.low++; g.min = Math.min(g.min, r.ratio) }; g.where.add(`${name} ${tag}`); audit.set(r.sel, g)
      }
    }
    await snap('1_landing')
    await ev(`document.querySelector('[data-tour=l-start]')?.click()`); await sleep(500)
    await snap('2_home')
    await click('.bcard'); await sleep(1500)
    await snap('3_block')
    await click('.detailsbtn'); await sleep(500)
    await snap('4_block_details')
    await click('.detailsbtn'); await sleep(300)
    await click('.toolbox .btn', 'help'); await sleep(500)
    await snap('5_help')
    await click('.overlay [data-act=tour]'); await sleep(900)
    await snap('6_tour')
  }
}
for (const [sel, g] of audit) console.log(`  ${g.n}  ${sel}  (under 12px: ${g.small}, below AA: ${g.low}, min ratio ${g.min})  e.g. "${g.text}"  [${[...g.where].slice(0, 3).join('; ')}]`)
console.log(audit.size ? `text: ${audit.size} selectors below 12 px or below AA` : 'text: nothing under 12 px and nothing below AA (both themes, 360 and 1280)')
console.log(problems.length ? problems.join(String.fromCharCode(10)) : 'no sideways scroll, no target under 44 px')
const CI = process.argv.includes('--ci')
const bad = audit.size > 0 || problems.length > 0
if (CI) b.log.push({ name: 'text and phone checks', ok: !bad, extra: '' })
await b.done('fieldpack_shots')
