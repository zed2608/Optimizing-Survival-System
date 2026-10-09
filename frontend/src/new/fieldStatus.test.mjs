import test from 'node:test'
import assert from 'node:assert/strict'
import { FIELD_CLASSES, FIELD_ORDER, fieldClass, fieldColor, fieldIcon } from './fieldStatus.js'
import { readFileSync } from 'node:fs'
import { FIELD_TABLE } from './fieldStatusTable.js'
import { ZONE_TABLE } from './zoneColorsTable.js'
import { ZONE_COLORS, conditionText, legendOrder, needsPermission, zoneColor } from './zoneColors.js'

test('field status classes: the colours and icons of the request', () => {
  assert.deepEqual(FIELD_ORDER, ['planted', 'verified', 'recheck', 'not_plantable', 'water', 'hard'])
  assert.equal(fieldClass('planted'), 'planted')
  assert.equal(fieldClass('verified_plantable'), 'verified')
  assert.equal(fieldClass('needs_recheck'), 'recheck')
  assert.equal(fieldClass('not_plantable', 'too_steep'), 'not_plantable')
  assert.equal(fieldClass('not_plantable', 'creek_or_waterlogged'), 'water')
  for (const r of ['paved', 'building', 'rock_or_ledge']) assert.equal(fieldClass('not_plantable', r), 'hard')
  assert.equal(fieldClass('not_plantable', 'other'), 'not_plantable')
  assert.equal(fieldIcon('planted'), 'check')
  assert.equal(fieldIcon('verified'), 'ring')
  assert.equal(fieldIcon('recheck'), 'question')
  assert.equal(fieldIcon('not_plantable'), 'close')
  assert.equal(fieldIcon('water'), 'close')
  assert.equal(fieldIcon('hard'), 'close')
  const hex = (c) => /^#[0-9a-f]{6}$/i.test(c)
  assert.ok(FIELD_ORDER.every((k) => hex(fieldColor(k))))
  assert.equal(new Set(FIELD_ORDER.map(fieldColor)).size, 6)                                  // six different colours
  // green for planted and verified, amber for recheck, red for not plantable, blue for water, gray for paved / building / rock
  const rgb = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16))
  const [pr, pg] = rgb(fieldColor('planted'))
  assert.ok(pg > pr)
  assert.ok(rgb(fieldColor('not_plantable'))[0] > 200 && rgb(fieldColor('not_plantable'))[1] < 80)
  assert.ok(rgb(fieldColor('water'))[2] > 200)
  const [gr, gg, gb] = rgb(fieldColor('hard'))
  assert.ok(Math.abs(gr - gg) < 12 && Math.abs(gg - gb) < 12)
  assert.ok(Object.values(FIELD_CLASSES).every((c) => c.label.length > 3))
})

test('zone colours follow the MPDC standard colours of the request', () => {
  const rgb = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16))
  const isGreen = (c) => { const [r, g, b] = rgb(c); return g >= r && g > b }
  for (const z of ['Forest Zone', 'Agricultural Zone', 'Buffer Zone', 'Parks and Recreation Zone', 'Special Reserved Zone']) assert.ok(isGreen(zoneColor(z)), z)
  assert.ok(rgb(zoneColor('Agricultural Zone'))[1] > rgb(zoneColor('Forest Zone'))[1])                    // lighter
  assert.ok(rgb(zoneColor('Special Reserved Zone'))[1] < rgb(zoneColor('Forest Zone'))[1])                 // darker
  for (const z of ['High Density Residential - Mixed Use Zone', 'Medium Density Residential Zone', 'Socialized Housing Zone']) { const [r, g, b] = rgb(zoneColor(z)); assert.ok(r > 150 && g > 110 && b < 100, z) }
  for (const z of ['Institutional Research Zone', 'General Institutional Zone', 'General Institutional Zonec']) assert.equal(zoneColor(z), zoneColor('Institutional Research Zone'))
  assert.ok(rgb(zoneColor('Institutional Research Zone'))[2] > 180)
  assert.ok(rgb(zoneColor('Medium Industrial Zone'))[0] > 90 && rgb(zoneColor('Medium Industrial Zone'))[2] > 120)
  assert.ok(rgb(zoneColor('Light Industrial Zone')).every((v) => v > 140))
  assert.equal(zoneColor('Minor Commercial - Mixed Use Zone'), zoneColor('Major Commercial Zone'))
  assert.ok(rgb(zoneColor('Major Commercial - Mixed Use Zone'))[0] < rgb(zoneColor('Major Commercial Zone'))[0])
  for (const z of ['Cemetery Zone', 'Quarry Sub-Zone', 'Sanitary Landfill']) assert.equal(zoneColor(z), zoneColor('Quarry Sub-Zone'))
  assert.equal(Object.keys(ZONE_COLORS).length, 19)
  assert.equal(zoneColor('A zone nobody listed'), '#9e9e9e')
})

test('zone legend order and condition words', () => {
  const f = (n) => ({ properties: { name: n } })
  assert.deepEqual(legendOrder([f('Quarry Sub-Zone'), f('Forest Zone'), f('Buffer Zone'), f('Zzz')]).map((x) => x.properties.name), ['Forest Zone', 'Buffer Zone', 'Quarry Sub-Zone', 'Zzz'])
  assert.equal(conditionText('needs permission (private land)'), 'Needs permission (private land)')
  assert.ok(needsPermission('needs permission (private land)') && needsPermission('needs DENR permission') && needsPermission('inside Forest Reserve: MENRO/DENR permit'))
  assert.ok(!needsPermission('may be converted to other use') && !needsPermission(''))
})

test('the JSON files that Python reads are the same data as the modules of the browser', () => {
  const read = (f) => JSON.parse(readFileSync(new URL(f, import.meta.url), 'utf-8'))
  assert.deepEqual(read('./fieldStatus.json'), FIELD_TABLE)
  assert.deepEqual(read('./zoneColors.json'), ZONE_TABLE)
})
