import test from 'node:test'
import assert from 'node:assert/strict'
import { featureAt, geometryBbox, geometryContains, polygonFromVertices } from './geo.js'

const square = polygonFromVertices([[14.0, 121.0], [14.0, 121.1], [14.1, 121.1], [14.1, 121.0]])

test('a point inside a polygon is found, a point outside is not', () => {
  assert.equal(geometryContains(square, 121.05, 14.05), true)
  assert.equal(geometryContains(square, 121.2, 14.05), false)
  assert.equal(geometryContains(null, 121.05, 14.05), false)
})

test('a hole is not inside', () => {
  const hole = { type: 'Polygon', coordinates: [square.coordinates[0], [[121.04, 14.04], [121.06, 14.04], [121.06, 14.06], [121.04, 14.06], [121.04, 14.04]]] }
  assert.equal(geometryContains(hole, 121.05, 14.05), false)
  assert.equal(geometryContains(hole, 121.02, 14.02), true)
})

test('featureAt returns the first containing feature or null; the bbox is [minlon, minlat, maxlon, maxlat]', () => {
  const f = { properties: { n: 1 }, geometry: square }
  assert.equal(featureAt([f], 121.05, 14.05), f)
  assert.equal(featureAt([f], 0, 0), null)
  assert.deepEqual(geometryBbox(square), [121.0, 14.0, 121.1, 14.1])
})
