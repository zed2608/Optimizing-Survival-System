// Print-to-PDF of the printable views (R1 W4), in headless Edge through the DevTools protocol of tests/browser/cdp_lib.mjs: the user guide (Help > Print this guide) and the Analytics page.
//   node scripts/print_check.mjs <base address> <output folder>      writes help.pdf and analytics.pdf (A4); tests/test_w4_print.py reads them
import { mkdirSync, writeFileSync } from 'node:fs'
import { launch, sleep } from '../tests/browser/cdp_lib.mjs'

const BASE = process.argv[2] ?? 'http://127.0.0.1:8001'
const OUT = process.argv[3] ?? 'reports/overnight/r1_shots/print'
mkdirSync(OUT, { recursive: true })
const b = await launch({ out: OUT })
const { ev, send } = b
await b.open(`${BASE}/#/new`)
await b.viewport(1280, 800)
await ev(`localStorage.setItem('nw_last_visit', String(Date.now())); localStorage.setItem('nw_lang','en'); localStorage.setItem('nw_theme','dark'); localStorage.setItem('nw_tour_done','1'); localStorage.setItem('nw_help_banner_off','1')`)
await ev('location.reload()'); await sleep(3500)
const pdf = async (name) => {
  await send('Emulation.setEmulatedMedia', { media: 'print' })
  const r = await send('Page.printToPDF', { paperWidth: 8.27, paperHeight: 11.69, marginTop: 0.59, marginBottom: 0.59, marginLeft: 0.59, marginRight: 0.59, printBackground: true, preferCSSPageSize: true })
  await send('Emulation.setEmulatedMedia', { media: '' })
  writeFileSync(`${OUT}/${name}.pdf`, Buffer.from(r.result.data, 'base64'))
}
await ev(`document.querySelector('[data-role=settings-open]').click()`); await sleep(400)
await ev(`document.querySelector('[data-role=help-open]').click()`); await sleep(1200)
await pdf('help')
await ev(`[...document.querySelectorAll('button')].find((x) => /^Close/.test(x.innerText.trim()))?.click()`); await sleep(500)
await ev(`document.querySelectorAll('[role=tab].cy-tab')[3].click()`); await sleep(3500)
await pdf('analytics')
b.done('print_check')
