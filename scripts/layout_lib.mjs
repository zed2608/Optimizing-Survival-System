
// ---------------------------------------------------------------------------------------------------------------------------------------------------------
// The layout half of the audit: text that is cut off, horizontal scrollbars inside panels and cards, boxes that stick out of their card, boxes that overlap each other,
// and sticky / fixed bars with a see-through background (content scrolls under them and shows through). Self-contained like pageAudit (used as source text in the page).
export function layoutAudit() {
  const out = []
  const label = (e) => e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '') + (e.getAttribute('data-role') ? `[${e.getAttribute('data-role')}]` : '')
  const visible = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.05 }
  const PANELS = '.nw-sidebar, .nw-right, .nw-card, .nw-pcard, .nw-page, .nw-fmenu, .set-menu, .ln-card'
  const roots = [...document.querySelectorAll(PANELS)].filter(visible)
  const inRoot = (e) => roots.some((r) => r.contains(e))
  for (const e of document.querySelectorAll('body *')) {
    if (!visible(e) || !inRoot(e) || e.closest('.leaflet-container, svg')) continue
    const s = getComputedStyle(e)
    const r = e.getBoundingClientRect()
    // 1. text cut off by the element's own box (ellipsis is a choice and is reported apart)
    if ((s.overflowX === 'hidden' || s.overflowX === 'clip') && e.scrollWidth > e.clientWidth + 1 && (e.innerText || '').trim() && s.display !== 'inline') {
      const er = e.getBoundingClientRect(); const wide = [...e.querySelectorAll('*')].find((c) => c.getBoundingClientRect().right > er.right + 1 && c.getBoundingClientRect().width > 0)
      out.push({ kind: s.textOverflow === 'ellipsis' ? 'ellipsis' : 'clipped', sel: label(e) + (wide ? ' <- ' + label(wide) : ''), text: (e.innerText || '').trim().slice(0, 40), w: e.clientWidth, sw: e.scrollWidth })
    }
    // 2. a horizontal scrollbar inside a panel or card
    if ((s.overflowX === 'auto' || s.overflowX === 'scroll') && e.scrollWidth > e.clientWidth + 1 && !e.matches('.nw-tabs-v2, .chips, .nw-page')) out.push({ kind: 'hscroll', sel: label(e), text: (e.innerText || '').trim().slice(0, 40), w: e.clientWidth, sw: e.scrollWidth })
    // 3. a box (input, button, strip) that sticks out of the panel or card it is in
    if (/^(INPUT|SELECT|BUTTON|TEXTAREA)$/.test(e.tagName) || e.matches('.nw-months, .nw-chip, .nw-estimate')) {
      const host = e.closest('.nw-step, .nw-card, .nw-pcard, .nw-sidebar, .nw-right-body, .set-menu')
      if (host && host !== e) {
        const h = host.getBoundingClientRect()
        if (r.right > h.right + 1 || r.left < h.left - 1) out.push({ kind: 'sticks-out', sel: label(e), text: (e.value || e.innerText || '').toString().trim().slice(0, 30), w: Math.round(r.right - h.right), sw: Math.round(h.left - r.left) })
      }
    }
    // 4. sticky / fixed bars in a panel need an opaque background
    if ((s.position === 'sticky' || s.position === 'fixed') && !e.closest('.leaflet-container')) {
      const m = s.backgroundColor.match(/rgba?\(([^)]*)\)/)
      const a = m ? (m[1].split(',').length === 4 ? parseFloat(m[1].split(',')[3]) : 1) : 0
      if (a < 0.9 && s.backgroundImage === 'none' && e.getBoundingClientRect().height > 20 && !/(toast|spark|tour|splash)/.test(String(e.className))) out.push({ kind: 'see-through', sel: label(e), text: (e.innerText || '').trim().slice(0, 30), w: 0, sw: 0 })
    }
  }
  // 5. boxes of a panel that overlap each other (children that flow in the normal way)
  for (const host of roots) {
    const kids = [...host.children].filter((k) => visible(k) && ['static', 'relative'].includes(getComputedStyle(k).position))
    for (let i = 0; i < kids.length; i++) {
      for (let j = i + 1; j < kids.length; j++) {
        const a = kids[i].getBoundingClientRect(); const b = kids[j].getBoundingClientRect()
        const w = Math.min(a.right, b.right) - Math.max(a.left, b.left); const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)
        if (w > 4 && h > 4) out.push({ kind: 'overlap', sel: `${label(kids[i])} x ${label(kids[j])}`, text: '', w: Math.round(w), sw: Math.round(h) })
      }
    }
  }
  return out
}

