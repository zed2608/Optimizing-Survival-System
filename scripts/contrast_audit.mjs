// Contrast and text-size audit of the dashboard, in a real browser (headless Edge through the DevTools protocol of tests/browser/cdp_lib.mjs: this project has no Playwright and no package may be installed).
//   node scripts/contrast_audit.mjs [--base http://127.0.0.1:8011] [--widths 360,1280] [--themes light,dark] [--out reports/overnight/v2_fix_shots] [--ci]
// For light and dark, at each width, it opens the studio (each step, the species walk, settings), the point panel (Simple, Detailed, the species card), the legend, the right-click menu, the three tabs and Help,
// the More items and the landing slides. For every visible text node it computes the font size and the contrast against the effective background (walking up the ancestors and compositing their alpha),
// and reports the nodes below 12 px and below WCAG AA (4.5:1; 3:1 for large text: 24 px, or bold from 18.66 px), grouped by selector.
// Not measured (said in the report): text over the map imagery (leaflet-container), svg text, disabled controls, text on a gradient (the nearest flat colour is used and the node is marked "gradient").
// With --ci the exit code is 1 when anything is below 12 px or below AA. The server must serve the built dashboard and the API (public mode, a temporary state folder).
import { mkdirSync, writeFileSync } from 'node:fs'
import { launch, sleep } from '../tests/browser/cdp_lib.mjs'
import { layoutAudit } from './layout_lib.mjs'

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d }
const BASE = arg('--base', 'http://127.0.0.1:8011')
const WIDTHS = arg('--widths', '360,768,1100,1280').split(',').map(Number)
const THEMES = arg('--themes', 'light,dark').split(',')
const OUT = arg('--out', 'reports/overnight/v2_fix_shots')
const CI = process.argv.includes('--ci')
mkdirSync(OUT, { recursive: true })

// ------------------------------------------------------------------------------------------------ in the page
function pageAudit() {
  const parse = (s) => {
    let m = s.match(/rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:[ ,/]+([\d.]+%?))?\s*\)/)
    if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : m[4].endsWith('%') ? parseFloat(m[4]) / 100 : +m[4] }
    m = s.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+%?))?\s*\)/)
    if (m) return { r: +m[1] * 255, g: +m[2] * 255, b: +m[3] * 255, a: m[4] === undefined ? 1 : m[4].endsWith('%') ? parseFloat(m[4]) / 100 : +m[4] }
    return { r: 0, g: 0, b: 0, a: 0 }
  }
  const over = (top, bottom) => {
    const a = top.a + bottom.a * (1 - top.a)
    if (a === 0) return { r: 0, g: 0, b: 0, a: 0 }
    const f = (c) => (top[c] * top.a + bottom[c] * bottom.a * (1 - top.a)) / a
    return { r: f('r'), g: f('g'), b: f('b'), a }
  }
  const lum = (c) => {
    const k = [c.r, c.g, c.b].map((v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4 })
    return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2]
  }
  const ratio = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05) }
  const label = (e) => {
    const cls = [...e.classList].filter((c) => !/^(is-|has-)/.test(c)).slice(0, 2).join('.')
    return e.tagName.toLowerCase() + (cls ? '.' + cls : '')
  }
  const ctx = (e) => {
    for (let p = e.parentElement; p; p = p.parentElement) {
      const role = p.getAttribute('data-role')
      if (role) return `[${role}]`
      const c = [...p.classList].find((x) => /^(nw-|cy-|an-|wx-|ln-|set-|v2)/.test(x))
      if (c && p !== document.body) return '.' + c
    }
    return ''
  }
  const out = []
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  const seen = new Set()
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const text = n.textContent.replace(/\s+/g, ' ').trim()
    if (!text) continue
    const e = n.parentElement
    if (!e || seen.has(e) || e.closest('svg, script, style, noscript, .sr-only, canvas, [aria-hidden="true"]') || (e.closest('.leaflet-container') && !e.closest('.leaflet-tooltip, .leaflet-popup'))) continue
    if (e.closest('button:disabled, input:disabled, [aria-disabled="true"]')) continue
    const r = e.getBoundingClientRect()
    if (r.width < 1 || r.height < 1 || r.bottom < 0 || r.right < 0 || r.top > innerHeight || r.left > innerWidth) continue
    const cs = getComputedStyle(e)
    if (cs.visibility === 'hidden' || cs.display === 'none') continue
    // clip / hidden overflow ancestors that cut this node away entirely
    let clipped = false
    for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
      const ps = getComputedStyle(p)
      if (ps.overflow !== 'visible' || ps.overflowX !== 'visible') { const pr = p.getBoundingClientRect(); if (r.bottom <= pr.top || r.top >= pr.bottom || r.right <= pr.left || r.left >= pr.right) { clipped = true; break } }
    }
    if (clipped) continue
    if (parseFloat(cs.fontSize) < 1) continue // font-size 0 = icon-only control: no visible text
    seen.add(e)
    let op = 1
    for (let p = e; p; p = p.parentElement) op *= parseFloat(getComputedStyle(p).opacity)
    if (op < 0.05) continue
    const fg = parse(cs.color)
    fg.a *= op
    // effective background: the layers from the element up to the root, composited over the page colour
    const layers = []
    let grad = false
    let stops = []
    const hl = e.closest('.cy-tabs-slide .cy-tab[aria-selected="true"]') && document.querySelector('.cy-tabs-slide .cy-tab-hl')
    if (hl) layers.push(parse(getComputedStyle(hl).backgroundColor))
    let cum = 1
    for (let p = e; p; p = p.parentElement) {
      const ps = getComputedStyle(p)
      const o = parseFloat(ps.opacity)
      const bg = parse(ps.backgroundColor)
      if (bg.a > 0) layers.push({ ...bg, a: bg.a * cum })
      if (ps.backgroundImage !== 'none' && /gradient/.test(ps.backgroundImage)) { grad = true; if (!stops.length) stops = (ps.backgroundImage.match(/rgba?([^)]*)/g) || []).map(parse).filter((c) => c.a > 0) }
      if (bg.a >= 0.99 && cum >= 0.99) break
      cum *= o
    }
    let base = { r: 255, g: 255, b: 255, a: 1 }
    for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base)
    // text on a gradient: judged against the worst colour stop (the gradient is drawn over the flat layers)
    const bases = stops.length ? stops.map((c) => over(c, base)) : [base]
    let worst = null
    for (const bb of bases) { const rr = ratio(over(fg, bb), bb); if (worst === null || rr < worst) worst = rr }
    const text2 = over(fg, base)
    const size = parseFloat(cs.fontSize)
    const weight = parseInt(cs.fontWeight, 10) || 400
    const large = size >= 24 || (size >= 18.66 && weight >= 700)
    out.push({ sel: `${label(e)} < ${ctx(e)}`, text: text.slice(0, 40), size, weight, ratio: +worst.toFixed(2), large, grad })
  }
  return out
}

