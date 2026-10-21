// OBSOLETE after design-v2 (R1): written for the earlier dashboard (old selectors, SVG clipping rule, top-tab size). Kept for reference; it needs a rewrite for the Canopy UI.
// Stage C1 in headless Edge against a real service: the Species card section "Climate and soil (reference only)" at a desktop and a phone width.
//   node tests/browser/species_card_climate_check.mjs <base address> <access cookie value> <expected rainfall from the file> <folder for pictures>
import { launch } from './cdp_lib.mjs'

const [BASE, COOKIE, RAIN, OUT] = process.argv.slice(2)
const b = await launch({ out: OUT })
const { ev, text, check, sleep, waitExpr, noBadText } = b
const host = new URL(BASE).hostname
await b.send('Network.enable')
await b.send('Network.setCookie', { name: 'os_access', value: COOKIE, domain: host, path: '/' })

for (const [W, H, label] of [[1280, 900, 'desktop'], [390, 844, 'phone']]) {
  const tag = `${label} ${W}x${H}: `
  await b.viewport(W, H)
  await b.open(`${BASE}/#/new`)
  await sleep(2500)
  await ev(`localStorage.setItem('nw_help_banner_off','1'); localStorage.setItem('nw_tour_done','1')`)
  await b.open(`${BASE}/#/new`)
  await sleep(2500)
  // find the species through the search box: choosing a species opens its card
  await ev(`(() => { const i = document.querySelector('input[role="combobox"]'); i.focus(); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(i, 'Narra'); i.dispatchEvent(new Event('input', { bubbles: true })) })()`)
  await waitExpr(`(() => { const o = [...document.querySelectorAll('[role="option"]')].find((x) => /Narra/.test(x.innerText)); if (!o) return false; o.dispatchEvent(new MouseEvent('click', { bubbles: true })); return true })()`, 12000) // found and chosen in one step: the list redraws while typing
  await waitExpr(`!!document.querySelector('[data-section="climate-reference"]')`, 15000)
  await ev(`document.querySelector('[data-section="climate-reference"]').scrollIntoView({ block: 'center' })`)
  await sleep(400)
  const sec = await ev(`document.querySelector('[data-section="climate-reference"]').innerText`)
  check(tag + 'the section "Climate and soil (reference only)" is in the Species card, in English and Filipino, with PROVISIONAL', /Climate and soil \(reference only\)/.test(sec) && /Klima at lupa \(reference lang\)/.test(sec) && /PROVISIONAL/.test(sec))
  check(tag + `rain: the species range, the San Mateo reference ${RAIN} mm a year from the file, and the station`, /1200 to 3000 mm a year/.test(sec) && sec.includes(`${RAIN} mm a year`) && /Science Garden, Quezon City/.test(sec) && /NOT San Mateo/.test(sec) && /2026-10-15/.test(sec))
  check(tag + 'rain: an honest verdict ("Fits" / "Pasok" for Narra)', await ev(`document.querySelector('[data-row="rain"] [data-verdict]').dataset.verdict`) === 'fits' && /Pasok/.test(sec))
  check(tag + 'temperature: the species range and "No data yet / Walang datos pa", no verdict', (sec.match(/Walang datos pa/g) || []).length >= 2 && /24 to 27/.test(sec) && (await ev(`document.querySelector('[data-row="temp"] [data-verdict]').dataset.verdict`)) === 'no_data')
  check(tag + 'each comparison names its reference and status', (await ev(`[...document.querySelectorAll('[data-section="climate-reference"] [data-role="verdict-ref"]')].map((e) => e.innerText).join(' | ')`)).includes('Science Garden, Quezon City') && /SoilGrids 2\.0 \(ISRIC\)/.test(sec) && /pansamantalang kapalit/.test(sec) && /Estimate lang/.test(sec))
  check(tag + 'pH (stage C2): the site pH from SoilGrids with its range, "estimate only", the species range "not yet verified", inside or outside, not in the score, the credit', /Tinatayang pH: \d\.\d \(posibleng \d\.\d–\d\.\d\)/.test(sec) && /Estimate lang, hindi sinukat sa San Mateo/.test(sec) && /range hindi pa pirmado/.test(sec) && /5 to 7.5/.test(sec) && ['inside', 'outside', 'uncertain'].includes(await ev(`document.querySelector('[data-row="ph"] [data-verdict]').dataset.verdict`)) && /Hindi ito kasama sa score\./.test(sec) && /pH: SoilGrids 2\.0 \(ISRIC\), CC BY 4\.0/.test(sec) && /SoilGrids 2\.0 \(modelo, 250 m, hindi sinukat sa San Mateo\)/.test(sec))
  check(tag + 'the climate type line comes from the file: Type I, dry from December to May', /Type I \(dry from December to May\)/.test(sec) && /Type I \(tuyo mula Disyembre hanggang Mayo\)/.test(sec) && /LCCAP/.test(sec))
  check(tag + 'the clear line: not part of the score, the nearest station is used', /This is not part of the score\. The nearest station is used, not San Mateo itself\./.test(sec) && /Hindi ito bahagi ng score\. Pinakamalapit na istasyon ang gamit, hindi San Mateo mismo\./.test(sec))
  const fit = JSON.parse(await ev(`(() => { const s = document.querySelector('[data-section="climate-reference"]'); const card = s.closest('.nw-card'); return JSON.stringify({ page: document.documentElement.scrollWidth <= document.documentElement.clientWidth, card: card.scrollWidth <= card.clientWidth + 1, section: s.scrollWidth <= s.clientWidth + 1, right: s.getBoundingClientRect().right <= innerWidth + 1 }) })()`))
  check(tag + 'no sideways scroll: the page, the card and the section fit the width', fit.page && fit.card && fit.section && fit.right, JSON.stringify(fit))
  await noBadText(tag + 'the climate section')
  await b.shot(`climate_${label}`)
}
check('no uncaught page errors', b.events.length === 0, b.events.length ? JSON.stringify(b.events[0].params.exceptionDetails).slice(0, 300) : '')
await b.done('climate_card_report')
