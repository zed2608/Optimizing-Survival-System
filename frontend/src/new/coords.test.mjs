import test from 'node:test'
import assert from 'node:assert/strict'
import { parseCoordinates, utmToLatLon } from './coords.js'

const near = (a, b, tol = 1e-5) => assert.ok(Math.abs(a - b) < tol, `${a} vs ${b}`)

test('decimal with comma, space and no comma', () => {
  for (const s of ['14.69, 121.12', '14.69 121.12', '14.69,121.12', '  14.69 ,  121.12 ', '14.69; 121.12']) {
    const r = parseCoordinates(s)
    assert.equal(r.ok, true, s)
    assert.equal(r.kind, 'latlon')
    near(r.lat, 14.69)
    near(r.lon, 121.12)
  }
})
test('degree signs and N/E letters; swapped order is read when the first number is above 90', () => {
  let r = parseCoordinates('14.69° N, 121.12° E')
  assert.ok(r.ok); near(r.lat, 14.69); near(r.lon, 121.12)
  r = parseCoordinates('121.12E 14.69N')
  assert.ok(r.ok); near(r.lat, 14.69); near(r.lon, 121.12)
  r = parseCoordinates('121.12, 14.69')
  assert.ok(r.ok); near(r.lat, 14.69); near(r.lon, 121.12); assert.match(r.note, /longitude, latitude/)
  r = parseCoordinates('14.69S 121.12W')
  assert.ok(r.ok); near(r.lat, -14.69); near(r.lon, -121.12)
})
test('UTM 51N reproduces a known kit point', () => {
  const r = parseCoordinates('296799.2 1625091.9')
  assert.ok(r.ok); assert.equal(r.kind, 'utm')
  near(r.lat, 14.691844, 2e-5); near(r.lon, 121.112866, 2e-5)
  for (const s of ['296799 1625091', '296799, 1625091', '51N 296799 1625091', '296799 1625091 51N', 'zone 51N 296799 1625091']) assert.ok(parseCoordinates(s).ok, s)
})
test('UTM central meridian and equator are exact', () => {
  const r = utmToLatLon(500000, 0)
  near(r.lat, 0, 1e-9); near(r.lon, 123, 1e-9)
})
test('bad input is rejected with a reason, never guessed', () => {
  for (const s of ['', '   ', 'hello', 'Narra', '832', '14.69', '14.69, ', '14.69, abc', '95, 121', '14.69, 200', '1,2,3', '14.69N 121.12N', '14.69N 121.12',
                   '296799 99999999999', '50N 296799 1625091', '51S 296799 1625091', '50000 1625091']) {
    const r = parseCoordinates(s)
    assert.equal(r.ok, false, `should reject "${s}"`)
    assert.ok(r.reason.length > 10)
  }
  assert.equal(parseCoordinates(null).ok, false)
})