// ------------------------------------------------------------------------------------------------ the states
const b = await launch({ out: OUT })
const { ev } = b
const clickText = (re, sel = 'button') => ev(`(() => { const e = [...document.querySelectorAll(${JSON.stringify(sel)})].find((x) => ${re}.test(x.innerText || '') && x.getBoundingClientRect().width > 0 && !x.disabled); if (!e) return false; e.click(); return true })()`)
const key = async (k, code, vk) => { for (const type of ['keyDown', 'keyUp']) await b.send('Input.dispatchKeyEvent', { type, key: k, code, windowsVirtualKeyCode: vk, ...(k === 'Enter' ? { text: '\r' } : {}) }) }
const rows = [] // every node of every state
const states = {}
const layoutRows = []
async function snap(name, ctxInfo) {
  const list = await ev(`(${pageAudit.toString()})()`)
  for (const r of list) rows.push({ ...ctxInfo, state: name, ...r })
  for (const r of await ev(`(${layoutAudit.toString()})()`)) layoutRows.push({ ...ctxInfo, state: name, ...r })
  states[`${ctxInfo.theme}/${ctxInfo.w}`] = (states[`${ctxInfo.theme}/${ctxInfo.w}`] ?? 0) + 1
}
const quiet = async (f) => { try { await f() } catch (e) { console.log('  step skipped:', String(e.message).slice(0, 90)) } }

