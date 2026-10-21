
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
      out.push({ kind: s.textOverflow === 'ellipsis' ? 'ellipsis' : 'clipped', sel: label(e), text: (e.innerText || '').trim().slice(0, 40), w: e.clientWidth, sw: e.scrollWidth })
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
