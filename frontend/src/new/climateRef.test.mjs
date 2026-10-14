// node --test src/new/climateRef.test.mjs : the "Climate and soil (reference only)" section of the Species card (stage C1). The service's answer is faked here with the SAME values as data/config/climate_reference.csv.
import test from 'node:test'
import assert from 'node:assert/strict'
import { TEXT, buildClimate, sourceLine } from './climateRef.js'

const ITEMS = [
  { key: 'annual_rainfall_mm', value: 2574.4, unit: 'mm', source: 'PAGASA Climatological Normals', source_url: 'https://www.pagasa.dost.gov.ph/climate/climatological-normals', station_or_scope: 'Science Garden, Quezon City (the nearest station on the list; NOT San Mateo)', accessed_date: '2026-10-15', status: 'provisional_proxy', note: '' },
  { key: 'climate_type', value: 'Type I (tuyo mula Disyembre hanggang Mayo)', unit: '', source: 'LCCAP 2021-2025, page 11', source_url: '', station_or_scope: 'San Mateo (municipality)', accessed_date: '2026-10-06', status: 'provisional', note: '' },
  { key: 'annual_mean_temperature_c', value: null, unit: 'degC', source: '', source_url: '', station_or_scope: 'San Mateo (municipality)', accessed_date: '2026-10-15', status: 'pending', note: '' },
  { key: 'soil_ph', value: null, unit: 'pH', source: '', source_url: '', station_or_scope: 'San Mateo (municipality)', accessed_date: '2026-10-15', status: 'no_layer', note: '' },
]
const cref = (assessment, lo, hi) => ({ items: ITEMS, rain: { assessment, species_min_mm: lo, species_max_mm: hi, reference_mm: 2574.4 }, temperature: { assessment: 'no_data' }, ph: { assessment: 'no_data' }, scored: false })
const CV = { temp_min_c: 24, temp_max_c: 27, ph_min: 5, ph_max: 7.5, corona_has_type_I: true }
const row = (c, id) => c.rows.find((r) => r.id === id)

test('rain: the species range, the San Mateo reference WITH its station and status, and the honest comparison', () => {
  const fits = buildClimate(cref('fits', 1200, 3000), CV)
  const r = row(fits, 'rain')
  assert.equal(r.species.en, '1200 to 3000 mm a year')
  assert.equal(r.species.fil, '1200 hanggang 3000 mm sa isang taon')
  assert.equal(r.reference.en, '2574.4 mm a year') // the number of the file, not typed here
  assert.match(r.source, /PAGASA Climatological Normals, Science Garden, Quezon City/)
  assert.match(r.source, /NOT San Mateo/)
  assert.equal(r.asOf, '2026-10-15')
  assert.equal(r.status, 'provisional_proxy')
  assert.equal(r.statusWords.fil, 'pansamantalang kapalit')
  assert.equal(r.verdictCode, 'fits')
  assert.match(r.verdict.fil, /^Pasok/)
  assert.equal(row(buildClimate(cref('below', 3000, 5000), CV), 'rain').verdict.fil, 'Mas mababa kaysa saklaw ng species')
  assert.equal(row(buildClimate(cref('above', 250, 2000), CV), 'rain').verdict.fil, 'Mas mataas kaysa saklaw ng species')
  assert.match(row(buildClimate(cref('above', 250, 2000), CV), 'rain').verdict.en, /^Higher than the species range/)
})

test('temperature and pH: the species range is shown, San Mateo says "No data yet", and nothing is compared', () => {
  const c = buildClimate(cref('fits', 1200, 3000), CV)
  for (const id of ['temp', 'ph']) {
    const r = row(c, id)
    assert.equal(r.verdictCode, 'no_data')
    assert.deepEqual(r.verdict, TEXT.noData)
    assert.match(r.reference.fil, /^Walang datos pa/)
    assert.equal(r.source, null)
    assert.equal(r.asOf, null)
  }
  assert.equal(row(c, 'temp').species.en, '24 to 27 °C')
  assert.equal(row(c, 'ph').species.en, '5 to 7.5')
  assert.match(row(c, 'temp').reference.en, /asked from PAGASA/)
  assert.match(row(c, 'ph').reference.en, /no pH map/)
})

test('a species with no rain range, or no reference at all, is "No data yet" and never a verdict', () => {
  assert.equal(row(buildClimate(cref('no_data', null, null), CV), 'rain').verdictCode, 'no_data')
  assert.equal(row(buildClimate(cref('no_data', null, null), CV), 'rain').species, null)
  const noRef = buildClimate({ items: ITEMS.map((i) => (i.key === 'annual_rainfall_mm' ? { ...i, value: null, status: 'pending' } : i)), rain: { assessment: 'no_data', species_min_mm: 1200, species_max_mm: 3000 }, scored: false }, CV)
  assert.equal(row(noRef, 'rain').verdictCode, 'no_data')
  assert.deepEqual(row(noRef, 'rain').reference, TEXT.noData)
  const none = buildClimate(null, CV)
  assert.ok(none.error && none.rows.length === 0 && none.scored === false)
  assert.match(none.notice.fil, /Hindi ito bahagi ng score/)
})

test('the climate type line comes from the file; English says it in English', () => {
  const r = row(buildClimate(cref('fits', 1200, 3000), CV), 'climate')
  assert.equal(r.reference.fil, 'Type I (tuyo mula Disyembre hanggang Mayo)')
  assert.equal(r.reference.en, 'Type I (dry from December to May)')
  assert.match(r.source, /LCCAP 2021-2025/)
  assert.equal(r.verdictCode, null)
  assert.equal(r.species.en, TEXT.type1.en)
  assert.equal(row(buildClimate(cref('fits', 1200, 3000), { ...CV, corona_has_type_I: false }), 'climate').species.en, TEXT.notType1.en)
})

test('the section says it is NOT part of the score and that the nearest station is used', () => {
  const c = buildClimate(cref('fits', 1200, 3000), CV)
  assert.equal(c.scored, false)
  assert.equal(c.notice.fil, 'Hindi ito bahagi ng score. Pinakamalapit na istasyon ang gamit, hindi San Mateo mismo.')
  assert.equal(c.notice.en, 'This is not part of the score. The nearest station is used, not San Mateo itself.')
  assert.equal(c.title.fil, 'Klima at lupa (reference lang)')
  assert.equal(TEXT.provisional.en, 'PROVISIONAL')
  assert.equal(sourceLine(null), null)
})

test('the words: both languages, short, none of the deep words', () => {
  const deep = /istaka|panukat|punla|hanay|pwesto|permission|coordinates|calibrat|satellite|accuracy|compass heading/i
  for (const [k, v] of Object.entries(TEXT)) {
    assert.ok(v.en.length > 1 && v.fil.length > 1, k)
    assert.doesNotMatch(v.en + ' ' + v.fil, deep, k)
    assert.ok(v.en.split(/\s+/).length <= 16 && v.fil.split(/\s+/).length <= 18, `${k} is too long`)
    assert.doesNotMatch(v.en + v.fil, /undefined|null|\[object/, k)
  }
})
