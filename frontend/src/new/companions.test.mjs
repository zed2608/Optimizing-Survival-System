import test from 'node:test'
import assert from 'node:assert/strict'
import { chosenIds, companionBody, overlapText } from './companions.js'
import { tr } from './i18n.js'
// V2: the words moved into messages.js (English by default, Taglish through the switch); this test pins the Taglish words as before and adds the English ones
const ASK = tr('sc.ask', {}, 'tl')
const COMPANION_NOTE = tr('sc.note', {}, 'tl')

test('the chosen ids: main first, no repeats, nothing without a main', () => {
  assert.deepEqual(chosenIds(null, [2, 3]), [])
  assert.deepEqual(chosenIds(1, [2, 3, 2, 1]), [1, 2, 3])
  assert.deepEqual(chosenIds(7, []), [7])
})

test('the request body carries the area chosen in step 4, or none', () => {
  assert.equal(companionBody('urban', null, null), null)
  assert.deepEqual(companionBody('urban', 1, null), { species_id: 1, purpose: 'urban' })
  assert.deepEqual(companionBody('urban', 1, { kind: 'barangay', name: 'STA ANA' }), { species_id: 1, purpose: 'urban', barangay: 'STA ANA' })
  assert.deepEqual(companionBody('planting', 1, { kind: 'zone', name: 'Forest Zone' }), { species_id: 1, purpose: 'planting', zone: 'Forest Zone' })
  assert.equal(companionBody('urban', 1, { kind: 'polygon', geometry: { type: 'Polygon' } }).polygon.type, 'Polygon')
})

test('the words: the question, the honest note, and no claim of ecological fit', () => {
  assert.equal(ASK, 'Isang species lang ba o marami?')
  assert.match(COMPANION_NOTE, /Batay lang ito sa parehong angkop na lugar\. Hindi pa kasama ang laki ng canopy, ugat o lilim\./)
  assert.equal(overlapText(0.734, 'tl'), 'angkop din sa 73% ng lugar na angkop sa pangunahing species')
  assert.ok(!/ekolohiya|magkaibigan|bagay sa isa|pairs well/i.test(COMPANION_NOTE + overlapText(0.5, 'tl')))
})

test('English mode shows no Filipino: the same words in English', () => {
  assert.equal(tr('sc.ask', {}, 'en'), 'One species or many?')
  assert.equal(overlapText(0.734, 'en'), 'also suits 73% of the land that suits the main species')
  assert.ok(!/ang |ng |mga |lang /.test(tr('sc.note', {}, 'en')))
})
