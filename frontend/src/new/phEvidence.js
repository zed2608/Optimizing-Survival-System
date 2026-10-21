import { getLang, tr } from './i18n.js'

// Soil pH range of a species, from the project species dataset (GET /species/{id} -> ph_reference, GET /species-ph-reference). Pure functions, tested in phEvidence.test.mjs.
// DISPLAY ONLY: not part of any score. The range is labelled "Project species dataset" with the references the dataset lists; this file never says verified / correct / safe.
// Nothing is typed here as a pH number: every range comes from the service.

export const PH_TEXT = {
  tolerance: { en: 'Tolerated', fil: 'Matitiis' },
  optimal: { en: 'Best', fil: 'Pinakamainam' },
  listed: { en: 'Listed', fil: 'Nakalista' },
  range: { en: 'Species pH range', fil: 'pH range ng species' },
  datasetLabel: { en: 'Project species dataset', fil: 'Dataset ng proyekto' },
  kind: {
    tolerance: { en: 'Range the tree tolerates (the source also gives a best range where shown)', fil: 'Saklaw na matitiis ng puno' },
    listed: { en: 'Range listed by the source (it does not say if tolerated or best)', fil: 'Saklaw na nakalista sa sanggunian (hindi sinabi kung matitiis o pinakamainam)' },
    optimal_only: { en: 'Best range only (the source gives no tolerated range)', fil: 'Pinakamainam na saklaw lang ang nakalista' },
  },
  tag: { en: 'Project species dataset', fil: 'Dataset ng proyekto' },
  conflict: { en: 'Sources disagree; check with the agriculturist', fil: 'May magkaibang sanggunian; tingnan sa agriculturist' },
  none: { en: 'pH range not available', fil: 'Walang available na pH range' },
  noneHelp: {
    en: 'The project species dataset has no pH range for this species.',
    fil: 'Walang pH range ang dataset ng proyekto para sa species na ito.',
  },
  group: { en: 'The source is about the whole group or genus, not this exact species', fil: 'Para sa buong grupo o genus ang sanggunian, hindi eksaktong species' },
  noVerdict: { en: 'No verdict: no pH range is available for this species.', fil: 'Walang hatol: walang available na pH range ang species na ito.' },
  outsideOptimal: { en: 'Outside the best range (not yet verified)', fil: 'Labas sa pinakamainam na saklaw (hindi pa pirmado)' },
  unmatched: { en: 'Draft range; the source could not be found or does not match', fil: 'Paunang saklaw; hindi makita o hindi tugma sa sanggunian' },
  // the "Sukat sa lugar" tool
  toolTitle: { en: 'Measure on site', fil: 'Sukat sa lugar' },
  toolLabel: { en: 'pH you measured (3.0 to 10.0)', fil: 'pH na nasukat mo (3.0 hanggang 10.0)' },
  toolNote: { en: 'Use a pH test kit or meter on the spot. This is not saved.', fil: 'Gumamit ng pH test kit o meter sa mismong lugar. Hindi ito sine-save.' },
  toolReset: { en: 'Clear', fil: 'I-reset' },
  toolBad: { en: 'Enter a number from 3.0 to 10.0.', fil: 'Maglagay ng numero mula 3.0 hanggang 10.0.' },
  cmp: {
    optimal: { en: 'Inside the best range', fil: 'Nasa pinakamainam na saklaw' },
    tolerated: { en: 'Inside the tolerated range, not the best', fil: 'Nasa saklaw na matitiis, hindi pinakamainam' },
    listed: { en: 'Inside the listed range', fil: 'Nasa saklaw na nakalista' },
    outside: { en: 'Outside the range', fil: 'Labas sa saklaw' },
    outsideOptimal: { en: 'Outside the best range', fil: 'Labas sa pinakamainam na saklaw' },
    none: { en: 'pH range not available', fil: 'Walang available na pH range' },
  },
  // plan result
  planNone: { en: 'pH: range not available', fil: 'pH: walang available na range' },
  other: { en: 'Other published range', fil: 'Ibang nailathalang range' },
}

const n = (v) => (v === null || v === undefined || v === '' ? null : Number.isFinite(Number(v)) ? Number(v) : null)
const fmt = (v) => String(Math.round(Number(v) * 10) / 10)
const pair = (lo, hi) => (n(lo) !== null && n(hi) !== null ? `${fmt(lo)}–${fmt(hi)}` : null)

