import test from 'node:test'
import assert from 'node:assert/strict'
import { FIELD_CLASSES, FIELD_ORDER, fieldClass, fieldColor, fieldIcon } from './fieldStatus.js'
import { readFileSync } from 'node:fs'
import { FIELD_TABLE } from './fieldStatusTable.js'
import { ZONE_TABLE } from './zoneColorsTable.js'
import { ZONE_COLORS, ZONE_CREDIT, ZONE_UNSTYLED_NOTE, conditionText, legendOrder, needsPermission, zoneColor, zoneHatch } from './zoneColors.js'

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
  // UX round 5 (C), user-approved: ONE violet for every mark; the shape is the only difference. (Before: six colours - green, green, amber, red, blue, gray.)
  assert.equal(new Set(FIELD_ORDER.map(fieldColor)).size, 1)
  const rgb = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16))
  const [vr, vg, vb] = rgb(fieldColor('planted'))
  assert.ok(vb > vg && vr > vg && vb > 200, 'a violet: blue and red above green')
  assert.equal(new Set(['planted', 'verified', 'recheck', 'not_plantable'].map(fieldIcon)).size, 4, 'the four statuses differ by shape: check, ring, question mark, cross')
  assert.deepEqual(['planted', 'verified', 'recheck', 'not_plantable', 'water', 'hard'].map((k) => FIELD_CLASSES[k].shape), ['check', 'ring', 'question', 'cross', 'cross', 'cross'])
  // the violet must stay away from the colours that mean something else: score colours (green, orange, red, grey), counted squares (cyan) and the dashed grey
  const dist = (a, b) => Math.hypot(...rgb(a).map((v, i) => v - rgb(b)[i]))
  for (const other of ['#22c55e', '#f59e0b', '#ef4444', '#9ca3af', '#22d3ee', '#e5e7eb']) assert.ok(dist(fieldColor('planted'), other) > 90, other)
  // contrast of the violet against white (light panels) and against the dark panel: both at least 3 for a symbol
  const lum = (c) => { const [r, g, b] = rgb(c).map((v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4 }); return 0.2126 * r + 0.7152 * g + 0.0722 * b }
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05) }
  assert.ok(ratio(fieldColor('planted'), '#ffffff') >= 3, 'on a light panel (a symbol; the words next to it are dark)')
  assert.ok(ratio(fieldColor('planted'), '#1f2937') >= 3, 'on a dark panel')
  assert.ok(Object.values(FIELD_CLASSES).every((c) => c.label.length > 3))
})

test('zone colours follow the LGU style file (Landuse-1.qml)', () => {
  const rgb = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16))
  const want = {
    'Forest Zone': [0, 100, 0], 'Buffer Zone': [50, 225, 50], 'Cemetery Zone': [100, 225, 100], 'Agricultural Zone': [100, 225, 100],
    'Parks and Recreation Zone': [210, 133, 107], 'Quarry Sub-Zone': [153, 51, 0], 'Special Reserved Zone': [190, 190, 190],
    'High Density Residential - Mixed Use Zone': [255, 255, 0], 'Medium Density Residential Zone': [255, 255, 0], 'Socialized Housing Zone': [255, 255, 0],
    'Institutional Research Zone': [0, 0, 255], 'General Institutional Zone': [0, 0, 255], 'General Institutional Zonec': [0, 0, 255],
    'Minor Commercial - Mixed Use Zone': [255, 0, 0], 'Major Commercial Zone': [255, 0, 0],
    'Light Industrial Zone': [150, 0, 200], 'Medium Industrial Zone': [150, 0, 200],
  }
  for (const [z, v] of Object.entries(want)) assert.deepEqual(rgb(zoneColor(z)), v, z)
  // Agricultural has the same green as Cemetery, so only it carries the blue hatch
  assert.equal(zoneColor('Agricultural Zone'), zoneColor('Cemetery Zone'))
  assert.deepEqual(Object.keys(ZONE_COLORS).filter((z) => zoneHatch(z)), ['Agricultural Zone'])
  // zones the LGU file does not style: a distinct dark gray and a dark red, said so in the table
  assert.deepEqual(rgb(zoneColor('Sanitary Landfill')), [77, 77, 77])
  assert.deepEqual(rgb(zoneColor('Major Commercial - Mixed Use Zone')), [139, 0, 0])
  for (const z of ['Sanitary Landfill', 'Major Commercial - Mixed Use Zone']) assert.match(ZONE_COLORS[z].source, /not styled/)
  assert.ok(ZONE_COLORS['Forest Zone'].source.includes('Landuse-1.qml'))
  assert.equal(ZONE_CREDIT, 'Colours follow the LGU style file (Landuse-1.qml)')
  assert.match(ZONE_UNSTYLED_NOTE, /Sanitary Landfill/)
  assert.equal(Object.keys(ZONE_COLORS).length, 19)
  assert.equal(zoneColor('A zone nobody listed'), '#9e9e9e')
  assert.ok(ZONE_TABLE.fill_opacity <= 0.25)                                                   // the fill never hides the dots
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
