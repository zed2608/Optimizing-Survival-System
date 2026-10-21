// Full-page tabs check (CDP, headless Edge): Campaign Logs, Weather and System Analytics open as full pages.
//   node tests/browser/tab_pages_check.mjs [--base http://127.0.0.1:8001] [--shots reports/overnight/v2_fix_shots] [--no-shots]
// For 360 / 768 / 1280 px, light and dark: the page covers the viewport below the header, the map / stepper / legend are not visible, the title (h1) has the focus, Esc goes back to the
// studio, the active tab stays marked, and the map is back when returning. Exit code 1 on any failure.
import { mkdirSync } from 'node:fs'
import { launch, sleep } from './cdp_lib.mjs'

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d }
const BASE = arg('--base', 'http://127.0.0.1:8001')
const SHOTS = process.argv.includes('--no-shots') ? null : arg('--shots', 'reports/overnight/v2_fix_shots')
if (SHOTS) mkdirSync(SHOTS, { recursive: true })
const b = await launch({ out: SHOTS || '.' })
const { ev } = b
const fails = []
const check = (ok, msg) => { if (!ok) { fails.push(msg); console.log('FAIL', msg) } }
const TABS = [['history', /Campaign|Logs|Kasaysayan/i], ['weather', /Weather|Panahon/i], ['analytics', /Analytics/i]]

for (const theme of ['light', 'dark']) {
  for (const w of [360, 768, 1280]) {
    await b.open(`${BASE}/#/new`); await b.viewport(w, 800)
    await ev(`localStorage.setItem('nw_last_visit', String(Date.now())); localStorage.setItem('nw_lang','en'); localStorage.setItem('nw_theme','${theme}'); localStorage.setItem('nw_tour_done','1'); localStorage.setItem('nw_help_banner_off','1'); localStorage.setItem('nw_hints','1')`)
    await ev('location.reload()')
    await sleep(3500)
    for (const [id, re] of TABS) {
      const tag = `${theme}/${w}/${id}`
      const clicked = await ev(`(() => { const e = [...document.querySelectorAll('[role=tab], .cy-tab')].find((x) => ${re}.test((x.innerText || '') + ' ' + (x.getAttribute('aria-label') || '')) && x.getBoundingClientRect().width > 0); if (!e) return false; e.click(); return true })()`)
      check(clicked, `${tag}: tab button not found`)
      if (!clicked) continue
      await sleep(900)
      const r = await ev(`(() => {
        const pg = document.querySelector('[data-role=tab-page]'); if (!pg) return { page: false }
        const pr = pg.getBoundingClientRect(); const hd = document.querySelector('.nw-topbar')?.getBoundingClientRect()
        const vis = (sel) => [...document.querySelectorAll(sel)].some((e) => { const s = getComputedStyle(e); const q = e.getBoundingClientRect(); return s.visibility !== 'hidden' && s.display !== 'none' && q.width > 0 && q.height > 0 && !pg.contains(e) })
        const h1 = pg.querySelector('h1')
        return { page: true, top: pr.top, headerBottom: hd ? hd.bottom : 0, left: pr.left, right: innerWidth - pr.right, bottom: innerHeight - pr.bottom,
          radius: getComputedStyle(pg).borderRadius, bg: getComputedStyle(pg).backgroundColor, scrollY: window.scrollY,
          mapVisible: vis('.leaflet-container') || vis('.leaflet-control-attribution'), stepperVisible: vis('.nw-stepper, .nw-sidebar, .nw-legend, .nw-legend-btn, .nw-locate, .nw-mapview'),
          h1: !!h1, h1Focus: document.activeElement === h1, closeBtn: /Close & Return/i.test(pg.innerText || ''),
          selected: [...document.querySelectorAll('[role=tab][aria-selected=true]')].map((x) => x.innerText.trim()).join('|') }
      })()`)
      check(r.page, `${tag}: no .nw-page`)
      if (!r.page) continue
      check(Math.abs(r.top - r.headerBottom) <= 2, `${tag}: page top ${r.top} is not the header bottom ${r.headerBottom}`)
      check(r.left <= 1 && r.right <= 1 && r.bottom <= 1, `${tag}: page does not reach the edges (${r.left}/${r.right}/${r.bottom})`)
      check(r.radius === '0px', `${tag}: rounded corners ${r.radius}`)
      check(!/rgba\(0, 0, 0, 0\)/.test(r.bg), `${tag}: page background is transparent`)
      check(!r.mapVisible, `${tag}: map or attribution visible`)
      check(!r.stepperVisible, `${tag}: stepper / legend / dock visible`)
      check(r.h1 && r.h1Focus, `${tag}: title has no focus`)
      check(!r.closeBtn, `${tag}: Close & Return button still there`)
      check(r.selected.length > 0, `${tag}: no tab marked as active`)
      check(r.scrollY === 0, `${tag}: the window scrolled`)
      if (SHOTS && theme && ['history', 'weather', 'analytics'].includes(id) && (w === 360 || w === 1280)) await b.shot(`page_${id}_${theme}_${w}`)
    }
    // Esc returns to the studio and the map is back
    await b.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
    await b.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
    await sleep(700)
    const back = await ev(`(() => { const m = document.querySelector('.leaflet-container'); const s = m && getComputedStyle(m); return { page: !!document.querySelector('[data-role=tab-page]'), map: !!m && s.visibility !== 'hidden' && m.getBoundingClientRect().width > 0 } })()`)
    check(!back.page && back.map, `${theme}/${w}: Esc did not bring the studio and map back (${JSON.stringify(back)})`)
  }
}
console.log(fails.length ? `${fails.length} failed` : 'tab pages: all checks passed')
b.done('tab_pages_check')
process.exit(fails.length ? 1 : 0)
