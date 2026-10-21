// First visit (R1 W3): after the landing is closed the global tour starts by itself with "Don't show again"; once it is finished it does not start again.
import { launch, sleep } from '../tests/browser/cdp_lib.mjs'
const BASE = process.argv[2] || 'http://127.0.0.1:8001'
const b = await launch({ out: '.' })
const { ev } = b
const tourUp = () => ev(`!!document.querySelector('[data-role=tour]')`)
const closeLanding = () => ev(`document.querySelector('[data-role=ln-skip],[data-role=ln-enter]')?.click()`)
await b.open(`${BASE}/#/new`); await b.viewport(1280, 800)
await ev(`localStorage.clear(); localStorage.setItem('nw_lang','en')`)
await ev('location.reload()'); await sleep(3500)
await closeLanding()
for (let k = 0; k < 40 && !(await tourUp()); k++) await sleep(250)
const shown = (await tourUp()) && (await ev(`!!document.querySelector('.tr-never')`))
b.log.push({ name: 'first visit: the tour starts after the landing, with "Don\'t show again"', ok: shown === true, extra: '' })
for (let i = 0; i < 60; i++) {
  if (await ev('!!window.__tourLast')) break
  await ev(`document.querySelector('[data-tour-primary]')?.click()`)
  await sleep(900)
}
const flag = await ev(`localStorage.getItem('nw_tour_done')`)
b.log.push({ name: 'finishing the tour is remembered', ok: flag === '1', extra: String(flag) })
await ev(`localStorage.setItem('nw_last_visit', '0')`)
await ev('location.reload()'); await sleep(3500)
await closeLanding(); await sleep(3000)
b.log.push({ name: 'second visit: the finished tour does not start again', ok: (await tourUp()) === false, extra: '' })
await b.done('tour_auto')
