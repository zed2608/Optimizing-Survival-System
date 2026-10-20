import test from 'node:test'
import assert from 'node:assert/strict'
import { STEP_TITLES, canGoNext, canJump, flowSteps } from './flowState.js'

const base = { selNames: [], where: { kind: 'all', name: '' }, whereLabel: '', planAreaLabel: '', planCreated: false }

test('four steps with their titles', () => {
  const s = flowSteps(base)
  assert.equal(s.length, 4)
  assert.deepEqual(s.map((x) => x.title), STEP_TITLES)
})

test('step 1 needs a species; the reason is plain words; the summary names them', () => {
  const s = flowSteps(base)
  assert.equal(s[0].done, false)
  assert.match(s[0].requirement, /Pumili muna ng kahit isang species/)
  assert.deepEqual(canGoNext(s, 1), { ok: false, reason: s[0].requirement })
  const t = flowSteps({ ...base, selNames: ['Narra', 'Duhat', 'Kamagong', 'Apitong'] })
  assert.equal(t[0].summary, 'Narra, Duhat at 2 pa')
  assert.equal(flowSteps({ ...base, selNames: ['Narra'] })[0].summary, 'Narra')
})

test('step 2: the whole municipality is enough; a barangay or zone needs a name', () => {
  const s = flowSteps({ ...base, selNames: ['Narra'] })
  assert.equal(s[1].done, true)
  assert.equal(s[1].summary, 'Buong San Mateo')
  const b = flowSteps({ ...base, selNames: ['Narra'], where: { kind: 'barangay', name: '' } })
  assert.equal(b[1].done, false)
  assert.match(b[1].requirement, /barangay/)
  assert.equal(canGoNext(b, 2).ok, false)
  const z = flowSteps({ ...base, selNames: ['Narra'], where: { kind: 'zone', name: 'Forest Zone' }, whereLabel: 'Forest Zone' })
  assert.equal(z[1].done, true)
  assert.equal(z[1].summary, 'Forest Zone')
})

test('step 3 needs an area for the plan; the summary says which; step 4 follows only when 1 to 3 are done', () => {
  const s = flowSteps({ ...base, selNames: ['Narra'] })
  assert.equal(s[2].done, false)
  assert.match(s[2].requirement, /markahan/)
  assert.equal(canGoNext(s, 3).ok, false)
  const d = flowSteps({ ...base, selNames: ['Narra'], planAreaLabel: 'Iginuhit na area' })
  assert.equal(d[2].summary, 'Iginuhit na area')
  assert.deepEqual(canGoNext(d, 3), { ok: true, reason: '' })
  assert.equal(canGoNext(d, 1).ok, true)
})

test('the stepper may jump only to a reachable step', () => {
  const s = flowSteps({ ...base, selNames: ['Narra'] })
  assert.equal(canJump(s, 1), true)
  assert.equal(canJump(s, 2), true)
  assert.equal(canJump(s, 3), true)
  assert.equal(canJump(s, 4), false)
  assert.equal(canJump(flowSteps(base), 2), false)
})
