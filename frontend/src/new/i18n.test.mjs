import test from 'node:test'
import assert from 'node:assert/strict'
import { LANGS, LANG_KEY, getLang, setLang, tr } from './i18n.js'
import { MESSAGES } from './messages.js'
import { flowSteps } from './flowState.js'
import { diagnosticText, haText } from './areaInfo.js'
import { areaPhSummary, areaPhText, phFitText, sitePhText } from './phEvidence.js'

const placeholders = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()

test('the default language is English (no stored choice, no storage at all)', () => {
  assert.equal(getLang(), 'en')
  assert.deepEqual(LANGS, ['en', 'tl'])
})

test('both languages have exactly the same keys and the same placeholders; nothing is empty', () => {
  const en = Object.keys(MESSAGES.en).sort()
  const tl = Object.keys(MESSAGES.tl).sort()
  assert.deepEqual(en, tl)
  for (const k of en) {
    assert.ok(MESSAGES.en[k].trim() !== '' && MESSAGES.tl[k].trim() !== '', k)
    assert.deepEqual(placeholders(MESSAGES.en[k]), placeholders(MESSAGES.tl[k]), `placeholders of ${k}`)
  }
})

test('every key renders in both languages, with every placeholder filled', () => {
  for (const lang of LANGS) {
    for (const k of Object.keys(MESSAGES.en)) {
      const params = Object.fromEntries(placeholders(MESSAGES[lang][k]).map((p) => [p, 'X']))
      const out = tr(k, params, lang)
      assert.ok(out.length > 0 && !/[{}]/.test(out), `${lang} ${k}: ${out}`)
    }
  }
  assert.equal(tr('no.such.key'), 'no.such.key')
  assert.equal(tr('flow.back', {}, 'xx'), 'Back') // an unknown language falls back to English
})

test('the switch changes what the functions say, and it still works when the browser storage fails', () => {
  globalThis.localStorage = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') } }
  setLang('tl')
  assert.equal(getLang(), 'tl')
  assert.equal(flowSteps({ selNames: [], where: { kind: 'all', name: '' }, whereLabel: '', planAreaLabel: '', planCreated: false })[0].title, 'Piliin ang species')
  setLang('en')
  assert.equal(getLang(), 'en')
  assert.equal(flowSteps({ selNames: [], where: { kind: 'all', name: '' }, whereLabel: '', planAreaLabel: '', planCreated: false })[0].title, 'Choose species')
  const saved = []
  globalThis.localStorage = { getItem: () => null, setItem: (k, v) => saved.push([k, v]) }
  setLang('tl')
  assert.deepEqual(saved, [[LANG_KEY, 'tl']])
  setLang('en')
  delete globalThis.localStorage
})

test('the English words of the walk, the area summary and the squares text', () => {
  const s = flowSteps({ selNames: ['Narra', 'Duhat', 'Kamagong'], where: { kind: 'barangay', name: '' }, whereLabel: '', planAreaLabel: '', planCreated: false }, 'en')
  assert.equal(s[0].summary, 'Narra, Duhat and 1 more')
  assert.equal(s[1].requirement, 'Choose a barangay, or choose Whole San Mateo.')
  assert.match(s[2].requirement, /three or more points/)
  assert.match(s[2].requirement, /Plan on this one square/, 'one point only works through the button that turns it into the one square')
  const d = { kind: 'polygon', touched: 5, not_planting: { total: 2, by_reason: { cemetery: 2 } }, left_out_by_field_check: 0, suitable: 2, low_match: 1, counted_squares: 2, partial_squares: 1, squares: { counted: [], partial: [] } }
  assert.equal(diagnosticText(d, 'en'), '5 squares touched by the drawn area: 2 suitable, 1 with a low match, 2 not a planting zone (cemetery). 2 squares were counted. 1 only partly touched (less than half), so they were not included.')
  assert.equal(haText(0.04, 'en'), 'less than 0.1 hectare')
  assert.equal(haText(0.8, 'en'), '0.8 hectares')
  assert.equal(haText(0.8, 'tl'), '0,8 ektarya')
})

