// Tests of the field pack's maths and rules (node --test fieldpack/core.test.mjs). tests/test_field_pack.py runs this file.
import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const Core = require('./core.js')
const STRINGS = require('./strings.js')

const close = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg || ''} ${a} vs ${b}`)

test('distance: one degree of longitude on the equator, one of latitude, zero, symmetry', () => {
  close(Core.distanceM(0, 0, 0, 1), (6371000 * Math.PI) / 180, 1e-6, 'equator')
  close(Core.distanceM(14, 121, 15, 121), (6371000 * Math.PI) / 180, 1e-6, 'meridian')
  assert.equal(Core.distanceM(14.7, 121.1, 14.7, 121.1), 0)
  close(Core.distanceM(14.7, 121.1, 14.71, 121.12), Core.distanceM(14.71, 121.12, 14.7, 121.1), 1e-9, 'symmetric')
})

test('bearing: north, east, south, west and the compass letters', () => {
  close(Core.bearingDeg(14, 121, 14.001, 121), 0, 1e-6, 'N')
  close(Core.bearingDeg(14, 121, 14, 121.001), 90, 0.01, 'E')
  close(Core.bearingDeg(14, 121, 13.999, 121), 180, 1e-6, 'S')
  close(Core.bearingDeg(14, 121, 14, 120.999), 270, 0.01, 'W')
  assert.deepEqual([0, 44, 46, 90, 135, 225, 315, 359.9, 360].map(Core.compassPoint), ['N', 'NE', 'NE', 'E', 'SE', 'SW', 'NW', 'N', 'N'])
})

test('turn: no heading means no arrow; with a heading the arrow is bearing minus heading', () => {
  assert.equal(Core.turnDeg(90, null), null)
  assert.equal(Core.turnDeg(90, undefined), null)
  assert.equal(Core.turnDeg(90, NaN), null)
  assert.equal(Core.turnDeg(90, 90), 0)
  assert.equal(Core.turnDeg(10, 350), 20)
  assert.equal(Core.turnDeg(350, 10), 340)
})

test('arrival: within the larger of 2 m and the reported accuracy, never more precise than the phone', () => {
  assert.equal(Core.arrival(1.5, 0.5, 7).arrived, true) // accuracy better than 2 m: the 2 m floor applies
  assert.equal(Core.arrival(2.5, 0.5, 7).arrived, false)
  assert.equal(Core.arrival(6, 8, 12.5).arrived, true) // accuracy 8 m: arrived inside 8 m
  assert.equal(Core.arrival(9, 8, 12.5).arrived, false)
  assert.equal(Core.arrival(9, 8, 12.5).radius, 8)
  assert.equal(Core.arrival(4, 3, 7).approximate, false) // accuracy 3 m is better than the 7 m spacing
  assert.equal(Core.arrival(4, 7, 7).approximate, false) // equal is not worse
  assert.equal(Core.arrival(4, 7.1, 7).approximate, true) // worse than the spacing: only approximate
  const u = Core.arrival(1, null, 7) // the phone gave no accuracy
  assert.deepEqual([u.accuracyKnown, u.approximate, u.arrived, u.radius], [false, true, true, 2])
  assert.equal(Core.arrival(3, null, 7).arrived, false)
  assert.equal(Core.arrival(NaN, 5, 7).arrived, false)
})

test('distance label: digits follow the accuracy', () => {
  assert.deepEqual(Core.distanceLabel(23.4, 1), { value: 23, step: 1, text: '23' })
  assert.equal(Core.distanceLabel(23.4, 4).text, 'about 24')
  assert.equal(Core.distanceLabel(23.4, 10).text, 'about 25')
  assert.equal(Core.distanceLabel(23.4, 30).text, 'about 20')
  assert.equal(Core.distanceLabel(23.4, null).text, 'about 25')
  assert.equal(Core.distanceLabel(0.2, 1).text, '0')
  assert.equal(Core.distanceLabel(1, 12).text, 'less than 5') // accuracy 12 m: step 5, so 1 m is not shown as a precise number
  assert.equal(Core.distanceLabel(3, 25).text, 'less than 10')
})

const mkBlock = (ref, n) => ({ ref, n, trees: Array.from({ length: n }, (_, i) => [i + 1, 14.7 + i * 1e-5, 121.1, i, 0]), row: { block_ref: ref, point_id: '7', plan_id: 'plan_x', check_code: 'abcd1234', status: '', trees_planted: '', moved_lat: '', moved_lon: '' } })
const pack = (blocks) => ({ columns: ['block_ref', 'point_id', 'status', 'trees_planted', 'moved_lat', 'moved_lon', 'plan_id', 'check_code'], blocks })

test('next target is the first tree without a record, in order; progress counts', () => {
  const b = mkBlock('AAA-B01', 4)
  const s = Core.emptyState()
  assert.equal(Core.nextTarget(b, s), 1)
  s.trees['AAA-B01:1'] = { s: 'planted', t: '2026-10-13T01:00:00Z' }
  s.trees['AAA-B01:2'] = { s: 'skipped', reason: 'paved', t: '2026-10-13T01:01:00Z' }
  assert.equal(Core.nextTarget(b, s), 3)
  assert.deepEqual(Core.progress(b, s), { n: 4, planted: 1, skipped: 1, todo: 2 })
  s.trees['AAA-B01:3'] = { s: 'planted', t: '2026-10-13T01:02:00Z' }
  s.trees['AAA-B01:4'] = { s: 'planted', t: '2026-10-13T01:03:00Z' }
  assert.equal(Core.nextTarget(b, s), null)
})

test('what a block becomes: planted with a count, a reason, or nothing yet', () => {
  const b = mkBlock('AAA-B01', 3)
  const s = Core.emptyState()
  assert.deepEqual(Core.decide(b, s), { status: '', trees_planted: '', reason: '', note: '' })
  s.trees['AAA-B01:1'] = { s: 'skipped', reason: 'paved', t: 'a' }
  assert.equal(Core.decide(b, s).status, '') // one skipped, two still to do: not decided
  s.trees['AAA-B01:2'] = { s: 'planted', t: 'b' }
  const d = Core.decide(b, s)
  assert.deepEqual([d.status, d.trees_planted, d.reason], ['planted', '1', ''])
  assert.match(d.note, /Trees 1 not planted \(paved\)/)
  const b2 = mkBlock('BBB-B01', 2)
  const s2 = Core.emptyState()
  s2.trees['BBB-B01:1'] = { s: 'skipped', reason: 'rock_or_ledge', t: 'a' }
  s2.trees['BBB-B01:2'] = { s: 'skipped', reason: 'rock_or_ledge', t: 'b' }
  assert.deepEqual(Core.decide(b2, s2), { status: 'rock_or_ledge', trees_planted: '', reason: 'rock_or_ledge', note: 'All 2 trees skipped: rock_or_ledge.' })
  s2.trees['BBB-B01:2'].reason = 'paved'
  assert.equal(Core.decide(b2, s2).status, 'other') // different reasons: "other" with the reasons in the note
})

test('results file: blocks.csv columns first and unchanged, then the extra columns; moved_lat and moved_lon stay empty; quoting works', () => {
  const b = mkBlock('AAA-B01', 2)
  b.row.status = 'should be replaced'
  const s = Core.emptyState()
  s.observer = 'Ana "Nick", Cruz'
  s.trees['AAA-B01:1'] = { s: 'planted', lat: 14.7000012, lon: 121.1000004, acc: 6.04, t: '2026-10-13T01:00:00Z' }
  const lines = Core.exportCsv(pack([b, mkBlock('BBB-B01', 2)]), s, undefined, 'Prototype. GPS accuracy not yet field-tested.').trim().split('\r\n')
  assert.equal(lines.length, 3)
  const header = lines[0].split(',')
  assert.deepEqual(header.slice(0, 8), ['block_ref', 'point_id', 'status', 'trees_planted', 'moved_lat', 'moved_lon', 'plan_id', 'check_code'])
  assert.deepEqual(header.slice(8), Core.EXTRA_COLUMNS)
  assert.match(lines[1], /^AAA-B01,7,planted,1,,,plan_x,abcd1234,/)
  assert.ok(lines[1].includes('"Ana ""Nick"", Cruz"'))
  assert.ok(lines[1].includes('14.700001,121.100000,6'))
  assert.ok(lines[1].includes('1:planted::14.700001:121.100000:6:2026-10-13T01:00:00Z'))
  assert.match(lines[2], /^BBB-B01,7,,,,,plan_x,abcd1234,,,,,,,,,Prototype\. GPS accuracy not yet field-tested\.$/) // not decided: status and trees_planted empty, nothing invented, but the prototype warning travels with every row
})

test('saving: a phone that refuses storage never throws and keeps the marks in memory', () => {
  const store = Core.makeStore(() => { throw new Error('denied') }, 'k')
  const s = store.load()
  assert.deepEqual(s, Core.emptyState())
  s.trees['x:1'] = { s: 'planted' }
  assert.equal(store.save(s), false)
  assert.equal(store.ok, false)
  assert.equal(store.load().trees['x:1'].s, 'planted')
  const mem = {}
  const good = Core.makeStore(() => ({ getItem: (k) => mem[k] || null, setItem: (k, v) => { mem[k] = v } }), 'k')
  assert.equal(good.save(s), true)
  assert.equal(good.load().trees['x:1'].s, 'planted')
  mem.k = '{not json'
  assert.deepEqual(good.load(), s) // broken data: falls back, does not throw
})

test('strings: the reason words of the README exist and nothing is missing a text', () => {
  for (const r of Core.REASONS) assert.ok(STRINGS['reason_' + r], r)
  for (const [k, v] of Object.entries(STRINGS)) assert.ok(typeof v === 'string' && v.length > 0, k)
  assert.equal(STRINGS.banner, 'Prototype. GPS accuracy not yet field-tested.')
})

const away = (a, b) => Math.abs(Core.angleDiff(a, b))

test('angles: signed shortest difference and the 359 to 1 wrap', () => {
  assert.equal(Core.angleDiff(359, 1), 2)
  assert.equal(Core.angleDiff(1, 359), -2)
  assert.equal(Core.angleDiff(10, 190), -180)
  assert.equal(Core.angleDiff(0, 90), 90)
  assert.equal(Core.normDeg(-30), 330)
  assert.equal(Core.normDeg(725), 5)
})

test('smoothing: low-pass on a circle, no spin through 180 when the heading crosses north', () => {
  assert.equal(Core.smoothAngle(null, 123, 0.3), 123)
  assert.equal(Core.smoothAngle(undefined, 400, 0.3), 40)
  let h = 350
  const seen = []
  for (const raw of [352, 355, 358, 1, 3, 5, 359, 2]) { const n = Core.smoothAngle(h, raw, 0.4); seen.push(away(h, n)); h = n }
  assert.ok(Math.max(...seen) < 10, 'never a big jump: ' + seen.join(','))
  let g = 359
  for (let i = 0; i < 40; i++) g = Core.smoothAngle(g, 1, 0.3)
  close(away(g, 1), 0, 0.01, 'converges to 1 through north, not through 180')
  assert.equal(Core.smoothAngle(100, NaN, 0.5), 100)
  assert.equal(Core.smoothAngle(100, 200, 0), 100)
  assert.equal(Core.smoothAngle(100, 200, 1), 200)
})

test('uncertainty: stable compass, shaky compass and GPS heading while walking give different cones', () => {
  close(Core.circularStd([10, 10, 10, 10]), 0, 1e-6, 'identical')
  assert.ok(Core.circularStd([358, 2, 359, 1, 0]) < 3, 'a cluster around north is stable, not spread over 360')
  assert.ok(Core.circularStd([0, 90, 180, 270, 45, 225]) > 60, 'all over the place')
  assert.equal(Core.coneHalfAngle('compass', 3, 0), 28)
  assert.equal(Core.coneHalfAngle('compass', 30, 0), 50)
  assert.equal(Core.coneHalfAngle('gps', 3, 2.5), 12)
  assert.equal(Core.coneHalfAngle('gps', 3, 1.0), 18)
  assert.equal(Core.coneHalfAngle('none', 0, 0), null)
  assert.ok(Core.coneHalfAngle('gps', 3, 2.5) < Core.coneHalfAngle('compass', 3, 0), 'GPS heading while moving is narrower than the compass')
  assert.match(Core.conePath(40, 40, 36, 28), /^M 40 40 L [\d.]+ [\d.]+ A 36 36 0 0 1 [\d.]+ [\d.]+ Z$/)
})

test('relative cue: straight ahead, left, right, around, from heading and bearing', () => {
  assert.deepEqual(Core.relativeCue(90, 90), { kind: 'ahead', deg: 0, turn: 0 })
  assert.equal(Core.relativeCue(100, 90).kind, 'ahead') // 10 degrees: still straight ahead
  assert.deepEqual(Core.relativeCue(90, 0), { kind: 'right', deg: 90, turn: 90 })
  assert.deepEqual(Core.relativeCue(90, 180), { kind: 'left', deg: 90, turn: -90 })
  assert.deepEqual(Core.relativeCue(350, 10), { kind: 'left', deg: 20, turn: -20 }) // across north
  assert.deepEqual(Core.relativeCue(10, 350), { kind: 'right', deg: 20, turn: 20 })
  assert.equal(Core.relativeCue(180, 0).kind, 'around')
  assert.equal(Core.relativeCue(90, null), null)
  assert.equal(Core.relativeCue(90, NaN), null)
  assert.equal(Core.relativeCue(80, 40).deg, 40)
})

test('compass heading from device angles: flat phone, upright phone, west and east', () => {
  close(away(Core.compassHeading(0, 0, 0), 0), 0, 1e-6, 'flat, facing north')
  close(away(Core.compassHeading(90, 0, 0), 270), 0, 1e-6, 'flat, turned a quarter turn anticlockwise = facing west')
  close(away(Core.compassHeading(270, 0, 0), 90), 0, 1e-6, 'flat, facing east')
  close(away(Core.compassHeading(180, 0, 0), 180), 0, 1e-6, 'flat, facing south')
  close(away(Core.compassHeading(0, 90, 0), 0), 0, 1e-6, 'upright, back of the phone facing north')
  close(away(Core.compassHeading(90, 90, 0), 270), 0, 1e-6, 'upright, facing west')
  close(away(Core.compassHeading(270, 90, 0), 90), 0, 1e-6, 'upright, facing east')
  close(away(Core.compassHeading(0, 50, 0), 0), 0, 1e-6, 'tilted 50 degrees, facing north')
  close(away(Core.compassHeading(90, 0, 0, 90), 0), 0, 1e-6, 'screen turned 90 degrees adds to the flat heading')
  assert.equal(Core.compassHeading(null, 0, 0), null)
  assert.equal(Core.compassHeading(10, undefined, 0), null)
})

test('heading from an event: iOS compass heading, Android absolute event, relative event gives nothing', () => {
  assert.equal(Core.headingFromEvent({ webkitCompassHeading: 120 }, 0), 120)
  assert.equal(Core.headingFromEvent({ webkitCompassHeading: 350 }, 20), 10)
  close(away(Core.headingFromEvent({ type: 'deviceorientationabsolute', alpha: 270, beta: 0, gamma: 0 }, 0), 90), 0, 1e-6)
  close(away(Core.headingFromEvent({ type: 'deviceorientation', absolute: true, alpha: 90, beta: 0, gamma: 0 }, 0), 270), 0, 1e-6)
  assert.equal(Core.headingFromEvent({ type: 'deviceorientation', absolute: false, alpha: 90, beta: 0, gamma: 0 }, 0), null)
  assert.equal(Core.headingFromEvent({ type: 'deviceorientation', alpha: 90, beta: 0, gamma: 0 }, 0), null)
  assert.equal(Core.headingFromEvent(null, 0), null)
  assert.equal(Core.headingFromEvent({ webkitCompassHeading: NaN, absolute: false }, 0), null)
})