for (const theme of THEMES) {
  for (const w of WIDTHS) {
    const c = { theme, w }
    await b.viewport(w, w <= 500 ? 740 : 800)
    await b.open(`${BASE}/#/new`); await sleep(2000)
    await ev(`localStorage.setItem('nw_last_visit', String(Date.now())); localStorage.setItem('nw_lang','en'); localStorage.setItem('nw_theme','${theme}'); localStorage.setItem('nw_tour_done','1'); localStorage.setItem('nw_help_banner_off','1'); localStorage.setItem('nw_hints','1')`)
    await ev('location.reload()'); await sleep(3500)
    const shot = (n) => b.shot(`audit_${n}_${w}_${theme}`)
    await snap('studio-goal', c)
    for (const [n, re] of [['purpose', '/Planting purpose/'], ['window', '/Planting window/'], ['species', '/^Species/'], ['plan', '/^Plan(?!ting)/']]) {
      await quiet(async () => { await clickText(re, '.nw-step-toggle'); await sleep(500); await snap('step-' + n, c) })
    }
    await quiet(async () => {
      await clickText('/Show all species/'); await sleep(400)
      await clickText('/^Species/', '.nw-step-toggle'); await sleep(500)
      await clickText('/^One species$/'); await sleep(500); await snap('walk-1', c); await shot('stepper-1')
      await ev(`document.querySelector('.nw-checklist input[type=checkbox]')?.click()`); await sleep(400)
      await clickText('/^Next: Where to look/'); await sleep(500); await snap('walk-2', c); await shot('stepper-2')
      await clickText('/^Next: Mark on the map/'); await sleep(600); await snap('walk-3-mark', c)
    })
    await quiet(async () => { await ev(`document.querySelector('[data-role=settings-open]').click()`); await sleep(400); await snap('settings', c); await ev(`document.querySelector('[data-role=settings-open]').click()`) })
    await quiet(async () => { await clickText('/Planting purpose/', '.nw-step-toggle'); await sleep(300) })
    if (w <= 800) await quiet(async () => { await ev(`document.querySelector('.nw-toggle')?.click()`); await sleep(400) })
    // the point panel
    await quiet(async () => {
      await ev(`(() => { const i = document.querySelector('.nw-search input'); i.focus(); i.select() })()`)
      await b.send('Input.insertText', { text: '17097' }); await sleep(900)
      await key('ArrowDown', 'ArrowDown', 40); await key('Enter', 'Enter', 13); await sleep(2500)
      await clickText('/Show all species/'); await sleep(900)
      await snap('point-simple', c); await shot('point-simple')
      await clickText('/^Detailed$/'); await sleep(700)
      await ev(`document.querySelector('[data-role="land-details"] summary')?.click()`); await sleep(400)
      await snap('point-detailed', c); await shot('point-detailed')
      await ev(`document.querySelector('.nw-prow details summary')?.click()`); await sleep(400); await snap('point-row-open', c)
      await ev(`document.querySelector('.nw-prow-name')?.click()`); await sleep(1500); await snap('species-card', c)
      await clickText('/^Close/'); await sleep(400)
    })
    await quiet(async () => { await clickText('/^Legend/'); await sleep(600); await snap('legend', c); await shot('legend') })
    // the right-click menu on a drawn square
    await quiet(async () => {
      if (w <= 800) await ev(`[...document.querySelectorAll('button')].find((x) => /^Close/.test(x.innerText.trim()) && x.getBoundingClientRect().width > 0)?.click()`)
      const spot = JSON.parse(await ev(`JSON.stringify((() => { const cv = document.querySelector('canvas.nw-grid-canvas'); if (!cv) return null; const r = cv.getBoundingClientRect(); const g = cv.getContext('2d'); const k = cv.width / r.width; for (let y = 250; y < innerHeight - 80; y += 12) for (let x = ${w >= 1000 ? 420 : 30}; x < ${w >= 1000 ? 900 : w - 30}; x += 12) { const d = g.getImageData(Math.round((x - r.left) * k), Math.round((y - r.top) * k), 1, 1).data; if (d[3] > 200) { const el = document.elementFromPoint(x, y); if (el && el.closest('.leaflet-container') && !el.closest('.nw-search, .nw-legend, .nw-locate, .nw-mapview, .leaflet-control, .nw-right, .nw-sidebar')) return { x, y } } } return null })())`))
      if (!spot) throw new Error('no square found')
      await b.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: spot.x, y: spot.y }); await sleep(600); await snap('hover-square', c); await shot('hover-square')   // the hover card of a square (a Leaflet tooltip)
      await b.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: spot.x, y: spot.y })
      await b.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: spot.x, y: spot.y, button: 'right', buttons: 2, clickCount: 1 })
      await b.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: spot.x, y: spot.y, button: 'right', buttons: 0, clickCount: 1 })
      await sleep(1200); await snap('rightclick-menu', c); await shot('rightclick-menu')
      await key('Escape', 'Escape', 27); await sleep(300)
    })
    // the tabs and Help
    for (const [n, i] of [['weather', 1], ['logs', 2], ['analytics', 3]]) {
      await quiet(async () => { await ev(`document.querySelectorAll('[role=tab].cy-tab')[${i}].click()`); await sleep(2800); await snap('tab-' + n, c); await shot('tab-' + n); if (n === 'weather') { await ev(`[...document.querySelectorAll('summary, h2, h3, h4, div')].find((e) => /Only if you can water/i.test(e.textContent || '') && e.children.length < 4)?.scrollIntoView({ block: 'center' })`); await sleep(400); await shot('tab-weather-water') } await ev(`document.querySelectorAll('[role=tab].cy-tab')[0].click()`); await sleep(500) })
    }
    await quiet(async () => { await ev(`document.querySelector('[data-role=settings-open]').click()`); await sleep(300); await ev(`document.querySelector('[data-role=help-open]').click()`); await sleep(1200); await snap('help', c); await clickText('/Close/'); await sleep(400) })
    // the More items
    await quiet(async () => {
      if (w <= 800) await ev(`[...document.querySelectorAll('.nw-toggle')].find((x) => /Open Control Panel|Hide/.test(x.innerText || x.getAttribute('aria-label') || ''))?.click()`)
      await sleep(400)
      await clickText('/^More/', 'button'); await sleep(500); await snap('more', c); await shot('more')
      for (const s of ['Known limits', 'Field checks', 'Data credits', 'Dataset version']) { await quiet(async () => { await clickText(new RegExp('^' + s), 'button'); await sleep(500); await snap('more-' + s, c) }) }
    })
    // the landing slides
    await quiet(async () => {
      await ev(`localStorage.removeItem('nw_last_visit')`); await ev('location.reload()'); await sleep(3500)
      for (let i = 0; i < 3; i++) { await sleep(900); await snap("landing-" + (i + 1), c); if (i < 2) { await ev(`document.querySelector('[data-role=ln-next]').click()`); await sleep(1300) } }
    })
  }
}