// ref = ph_reference of the service. Returns the lines of the Species card row.
export function phRowFromRef(ref) {
  if (!ref) return { none: true, text: PH_TEXT.none, help: PH_TEXT.noneHelp, lines: [], tag: null, conflict: false, kind: null, group: false, source: null }
  if (ref.status !== 'sourced') return { none: true, text: PH_TEXT.none, help: PH_TEXT.noneHelp, lines: [], tag: null, conflict: false, kind: null, group: false, source: null }
  const lines = []
  const tol = pair(ref.tol_min, ref.tol_max)
  const opt = pair(ref.opt_min, ref.opt_max)
  const lst = pair(ref.listed_min, ref.listed_max)
  if (tol) lines.push({ key: 'tolerance', label: PH_TEXT.tolerance, range: tol })
  if (opt) lines.push({ key: 'optimal', label: PH_TEXT.optimal, range: opt })
  if (lst) lines.push({ key: 'listed', label: ref.source_kind === 'dataset' ? PH_TEXT.range : PH_TEXT.listed, range: lst })
  const dataset = ref.source_kind === 'dataset'
  const auth = ref.authority_listed ?? ref.source_name ?? ''
  const oth = ref.other_published ? pair(ref.other_published.min, ref.other_published.max) : null
  return {
    dataset,
    summary: dataset && lst ? { en: `Species pH range: ${lst} (${PH_TEXT.datasetLabel.en}; references: ${auth})`, fil: `pH range ng species: ${lst} (${PH_TEXT.datasetLabel.fil}; sanggunian: ${auth})` } : null,
    other: oth ? { text: { en: `${PH_TEXT.other.en}: ${oth} (${ref.other_published.source_name ?? '-'})`, fil: `${PH_TEXT.other.fil}: ${oth} (${ref.other_published.source_name ?? '-'})` }, url: ref.other_published.source_url ?? null } : null,
    none: false,
    lines,
    kind: PH_TEXT.kind[ref.verdict_kind] ?? null,
    tag: PH_TEXT.tag,
    conflict: ref.conflict === true,
    group: ref.scope === 'genus_or_group',
    source: { url: ref.source_url, rank: ref.source_rank, name: ref.source_name },
    quote: ref.quote ?? null,
  }
}

// Parse what the user typed: comma or dot, 3.0 to 10.0. Returns a number or null.
export function parsePhInput(text) {
  const t = String(text ?? '').trim().replace(',', '.')
  if (!/^\d{1,2}(\.\d{1,2})?$/.test(t)) return null
  const v = Number(t)
  return v >= 3 && v <= 10 ? v : null
}

// The measured pH against the evidence: code in optimal | tolerated | listed | outside | outside_optimal | none. Tolerated wins over listed; the limits count as inside.
export function compareMeasured(ph, ref) {
  const v = n(ph)
  if (v === null || !ref || ref.status !== 'sourced') return 'none'
  const inside = (lo, hi) => n(lo) !== null && n(hi) !== null && v >= Number(lo) && v <= Number(hi)
  if (inside(ref.opt_min, ref.opt_max)) return 'optimal'
  if (inside(ref.tol_min, ref.tol_max)) return 'tolerated'
  if (inside(ref.listed_min, ref.listed_max)) return ref.verdict_kind === 'optimal_only' ? 'optimal' : 'listed'
  return ref.verdict_kind === 'optimal_only' ? 'outside_optimal' : 'outside'
}

export const COMPARE_TEXT = {
  optimal: PH_TEXT.cmp.optimal,
  tolerated: PH_TEXT.cmp.tolerated,
  listed: PH_TEXT.cmp.listed,
  outside: PH_TEXT.cmp.outside,
  outside_optimal: PH_TEXT.cmp.outsideOptimal,
  none: PH_TEXT.cmp.none,
}

// One short line per species for the plan result: "pH: 5.0–7.5 (sanggunian) · sukatin sa lugar" or "pH: walang nakumpirmang range".
export function planPhLine(ref) {
  if (!ref || ref.status !== 'sourced') return { code: 'none', text: PH_TEXT.planNone }
  const range = pair(ref.verdict_min, ref.verdict_max)
  return { code: 'range', text: { en: `pH: ${range} (project species dataset) · measure on site`, fil: `pH: ${range} (dataset ng proyekto) · sukatin sa lugar` } }
}

// "N of M species in this plan have no pH range available" (Filipino with the English line). Null when every species has one (all 45 have one in the project species dataset).
export function planPhSummary(speciesIds, all) {
  const ids = [...new Set(speciesIds ?? [])]
  if (!ids.length) return null
  const none = ids.filter((id) => !all || !all[String(id)] || all[String(id)].status !== 'sourced')
  if (!none.length) return null
  return {
    count: none.length,
    total: ids.length,
    ids: none,
    text: {
      en: `${none.length} of ${ids.length} species in this plan have no pH range available`,
      fil: `${none.length} sa ${ids.length} na species sa planong ito ay walang available na pH range`,
    },
  }
}

