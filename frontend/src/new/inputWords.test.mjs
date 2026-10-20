import test from 'node:test'
import assert from 'node:assert/strict'
import { otherInputText } from './inputWords.js'

test('team decisions and provisional maps are named for what they are', () => {
  assert.equal(otherInputText('team_decision:species_directsource.csv (not a sourced fact)'), 'desisyon ng team, hindi sourced na datos (species_directsource.csv)')
  assert.equal(otherInputText('provisional_map:tag_maps_urban.csv'), 'pansamantalang mapa ng team, hindi sourced na datos (tag_maps_urban.csv)')
  assert.equal(otherInputText('something else'), 'something else')
})
