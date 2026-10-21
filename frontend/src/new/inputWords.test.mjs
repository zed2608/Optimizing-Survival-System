import test from 'node:test'
import assert from 'node:assert/strict'
import { otherInputText } from './inputWords.js'

// V2: the words moved to messages.js; these pins use the Taglish words as before, and the English ones are added
test('team decisions and provisional maps are named for what they are', () => {
  assert.equal(otherInputText('team_decision:species_directsource.csv (not a sourced fact)', 'tl'), 'desisyon ng team, hindi sourced na datos (species_directsource.csv)')
  assert.equal(otherInputText('provisional_map:tag_maps_urban.csv', 'tl'), 'pansamantalang mapa ng team, hindi sourced na datos (tag_maps_urban.csv)')
  assert.equal(otherInputText('something else', 'tl'), 'something else')
})

test('English words, no Filipino', () => {
  assert.equal(otherInputText('team_decision:a.csv (not a sourced fact)', 'en'), 'a team decision, not sourced data (a.csv)')
  assert.equal(otherInputText('provisional_map:b.csv', 'en'), 'a provisional map made by the team, not sourced data (b.csv)')
})
