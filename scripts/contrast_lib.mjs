// The in-page part of the contrast audit (shared by scripts/contrast_audit.mjs and scripts/fieldpack_shots.mjs): for every visible text node, its font size and its contrast against the effective background.
// Used as source text in the page (pageAudit.toString()), so it must stay self-contained.
export function pageAudit() {
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
    if (!e || seen.has(e) || e.closest('svg, script, style, noscript, .leaflet-container, .sr-only, canvas, [aria-hidden="true"]')) continue
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
