import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { GROUND_FLAGS, W_GOOD, W_MODERATE, matchLevel, matchText, plainFlag, plainWarning, verdictSentence } from './plainWords.js'

// Every warning the service can produce (pipeline/palettes.py, pipeline/run_plan.py, api_v2.py), word for word.
const API_WARNINGS = [
  'palette_smaller_than_min: 2 species (min 4) satisfy the rules for this area',
  'no species can be placed in this area',
  'caps_cannot_absorb_all_saplings: 40 of 100 saplings allocated (per-species/genus caps or eligible points)',
  'Single species planting: high pest and disease risk',
  'Single species planting: higher pest and disease risk',
  'Mostly one species: higher pest risk',
  'Only 2 species: low diversity, higher pest risk',
  'Only 4 species: low diversity, higher pest risk',
  'Caps relaxed: The per-species and per-genus caps were raised to the minimum needed to place every sapling with only these species.',
  'Caps relaxed: You chose the tree count of every species, so the per-species and per-genus caps do not apply.',
  'You chose the tree count of every species, so the per-species and per-genus caps do not apply.',
  'season: the species of this palette do not share a planting month inside the window (season_filter=mark does not change the palette)',
  'season: the species of this mix do not share a planting month inside the window',
  'Every species is out of season between 7 Oct and 6 Nov, so no plan can be made. Change the dates, or send season_filter=mark to plan anyway and see the season labels.',
  'None of your chosen species can be planted between 7 Oct and 6 Nov (all are outside their best months). Change the dates, choose other species, or send season_filter=mark.',
  'dioecious_species_needs_both_sexes_quota',
  'spacing_missing_cannot_plan_in_blocks',
  'zoning_unconfirmed',
]
const BAD = /[a-z]+_[a-z]+|=/

test('no visible warning keeps an underscore or an equals sign', () => {
  for (const w of API_WARNINGS) {
    const p = plainWarning(w)
    assert.ok(p.length > 3, w)
    assert.ok(!BAD.test(p), `${w}  ->  ${p}`)
  }
})

test('the known warnings are rewritten as plain sentences', () => {
  assert.equal(plainWarning('Single species planting: higher pest and disease risk'), 'Only one species: a higher risk of pests and disease.')
  assert.equal(plainWarning('Mostly one species: higher pest risk'), 'Mostly one species: a higher risk of pests.')
  assert.match(plainWarning('Caps relaxed: The per-species and per-genus caps were raised...'), /bigger share of the trees than usual/)
  assert.match(plainWarning('season: the species of this palette do not share a planting month inside the window (season_filter=mark does not change the palette)'), /no planting month in common inside your dates/)
  assert.match(plainWarning('palette_smaller_than_min: 2 species (min 4) satisfy the rules'), /Only 2 species suit this area, fewer than the 4/)
  assert.match(plainWarning('caps_cannot_absorb_all_saplings: 40 of 100 saplings allocated (x)'), /Only 40 of 100 trees could be shared out/)
  assert.match(plainWarning('Every species is out of season between 7 Oct and 6 Nov, so no plan can be made. Change the dates, or send season_filter=mark to plan anyway and see the season labels.'), /Show all species/)
})

test('flags are plain words, the same as the field kit', () => {
  const codes = ['soil_provisional', 'ground_built_up', 'ground_bare', 'ground_water', 'zoning_unconfirmed', 'needs_both_sexes', 'soil_unverified_mismatch', 'species_data_unverified', 'low_confidence', 'barangay_nearest', 'some_new_flag']
  for (const c of codes) assert.ok(!BAD.test(plainFlag(c)), c + ' -> ' + plainFlag(c))
  assert.equal(plainFlag('ground_built_up'), 'Looks built-up in the satellite land cover: check on the ground first')
  assert.equal(plainFlag('zoning_unconfirmed'), 'Outside our zoning map: Forest Reserve, coordinate with MENRO and DENR')
  assert.equal(plainFlag('needs_both_sexes'), 'Separate sexes: plant both')
  assert.equal(plainFlag('soil_provisional'), 'Soil from the LGU soil map (provisional)')
  assert.deepEqual(GROUND_FLAGS, ['ground_built_up', 'ground_bare', 'ground_water'])
})

test('match words use the cut-offs of the map colours', () => {
  assert.equal(matchLevel(0.55), 'Good')
  assert.equal(matchLevel(0.5499), 'Fair')
  assert.equal(matchLevel(0.35), 'Fair')
  assert.equal(matchLevel(0.3499), 'Poor')
  assert.equal(matchLevel(null), null)
  assert.equal(matchText(0.774), 'Good · 77%')
  assert.equal(matchText(undefined), 'Data Unavailable')
})

test('the verdict sentence says place, match, season and the ground check in one go', () => {
  const item = { common_name: 'Kamagong', W: 0.77, eligible: true, season: { status: 'in_season' } }
  assert.equal(verdictSentence(item, ['ground_bare']), 'Good place for Kamagong: overall match 77%. In its planting months. Check the ground first.')
  assert.equal(verdictSentence(item, []), 'Good place for Kamagong: overall match 77%. In its planting months.')
  assert.equal(verdictSentence({ ...item, eligible: false }, []), 'Not a suitable place for Kamagong. In its planting months.')
  assert.ok(!BAD.test(verdictSentence(item, ['soil_provisional'])))
})

test('the cut-offs are the ones of the map colours in v2/config.js', () => {
  const cfg = readFileSync(new URL('../v2/config.js', import.meta.url), 'utf-8')
  assert.equal(Number(cfg.match(/W_GOOD\s*=\s*([\d.]+)/)[1]), W_GOOD)
  assert.equal(Number(cfg.match(/W_MODERATE\s*=\s*([\d.]+)/)[1]), W_MODERATE)
})
