import test from 'node:test'
import assert from 'node:assert/strict'
import { compareMeasured, parsePhInput, phRowFromRef, planPhLine, planPhSummary, PH_TEXT } from './phEvidence.js'

const REF = { status: 'sourced', verdict_kind: 'tolerance', verdict_min: 5, verdict_max: 7.5, tol_min: 5, tol_max: 7.5, opt_min: 5.5, opt_max: 6.5, listed_min: null, listed_max: null, source_url: 'https://x.org/a', source_rank: 3, source_name: 'FAO EcoCrop', conflict: false, scope: 'species' }
const OPT_ONLY = { status: 'sourced', verdict_kind: 'optimal_only', verdict_min: 5, verdict_max: 6.5, tol_min: null, tol_max: null, opt_min: 5, opt_max: 6.5, listed_min: null, listed_max: null, source_url: 'https://x.org/b', source_rank: 1, conflict: false, scope: 'genus_or_group' }
const LISTED = { status: 'sourced', verdict_kind: 'listed', verdict_min: 5, verdict_max: 7.5, tol_min: null, tol_max: null, opt_min: null, opt_max: null, listed_min: 5, listed_max: 7.5, source_url: 'https://x.org/c', source_rank: 3, conflict: true, scope: 'species' }
const NONE = { status: 'none', verdict_kind: 'none' }

test('parsePhInput: comma or dot, 3.0 to 10.0, nothing else', () => {
  assert.equal(parsePhInput('6.5'), 6.5)
  assert.equal(parsePhInput('6,5'), 6.5)
  assert.equal(parsePhInput(' 10 '), 10)
  assert.equal(parsePhInput('3'), 3)
  for (const bad of ['', 'abc', '2.9', '10.1', '6.5.1', '-5', '6,5,1']) assert.equal(parsePhInput(bad), null, bad)
})

test('compareMeasured: all five answers', () => {
  assert.equal(compareMeasured(6, REF), 'optimal')
  assert.equal(compareMeasured(5.5, REF), 'optimal') // the limits count as inside
  assert.equal(compareMeasured(5.2, REF), 'tolerated')
  assert.equal(compareMeasured(7.5, REF), 'tolerated')
  assert.equal(compareMeasured(4.9, REF), 'outside')
  assert.equal(compareMeasured(8, REF), 'outside')
  assert.equal(compareMeasured(6, LISTED), 'listed')
  assert.equal(compareMeasured(8, LISTED), 'outside')
  assert.equal(compareMeasured(6, OPT_ONLY), 'optimal')
  assert.equal(compareMeasured(8, OPT_ONLY), 'outside_optimal')
  assert.equal(compareMeasured(6, NONE), 'none')
  assert.equal(compareMeasured(6, null), 'none')
  assert.equal(compareMeasured(null, REF), 'none')
})

test('phRowFromRef: with a range, no range, conflict, group', () => {
  const a = phRowFromRef(REF)
  assert.equal(a.none, false)
  assert.deepEqual(a.lines.map((l) => [l.key, l.range]), [['tolerance', '5–7.5'], ['optimal', '5.5–6.5']])
  assert.equal(a.tag.fil, 'mula sa sanggunian; hindi pa pirmado ng agriculturist')
  assert.equal(a.source.rank, 3)
  const b = phRowFromRef(NONE)
  assert.equal(b.none, true)
  assert.equal(b.source, null)
  assert.equal(b.text.fil, 'Walang nakumpirmang pH range')
  assert.equal(phRowFromRef(null).none, true)
  assert.equal(phRowFromRef(LISTED).conflict, true)
  assert.equal(phRowFromRef(OPT_ONLY).group, true)
  assert.deepEqual(phRowFromRef(OPT_ONLY).lines.map((l) => l.key), ['optimal'])
})

test('plan lines and the summary', () => {
  assert.equal(planPhLine(REF).text.fil, 'pH: 5–7.5 (sanggunian) · sukatin sa lugar')
  assert.equal(planPhLine(NONE).text.fil, 'pH: walang nakumpirmang range')
  const all = { 1: REF, 2: NONE, 3: NONE }
  const s = planPhSummary([1, 2, 3, 3], all)
  assert.equal(s.count, 2)
  assert.equal(s.total, 3)
  assert.equal(s.text.fil, '2 sa 3 na species sa planong ito ay walang nakumpirmang pH range')
  assert.equal(planPhSummary([1], all), null)
  assert.equal(planPhSummary([], all), null)
})

test('wording never claims verification', () => {
  const blob = JSON.stringify(PH_TEXT).toLowerCase()
  for (const w of ['kinumpirma', 'ligtas', ' tama', 'safe']) assert.ok(!blob.includes(w), w)
  assert.ok(!/(?<!not yet |hindi pa )verified/.test(blob))
})

import { areaPhSummary, areaPhText } from './phEvidence.js'

test('area pH lines: a text for every verdict code the service sends, and the area summary', () => {
  for (const c of ['inside', 'outside', 'outside_optimal', 'uncertain', 'no_value', 'no_confirmed_range', 'no_range']) assert.match(areaPhText(c), /^pH: /)
  assert.equal(areaPhText('nonsense'), null)
  assert.match(areaPhSummary({ mean: 5.75, q05: 4.25, q95: 7.5 }), /mga 5\.8 \(posibleng 4\.3–7\.5\).*hindi sinukat/)
  assert.match(areaPhSummary(null), /Walang pH estimate/)
  assert.ok(!/verified|ligtas|tama/i.test(areaPhText('inside') + areaPhSummary(null)))
})