// ------------------------------------------------------------------------------------------------ report
const small = rows.filter((r) => r.size < 12)
const weak = rows.filter((r) => r.ratio < (r.large ? 3 : 4.5))
const group = (list) => {
  const m = new Map()
  for (const r of list) {
    const k = r.sel
    const e = m.get(k) ?? { sel: k, n: 0, worst: 99, size: r.size, states: new Set(), sample: r.text }
    e.n++; e.worst = Math.min(e.worst, r.ratio); e.size = Math.min(e.size, r.size); e.states.add(`${r.theme}/${r.w}/${r.state}`)
    m.set(k, e)
  }
  return [...m.values()].sort((a, b2) => b2.n - a.n)
}
const BAD_LAYOUT = ['clipped', 'hscroll', 'sticks-out', 'overlap', 'see-through']
const lay = layoutRows.filter((r) => BAD_LAYOUT.includes(r.kind))
const layGroup = new Map()
for (const r of lay) { const k = `${r.kind}  ${r.sel}`; const e = layGroup.get(k) ?? { n: 0, sample: r.text, w: r.w, sw: r.sw, where: new Set() }; e.n++; e.where.add(`${r.theme}/${r.w0 ?? r.w}/${r.state}`); layGroup.set(k, e) }
const layLines = [...layGroup].sort((a, b2) => b2[1].n - a[1].n).slice(0, 40).map(([k, e]) => `${String(e.n).padStart(4)}  ${k}  (${e.w}/${e.sw})  e.g. "${e.sample}"  [${[...e.where].slice(0, 3).join('; ')}]`)
const g1 = group(small)
const g2 = group(weak)
const line = (g) => `${String(g.n).padStart(4)}  ${g.sel}  (min ratio ${g.worst}, min size ${g.size}px)  e.g. "${g.sample}"  [${[...g.states].slice(0, 3).join('; ')}${g.states.size > 3 ? '…' : ''}]`
const report = [
  `text nodes audited: ${rows.length}  (themes ${THEMES.join(',')}  widths ${WIDTHS.join(',')})`,
  `below 12 px: ${small.length} nodes in ${g1.length} selectors`,
  `below AA contrast: ${weak.length} nodes in ${g2.length} selectors (${weak.filter((r) => r.grad).length} of them on a gradient: approximate)`,
  `layout problems (clipped text, scrollbars in panels, boxes sticking out, overlaps, see-through sticky bars): ${lay.length} in ${layGroup.size} groups`,
  '', '--- below 12 px', ...g1.slice(0, 40).map(line), '', '--- below AA', ...g2.slice(0, 60).map(line), '', '--- layout', ...layLines,
].join('\n')
writeFileSync(`${OUT}/contrast_audit.txt`, report + '\n')
console.log(report)
b.log.push({ ok: small.length === 0 && weak.length === 0 && lay.length === 0, name: 'no text below 12 px, none below AA, no layout problems' })
if (!CI) b.log[0].ok = true
await b.done('contrast_audit')
