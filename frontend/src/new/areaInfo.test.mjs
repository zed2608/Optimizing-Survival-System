import test from 'node:test'
import assert from 'node:assert/strict'
import { barangaysOfShape, continueState, describeArea, geometryHectares, haText, polygonHectares } from './areaInfo.js'
import { polygonFromVertices } from './geo.js'

const LAT = 14.69
const D = 100 / 111320 // 100 m in degrees of latitude
const DLON = D / Math.cos((LAT * Math.PI) / 180)
const SQUARE = [[LAT, 121.1], [LAT + D, 121.1], [LAT + D, 121.1 + DLON], [LAT, 121.1 + DLON]]
const feat = (name, display, x0, y0, x1, y1) => ({ properties: { name, display_name: display }, geometry: { type: 'Polygon', coordinates: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]] } })
const BR = [feat('A', 'Maly', 121.0, 14.6, 121.15, 14.8), feat('B', 'Sto Nino', 121.15, 14.6, 121.3, 14.8)]

test('polygonHectares: a 100 m square is about 1 hectare, fewer than 3 corners is 0', () => {
  assert.ok(Math.abs(polygonHectares(SQUARE) - 1) < 0.02)
  assert.ok(Math.abs(geometryHectares(polygonFromVertices(SQUARE)) - 1) < 0.02)
  assert.equal(polygonHectares([[1, 1], [1, 2]]), 0)
  assert.equal(haText(1.04), '1 ektarya'.replace('1 ', '1 '))
  assert.equal(haText(12.34), '12 ektarya')
})

test('barangaysOfShape: judged from the corners and the middle', () => {
  const g = polygonFromVertices([[14.7, 121.14], [14.7, 121.16], [14.71, 121.16], [14.71, 121.14]])
  assert.deepEqual(barangaysOfShape(g, BR).sort(), ['Maly', 'Sto Nino'])
  assert.deepEqual(barangaysOfShape(polygonFromVertices(SQUARE), BR), ['Maly'])
  assert.deepEqual(barangaysOfShape(polygonFromVertices(SQUARE), []), [])
})

test('describeArea: point, barangay, zone and drawn shape each say how, what name and what kind', () => {
  const b = describeArea({ tool: 'barangay', area: { kind: 'barangay', name: 'A' }, barangayFeatures: BR, squares: 42 })
  assert.deepEqual(b.map((r) => r.label), ['Paraan', 'Pangalan', 'Uri', 'Mga planting square'])
  assert.equal(b[1].value, 'Maly')
  const z = describeArea({ tool: 'barangay', area: { kind: 'zone', name: 'Forest Zone' }, barangayFeatures: BR })
  assert.equal(z[1].value, 'Forest Zone')
  const p = describeArea({ tool: 'draw', area: { kind: 'polygon', geometry: polygonFromVertices(SQUARE) }, barangayFeatures: BR, squares: 1, selection: 'touching' })
  assert.ok(p.some((r) => r.label === 'Barangay' && r.value.startsWith('Maly')))
  assert.ok(p.some((r) => r.label === 'Laki ng iginuhit' && /ektarya/.test(r.value)))
  assert.ok(p.some((r) => r.label === 'Paalala' && /tinatamaan/.test(r.value)))
  const s = describeArea({ tool: 'point', area: null, spot: { lat: 14.7, lon: 121.05 }, barangayFeatures: BR, zoneFeatures: [feat('Agricultural Zone', 'x', 121.0, 14.6, 121.2, 14.8)] })
  assert.deepEqual(s.map((r) => r.label), ['Paraan', 'Barangay', 'Zone', 'Uri'])
  assert.equal(s[1].value, 'Maly')
  assert.equal(describeArea({ tool: 'point', area: null, spot: null }).length, 0)
})

test('continueState: no area, an empty area and a loading check keep Continue off; species mode and a good area let it on', () => {
  assert.equal(continueState({ mode: 'species', area: null, areaRank: null }).ok, true)
  assert.equal(continueState({ mode: 'area', area: null, areaRank: null }).ok, false)
  const empty = continueState({ mode: 'area', area: { kind: 'polygon' }, areaRank: { status: 'error', error: { status: 400, message: 'The area contains no legal-zone grid points (it may lie outside San Mateo)' } } })
  assert.equal(empty.ok, false)
  assert.match(empty.reason, /Walang planting square/)
  assert.equal(continueState({ mode: 'area', area: { kind: 'polygon' }, areaRank: { status: 'loading' } }).ok, false)
  assert.equal(continueState({ mode: 'area', area: { kind: 'barangay', name: 'A' }, areaRank: { status: 'ok' } }).ok, true)
  assert.equal(continueState({ mode: 'area', area: { kind: 'barangay', name: 'A' }, areaRank: { status: 'error', error: { status: 500, message: 'x' } } }).ok, true)
})