// The pH verdict of one species for an AREA (from POST /rank/area: ph_verdict), one short line for the species list. Display only: it never changes a score or the order.
const AREA_PH_CODES = ['inside', 'outside', 'outside_optimal', 'uncertain', 'no_value', 'no_confirmed_range', 'no_range']
export function areaPhText(code, lang = getLang()) {
  return AREA_PH_CODES.includes(code) ? tr(`ph.v.${code}`, {}, lang) : null
}

const f1 = (v) => String(Math.round(Number(v) * 10) / 10)

// One line about the area's own pH estimate (r.area.ph of POST /rank/area), or a "no estimate" line when there is none.
export function areaPhSummary(ph, lang = getLang()) {
  if (!ph) return tr('ph.areaSummaryNone', {}, lang)
  return tr('ph.areaSummary', { mean: f1(ph.mean), lo: f1(ph.q05), hi: f1(ph.q95) }, lang)
}

// The SoilGrids estimate of a square or of an area (display only; a model estimate, never called a measurement).
export function sitePhText(ph, scope = 'square', lang = getLang()) {
  if (!ph) return tr(scope === 'area' ? 'ph.none.area' : 'ph.none.square', {}, lang)
  const head = tr(scope === 'area' ? 'ph.head.area' : 'ph.head.square', { mean: f1(ph.mean), lo: f1(ph.q05), hi: f1(ph.q95) }, lang)
  const from = scope === 'area' && ph.n_squares != null ? tr('ph.from', { n: ph.n_squares, total: ph.n_total }, lang) : ''
  return `${head}${from}${tr('ph.tail', {}, lang)}`
}

// What a pH measured on the spot means for a list of species: how many have it inside their range (tolerated, best or listed), outside, or have no confirmed range. all = GET /species-ph-reference .species
export function phFitCounts(value, speciesIds, all) {
  const out = { inside: 0, outside: 0, none: 0, total: 0 }
  for (const id of new Set(speciesIds ?? [])) {
    out.total++
    const ref = all?.[String(id)]
    const c = compareMeasured(value, ref)
    if (!ref || ref.status !== 'sourced') out.none++
    else if (c === 'outside' || c === 'outside_optimal') out.outside++
    else out.inside++
  }
  return out
}

export function phFitText(c, lang = getLang()) {
  return tr('ph.fit', { total: c.total, inside: c.inside, outside: c.outside, none: c.none }, lang)
}

// The one-line soil pH of a place or an area, for the "Land details" and the area result: "Soil pH (estimated): 5.7, range 4.1–7.5 (SoilGrids, 250 m; not measured in San Mateo)". Display only.
export function phLineText(ph, scope = 'square', lang = getLang()) {
  if (!ph) return tr(scope === 'area' ? 'ph.none.area' : 'ph.none.square', {}, lang)
  return tr(scope === 'area' ? 'ph.line.area' : 'ph.line.square', { mean: f1(ph.mean), lo: f1(ph.q05), hi: f1(ph.q95) }, lang)
}

// What a species pH chip means, with the numbers. site = {mean, q05, q95} (the estimate of the square or area) or null; range = {min, max} of the species (project species dataset) or null.
// verdict = the code the service sent (inside | outside | outside_optimal | uncertain | no_value | no_range | no_confirmed_range). Display only.
export function phExplain(verdict, site, range, lang = getLang()) {
  const t = (k, p) => tr(k, p, lang)
  const tail = ` ${t('ph.explain.tail')}`
  if (verdict === 'no_value' || !site) return t('ph.explain.no_value') + tail
  if (verdict === 'no_range' || verdict === 'no_confirmed_range' || !range) return t('ph.explain.no_range') + tail
  const p = { mean: f1(site.mean), lo: f1(site.q05), hi: f1(site.q95), smin: f1(range.min), smax: f1(range.max) }
  if (verdict === 'inside' || verdict === 'outside' || verdict === 'outside_optimal') return t(`ph.explain.${verdict}`, p) + tail
  const inside = site.mean >= range.min && site.mean <= range.max
  const below = site.q05 < range.min
  const above = site.q95 > range.max
  const side = below && above ? 'both' : below ? 'below' : 'above'
  return t(`ph.explain.uncertain.${side}`, { ...p, where: t(inside ? 'ph.explain.where.in' : 'ph.explain.where.out'), conn: t(inside ? 'ph.explain.conn.in' : 'ph.explain.conn.out') }) + tail
}
