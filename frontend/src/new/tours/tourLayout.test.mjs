import test from 'node:test'
import assert from 'node:assert/strict'
import { freeBand, overlaps, placePopover } from './tourLayout.js'

const V = { width: 1280, height: 800 }
const S = { width: 340, height: 200 }
const inScreen = (p, v) => p.left >= 0 && p.top >= 0 && p.left + p.width <= v.width && p.top + p.height <= v.height

test('wide screen: beside the target, inside the screen, never over the target', () => {
  for (const rect of [{ left: 100, top: 100, width: 200, height: 60 }, { left: 900, top: 650, width: 120, height: 40 }, { left: 10, top: 300, width: 300, height: 400 }, { left: 1000, top: 20, width: 260, height: 40 }]) {
    const p = placePopover(rect, S, V)
    assert.ok(inScreen(p, V), JSON.stringify([rect, p]))
    assert.ok(!overlaps(p, rect), JSON.stringify([rect, p]))
  }
})

test('prefers below, then above, then the sides', () => {
  assert.equal(placePopover({ left: 500, top: 100, width: 100, height: 40 }, S, V).placement, 'bottom')
  assert.equal(placePopover({ left: 500, top: 700, width: 100, height: 40 }, S, V).placement, 'top')
  assert.equal(placePopover({ left: 100, top: 20, width: 400, height: 770 }, S, V).placement, 'right')
})

test('phone: docked to the side away from the target, full width', () => {
  const v = { width: 360, height: 740 }
  const top = placePopover({ left: 20, top: 100, width: 100, height: 40 }, S, v)
  assert.equal(top.placement, 'dock-bottom'); assert.equal(top.width, 344)
  const low = placePopover({ left: 20, top: 600, width: 100, height: 40 }, S, v)
  assert.equal(low.placement, 'dock-top')
  for (const p of [top, low]) assert.ok(inScreen(p, v))
  assert.ok(!overlaps(top, { left: 20, top: 100, width: 100, height: 40 }) && !overlaps(low, { left: 20, top: 600, width: 100, height: 40 }))
})

test('no target: centred; the free band excludes the docked popover', () => {
  const p = placePopover(null, S, V)
  assert.equal(p.placement, 'center'); assert.equal(p.left, 470)
  const d = placePopover({ left: 0, top: 50, width: 10, height: 10 }, S, { width: 360, height: 740 })
  const b = freeBand(d, { width: 360, height: 740 })
  assert.ok(b.bottom <= d.top)
})