test('the honest wording about pH exists in both languages: an estimate, not measured here, not part of the score', () => {
  const ph = { mean: 5.75, q05: 4.25, q95: 7.5, n_squares: 5, n_total: 6 }
  const en = [sitePhText(ph, 'square', 'en'), sitePhText(ph, 'area', 'en'), areaPhSummary(ph, 'en'), tr('ph.notScored', {}, 'en')].join(' ')
  const tl = [sitePhText(ph, 'square', 'tl'), sitePhText(ph, 'area', 'tl'), areaPhSummary(ph, 'tl'), tr('ph.notScored', {}, 'tl')].join(' ')
  assert.match(en, /only an estimate/)
  assert.match(en, /not measured in San Mateo/)
  assert.match(en, /not part of the score/)
  assert.match(tl, /tantiya lang/)
  assert.match(tl, /hindi sinukat sa San Mateo/)
  assert.match(tl, /Hindi ito kasama sa score/)
  assert.match(tr('ph.vsOutside', {}, 'en'), /Use the measurement taken on the spot/)
  assert.match(tr('ph.vsOutside', {}, 'tl'), /Ang sukat sa mismong lugar ang gamitin/)
  assert.match(areaPhSummary(null, 'en'), /no pH estimate/)
  assert.ok(!/verified|\bsafe\b|correct|guarantee|ligtas|tama/i.test(en + tl + areaPhText('inside', 'en') + areaPhText('inside', 'tl')))
  assert.match(phFitText({ inside: 2, outside: 1, none: 3, total: 6 }, 'en'), /^Of the 6 species in the list: 2 have this pH inside their range/)
})

import { phExplain, phLineText } from './phEvidence.js'

test('Phase 0 B/C: the one-line soil pH and the chip explanation say the numbers, in both languages', () => {
  const site = { mean: 5.7, q05: 4.1, q95: 7.5 }
  assert.equal(phLineText(site, 'square', 'en'), 'Soil pH (estimated): 5.7, range 4.1–7.5 (SoilGrids, 250 m; not measured in San Mateo)')
  assert.match(phLineText(site, 'square', 'tl'), /^pH ng lupa \(tantiya\): 5\.7, saklaw 4\.1–7\.5 \(SoilGrids, 250 m; hindi sinukat sa San Mateo\)$/)
  assert.equal(phLineText(null, 'square', 'en'), 'No pH estimate for this square (the model has too little data there).')
  const r = { min: 5, max: 7.5 }
  assert.equal(phExplain('uncertain', site, r, 'en'), 'The estimate 5.7 is inside the species range 5–7.5, but the model’s uncertainty (4.1–7.5) reaches below it. Display only: it is not part of the score or the order.')
  assert.match(phExplain('uncertain', { mean: 8, q05: 4, q95: 9.5 }, r, 'en'), /outside the species range 5–7.5, and the model’s uncertainty \(4–9.5\) reaches both below and above/)
  assert.match(phExplain('inside', { mean: 6, q05: 5.2, q95: 7 }, r, 'en'), /lie inside the species range 5–7.5/)
  assert.match(phExplain('outside', { mean: 4, q05: 3.5, q95: 4.5 }, r, 'en'), /lies outside the species range/)
  assert.match(phExplain('no_value', null, r, 'en'), /No pH estimate for this square/)
  assert.match(phExplain('no_range', site, null, 'en'), /has no pH range for this species/)
  for (const v of ['inside', 'outside', 'outside_optimal', 'uncertain', 'no_value', 'no_range']) for (const l of ['en', 'tl']) {
    const t = phExplain(v, site, r, l)
    assert.ok(t.length > 20 && !/[{}]/.test(t) && !/verified|\bsafe\b|guarantee/i.test(t), `${v} ${l}`)
  }
  assert.match(phExplain('uncertain', site, r, 'tl'), /umaabot sa ibaba nito ang duda ng modelo \(4\.1–7\.5\)/)
})
