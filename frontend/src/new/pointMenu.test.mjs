import test from 'node:test'
import assert from 'node:assert/strict'
import { distanceM, menuLines } from './pointMenu.js'

const feat = (props, x0, y0, x1, y1) => ({ properties: props, geometry: { type: 'Polygon', coordinates: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]] } })
const BR = [feat({ name: 'GUINAYANG', display_name: 'Guinayang' }, 121.0, 14.6, 121.2, 14.8)]
const ZN = [feat({ name: 'Agricultural Zone' }, 121.0, 14.6, 121.2, 14.8)]
const WIN = { start: '2026-10-20', end: '2026-12-29' }

test('distance: 100 m of latitude is about 100 m, same point is 0', () => {
  assert.equal(Math.round(distanceM(14.7, 121.1, 14.7, 121.1)), 0)
  assert.ok(Math.abs(distanceM(14.7, 121.1, 14.7 + 100 / 111195, 121.1) - 100) < 1)
})

test('menuLines: place, zone, grid number, window, viewing day and the distance from the click', () => {
  const m = menuLines({ square: { lat: 14.7, lon: 121.1, pointId: 1921 }, click: { lat: 14.7 + 1 / 111195, lon: 121.1 }, barangayFeatures: BR, zoneFeatures: ZN, win: WIN, today: '2026-10-20' })
  assert.equal(m.title, 'Guinayang')
  assert.deepEqual(m.lines, ['Guinayang / Agricultural Zone, grid 1921', 'Planting window 20 Oct - 29 Dec 2026, viewed 20 Oct 2026', '1 m from where you clicked'])
})

test('menuLines: outside the outlines and the zoning map, and no distance line when the click is on the centre', () => {
  const m = menuLines({ square: { lat: 10, lon: 120, pointId: 5 }, click: { lat: 10, lon: 120 }, barangayFeatures: BR, zoneFeatures: ZN, win: WIN, today: '2026-10-20' })
  assert.equal(m.lines[0], 'Outside the barangay outlines / Outside our zoning map, grid 5')
  assert.equal(m.lines.length, 2)
})