// ---------------------------------------------------------------------------------------------------------------------------------------------------------
// THEME PURITY (R1 W2): no dark pieces inside the light theme and no light pieces inside the dark theme. A "large surface" is a visible box of at least 120 x 40 px with its own background.
// In light a large surface must not be dark (luminance < 0.25 fails); in dark it must not be light (luminance > 0.75 fails). Not checked (each with its reason):
//   the map and everything on it (map imagery is light / satellite in both themes), the weather hero (an illustration of the sky with its own scrim), buttons / tabs / radios / inputs (primary and
//   selected states are coloured on purpose), QR codes and the white sheet of a field-kit preview (paper), the tour spotlight layer (a dimmer, not a surface).
export function purityAudit(theme) {
  const parse = (s) => { const m = s.match(/rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:[ ,/]+([\d.]+%?))?\s*\)/); if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : m[4].endsWith('%') ? parseFloat(m[4]) / 100 : +m[4] }; const c = s.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+%?))?\s*\)/); if (c) return { r: +c[1] * 255, g: +c[2] * 255, b: +c[3] * 255, a: c[4] === undefined ? 1 : c[4].endsWith('%') ? parseFloat(c[4]) / 100 : +c[4] }; return { r: 0, g: 0, b: 0, a: 0 } }
  const over = (t, b) => { const a = t.a + b.a * (1 - t.a); return a === 0 ? { r: 0, g: 0, b: 0, a: 0 } : { r: (t.r * t.a + b.r * b.a * (1 - t.a)) / a, g: (t.g * t.a + b.g * b.a * (1 - t.a)) / a, b: (t.b * t.a + b.b * b.a * (1 - t.a)) / a, a } }
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b) }
  const SKIP = '.leaflet-container, .wx-hero, button, [role=button], [role=tab], [role=radio], [role=switch], input, select, textarea, label, summary, canvas, svg, img, video, .nw-qr, [data-paper], .tour-hole, .cy-tab-hl, .cy-splash, .set-switch, .nw-checklist .nw-check'
  const label = (e) => e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '') + (e.getAttribute('data-role') ? `[${e.getAttribute('data-role')}]` : '')
  const out = []
  for (const e of document.querySelectorAll('body *')) {
    const r = e.getBoundingClientRect()
    if (r.width < 120 || r.height < 40) continue
    const cs = getComputedStyle(e)
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) < 0.3) continue
    if (e.closest(SKIP)) continue
    const own = parse(cs.backgroundColor)
    if (own.a < 0.6) continue
    // composite over the ancestors up to an opaque one
    const layers = [own]
    let cum = 1
    for (let p = e.parentElement; p; p = p.parentElement) { const ps = getComputedStyle(p); const bg = parse(ps.backgroundColor); if (bg.a > 0) layers.push({ ...bg, a: bg.a * cum }); if (bg.a >= 0.99) break; cum *= parseFloat(ps.opacity) }
    let base = { r: 255, g: 255, b: 255, a: 1 }
    for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base)
    const L = lum(base)
    if (theme === 'light' ? L < 0.25 : L > 0.75) out.push({ kind: 'impure-' + theme, sel: label(e), text: (e.innerText || '').trim().slice(0, 40), w: Math.round(r.width), sw: Math.round(r.height), lum: +L.toFixed(2) })
  }
  return out
}
