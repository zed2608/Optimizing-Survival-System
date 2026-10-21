// Where the tour popover goes (R1 W3). Pure functions (tested in tourLayout.test.mjs): the popover is placed BESIDE the target, never on top of it and never outside the screen.
//   rect     = the target's box {left, top, width, height} in viewport pixels
//   size     = the popover's box {width, height}
//   viewport = {width, height}
// Wide screens: the first of bottom, top, right, left where the popover fits and does not touch the target (a gap of `gap` px). If none fits, the side with the most room is used and the popover is
// pulled inside the screen; the page scrolls the target away from the popover first (see the host), so this is only the last resort.
// Narrow screens (width < 640): the popover is docked to the bottom or to the top, whichever is on the side AWAY from the target, full width, so the target stays visible next to it.
export const GAP = 12
export const MARGIN = 8
export const PHONE_MAX = 640

const clamp = (v, lo, hi) => Math.max(lo, Math.min(v, hi))
export const overlaps = (a, b) => a.left < b.left + b.width && a.left + a.width > b.left && a.top < b.top + b.height && a.top + a.height > b.top

export function placePopover(rect, size, viewport, gap = GAP) {
  const vw = viewport.width
  const vh = viewport.height
  if (vw < PHONE_MAX) {
    const w = vw - MARGIN * 2
    const h = Math.min(size.height, Math.round(vh * 0.5))
    const targetMid = rect ? rect.top + rect.height / 2 : vh / 2
    const dockBottom = targetMid < vh / 2
    return { placement: dockBottom ? 'dock-bottom' : 'dock-top', left: MARGIN, top: dockBottom ? vh - h - MARGIN : MARGIN, width: w, height: h, docked: true }
  }
  const w = Math.min(size.width, vw - MARGIN * 2)
  const h = Math.min(size.height, vh - MARGIN * 2)
  if (!rect) return { placement: 'center', left: Math.round((vw - w) / 2), top: Math.round((vh - h) / 2), width: w, height: h, docked: false }
  const cx = rect.left + rect.width / 2 - w / 2
  const cy = rect.top + rect.height / 2 - h / 2
  const tries = [
    ['bottom', clamp(cx, MARGIN, vw - w - MARGIN), rect.top + rect.height + gap],
    ['top', clamp(cx, MARGIN, vw - w - MARGIN), rect.top - h - gap],
    ['right', rect.left + rect.width + gap, clamp(cy, MARGIN, vh - h - MARGIN)],
    ['left', rect.left - w - gap, clamp(cy, MARGIN, vh - h - MARGIN)],
  ]
  for (const [placement, left, top] of tries) {
    const box = { left, top, width: w, height: h }
    const inside = left >= MARGIN && top >= MARGIN && left + w <= vw - MARGIN && top + h <= vh - MARGIN
    if (inside && !overlaps(box, { left: rect.left - 2, top: rect.top - 2, width: rect.width + 4, height: rect.height + 4 })) return { placement, left: Math.round(left), top: Math.round(top), width: w, height: h, docked: false }
  }
  // nothing fits cleanly: the side with the most room, pulled inside the screen
  const room = { bottom: vh - (rect.top + rect.height), top: rect.top, right: vw - (rect.left + rect.width), left: rect.left }
  const best = Object.entries(room).sort((a, b) => b[1] - a[1])[0][0]
  const t = tries.find((x) => x[0] === best)
  return { placement: best, left: Math.round(clamp(t[1], MARGIN, vw - w - MARGIN)), top: Math.round(clamp(t[2], MARGIN, vh - h - MARGIN)), width: w, height: h, docked: false }
}

// The part of the screen that stays free for the target when the popover is docked (phone) or placed beside it: used to scroll the target into view.
export function freeBand(popover, viewport) {
  if (!popover) return { top: MARGIN, bottom: viewport.height - MARGIN }
  if (popover.placement === 'dock-bottom') return { top: MARGIN, bottom: popover.top - GAP }
  if (popover.placement === 'dock-top') return { top: popover.top + popover.height + GAP, bottom: viewport.height - MARGIN }
  return { top: MARGIN, bottom: viewport.height - MARGIN }
}
