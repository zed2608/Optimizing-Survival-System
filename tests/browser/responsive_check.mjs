// OBSOLETE after design-v2 (R1): written for the earlier dashboard (old selectors, SVG clipping rule, top-tab size). Kept for reference; it needs a rewrite for the Canopy UI.
// C4 (overnight 2026-10-15) in headless Edge against a real service: the dashboard (#/new) on a phone, 360 and 390 px wide: no sideways scroll, nothing clipped by the right edge, and the main buttons at least 44 px tall.
//   node tests/browser/responsive_check.mjs <base address> <access cookie value> <folder for pictures>
import { launch } from './cdp_lib.mjs'

const [BASE, COOKIE, OUT] = process.argv.slice(2)
const b = await launch({ out: OUT })
const { ev, check, sleep, waitExpr, send } = b
await send('Network.enable')
await send('Network.setCookie', { name: 'os_access', value: COOKIE, domain: new URL(BASE).hostname, path: '/' })

// What the person cannot reach: a visible element (outside the map) whose right edge is beyond the screen and that is not inside a real scroller (overflow auto / scroll).
const CLIPPED = `(() => {
  const vw = innerWidth
  const vis = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !e.closest('[hidden]') }
  const inScroller = (e) => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const o = getComputedStyle(p); if (/(auto|scroll)/.test(o.overflowX) && p.scrollWidth > p.clientWidth + 1) return true } return false }
  const sideOpen = !!document.querySelector('.nw-root.sidebar-open')
  const bad = [...document.querySelectorAll('body *')].filter((e) => vis(e) && !e.closest('.leaflet-container') && !e.closest('.leaflet-control-container') && (sideOpen || !e.closest('.nw-sidebar')))   // a CLOSED sidebar waits off the left edge on purpose
    .filter((e) => { const r = e.getBoundingClientRect(); return (r.right > vw + 1 || r.left < -1) && !inScroller(e) })
  return JSON.stringify({ hscroll: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > vw + 1, clipped: bad.length, first: bad.slice(0, 3).map((e) => e.tagName.toLowerCase() + '.' + String(e.className).split(' ')[0]) })
})()`
const TALL = (sel) => `(() => { const e = [...document.querySelectorAll(${JSON.stringify(sel)})].filter((x) => { const r = x.getBoundingClientRect(); return r.width > 0 && r.height > 0 }); return JSON.stringify({ n: e.length, min: e.length ? Math.min(...e.map((x) => Math.round(x.getBoundingClientRect().height))) : null }) })()`
const clickText = (re, scope) => ev(`(() => { const re = ${re.toString()}; const e = [...document.querySelectorAll(${JSON.stringify(scope)})].find((x) => x.getBoundingClientRect().width > 0 && re.test((x.getAttribute('aria-label') || '') + ' ' + (x.innerText || ''))); if (!e) return false; e.click(); return true })()`)

for (const [W, H] of [[360, 740], [390, 844]]) {
  const tag = `phone ${W}x${H}: `
  await b.viewport(W, H)
  await b.open('about:blank')
  await b.open(`${BASE}/#/new`)
  await sleep(2500)
  await ev(`localStorage.setItem('nw_help_banner_off','1'); localStorage.setItem('nw_tour_done','1'); localStorage.setItem('nw_legend_open','0')`)
  await send('Page.reload')
  await sleep(3500)
  const look = async (what) => {
    await sleep(600)
    const r = JSON.parse(await ev(CLIPPED))
    check(tag + what + ': no sideways scroll', r.hscroll === false)
    check(tag + what + ': nothing is clipped by the screen edge', r.clipped === 0, JSON.stringify(r.first))
    await b.shot(`resp_${W}_${what.replace(/[^a-z0-9]+/gi, '_')}`)
  }
  // the sidebar is open at the start
  await look('home with the sidebar open')
  const tabs = JSON.parse(await ev(TALL('.nw-tab')))
  check(tag + 'the top tabs are at least 44 px tall', tabs.n >= 3 && tabs.min >= 44, JSON.stringify(tabs))
  const tog = JSON.parse(await ev(TALL('.nw-toggle, .nw-step-toggle')))
  check(tag + 'the sidebar button and the step buttons are at least 44 px tall', tog.n >= 5 && tog.min >= 44, JSON.stringify(tog))
  // every step, one after the other
  for (const re of [/Planting purpose/, /Planting window/, /Species/, /Plan(?!ting)/]) {
    await clickText(re, '.nw-step-toggle')
    await look('step ' + re.source.replace(/[^a-z ]/gi, ''))
  }
  // close the sidebar: the search box, Map view and the season note are shown across the width
  await clickText(/Hide Control Panel/, 'button')
  await sleep(700)
  await look('home with the sidebar closed')
  check(tag + 'the search box is on the screen and as wide as the screen allows', JSON.parse(await ev(`(() => { const e = document.querySelector('.nw-search-box'); if (!e) return 'null'; const r = e.getBoundingClientRect(); return JSON.stringify({ l: r.left >= 0, r: r.right <= innerWidth, w: Math.round(r.width) }) })()`)).r === true)
  const mv = JSON.parse(await ev(TALL('.nw-mapview-btn, .nw-legend-btn')))
  check(tag + 'Map view and Legend are at least 44 px tall', mv.n >= 2 && mv.min >= 44, JSON.stringify(mv))
  // the tabs
  for (const [re, name] of [[/Weather/, 'weather tab'], [/Campaign Logs/, 'campaign logs'], [/System Analytics/, 'analytics'], [/Active Studio/, 'studio again']]) {
    await clickText(re, '[role=tab]')
    await sleep(1500)
    await look(name)
  }
}
await b.done('responsive')
