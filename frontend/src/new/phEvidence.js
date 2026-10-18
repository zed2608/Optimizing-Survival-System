// Soil pH reference of a species, from the evidence file (GET /species/{id} -> ph_reference, GET /species-ph-reference). Pure functions, tested in phEvidence.test.mjs.
// DISPLAY ONLY: not part of any score. The ranges are "from a source, not yet signed by the agriculturist"; this file never says verified / correct / safe.
// Nothing is typed here as a pH number: every range comes from the service.

export const PH_TEXT = {
  tolerance: { en: 'Tolerated', fil: 'Matitiis' },
  optimal: { en: 'Best', fil: 'Pinakamainam' },
  listed: { en: 'Listed', fil: 'Nakalista' },
  kind: {
    tolerance: { en: 'Range the tree tolerates (the source also gives a best range where shown)', fil: 'Saklaw na matitiis ng puno' },
    listed: { en: 'Range listed by the source (it does not say if tolerated or best)', fil: 'Saklaw na nakalista sa sanggunian (hindi sinabi kung matitiis o pinakamainam)' },
    optimal_only: { en: 'Best range only (the source gives no tolerated range)', fil: 'Pinakamainam na saklaw lang ang nakalista' },
  },
  tag: { en: 'from a source, not yet signed by the agriculturist', fil: 'mula sa sanggunian; hindi pa pirmado ng agriculturist' },
  conflict: { en: 'Sources disagree; check with the agriculturist', fil: 'May magkaibang sanggunian; tingnan sa agriculturist' },
  none: { en: 'No confirmed pH range', fil: 'Walang nakumpirmang pH range' },
  noneHelp: {
    en: 'Ask the agriculturist or MAO before using it on land with doubtful pH.',
    fil: 'Itanong sa agriculturist/MAO bago gamitin sa lugar na may kaduda-dudang pH.',
  },
  group: { en: 'The source is about the whole group or genus, not this exact species', fil: 'Para sa buong grupo o genus ang sanggunian, hindi eksaktong species' },
  noVerdict: { en: 'No verdict: this species has no confirmed pH range.', fil: 'Walang hatol: walang nakumpirmang pH range ang species na ito.' },
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
    none: { en: 'No confirmed pH range', fil: 'Walang nakumpirmang pH range' },
  },
  // plan result
  planNone: { en: 'pH: no confirmed range', fil: 'pH: walang nakumpirmang range' },
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
  if (lst) lines.push({ key: 'listed', label: PH_TEXT.listed, range: lst })
  return {
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
  return { code: 'range', text: { en: `pH: ${range} (source) · measure on site`, fil: `pH: ${range} (sanggunian) · sukatin sa lugar` } }
}

// "N of M species in this plan have no confirmed pH range" (Filipino with the English line). Null when every species has one.
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
      en: `${none.length} of ${ids.length} species in this plan have no confirmed pH range`,
      fil: `${none.length} sa ${ids.length} na species sa planong ito ay walang nakumpirmang pH range`,
    },
  }
}
