// The cut-offs of the map colours (v2/config.js W_GOOD and W_MODERATE; plainWords.test.mjs checks that they are still the same).
export const W_GOOD = 0.55
export const W_MODERATE = 0.35

// ONE place that turns every warning, note and flag of the service into a plain sentence for the main (Simple) view. The Detailed view may still show the technical
// terms. Nothing the service says is dropped: a text that no rule knows is cleaned (underscores to spaces, "name=value" pieces removed) and shown.

const RULES = [
  [/^palette_smaller_than_min:\s*(\d+) species \(min (\d+)\)/i, (m) => `Only ${m[1]} species suit this area, fewer than the ${m[2]} we usually plan with.`],
  [/^no species can be placed/i, () => 'No species can be planted in this area.'],
  [/^caps_cannot_absorb_all_saplings:\s*(\d+) of (\d+)/i, (m) => `Only ${m[1]} of ${m[2]} trees could be shared out between the species: each species can only take so many.`],
  [/^Single species planting/i, () => 'Only one species: a higher risk of pests and disease.'],
  [/^Mostly one species/i, () => 'Mostly one species: a higher risk of pests.'],
  [/^Only (\d+) species: low diversity/i, (m) => `Only ${m[1]} species: little variety, so a higher risk of pests.`],
  [/^Caps relaxed:/i, () => 'You chose only a few species, so each one takes a bigger share of the trees than usual.'],
  [/^You chose the tree count of every species/i, () => 'You chose how many trees of each species, so the usual share limits do not apply.'],
  [/^season:.*(do not|don.t) share a planting month/i, () => 'These species have no planting month in common inside your dates.'],
  [/^season:/i, (m, t) => cleanText(t.replace(/^season:\s*/i, ''))],
]

// Pieces of text that only make sense to a developer: "season_filter=mark ...", file names, code names.
function cleanText(t) {
  let s = String(t ?? '')
  s = s.replace(/,?\s*or send season_filter=mark[^.]*\./gi, ' Or choose “Show all species”.')
  s = s.replace(/\(\s*season_filter=\w+[^)]*\)/gi, '')
  s = s.replace(/\bsend\s+season_filter=\w+\b/gi, 'choose “Show all species”')
  s = s.replace(/\b[\w.]+=[\w.\-"]+/g, '')
  s = s.replace(/([A-Za-z0-9]+)_([A-Za-z0-9_]+)/g, (a) => a.replace(/_/g, ' '))
  return s.replace(/\s+([.,;:])/g, '$1').replace(/\s{2,}/g, ' ').trim()
}

export function plainWarning(text) {
  const t = String(text ?? '').trim()
  for (const [re, fn] of RULES) {
    const m = t.match(re)
    if (m) return fn(m, t)
  }
  return cleanText(t)
}

// Flag codes (the "flags" of a ranked species or planted block) in plain words, the same wording as the printed field kit.
const FLAGS = {
  soil_provisional: 'Soil from the LGU soil map (provisional)',
  ground_built_up: 'Looks built-up in the satellite land cover: check on the ground first',
  ground_bare: 'Looks bare in the satellite land cover: check on the ground first',
  ground_water: 'Looks like water in the satellite land cover: check on the ground first',
  zoning_unconfirmed: 'Outside our zoning map: Forest Reserve, coordinate with MENRO and DENR',
  needs_both_sexes: 'Separate sexes: plant both',
  rehab_site_food_warning: 'Fruit or produce from a landfill or mining site may hold heavy metals; do not plan to eat or sell it without testing',
  habagat_washout: 'Heavy rain and flooding (Habagat) can wash out seedlings here in Jul-Sep',
  soil_unverified_mismatch: 'Soil may not suit the species: check on site',
  species_data_unverified: 'Species data cites a file we do not have',
  low_confidence: 'Some inputs were missing: less certain score',
  barangay_nearest: 'Outside every barangay outline: nearest one listed',
}
export const GROUND_FLAGS = ['ground_built_up', 'ground_bare', 'ground_water']

export function plainFlag(code) {
  return FLAGS[code] ?? cleanText(String(code).replace(/_/g, ' '))
}

// The three scores in words: "Overall match" (W), "Site fit" (S), "Purpose fit" (P), each as a word (Good, Fair, Poor) and a percentage. The cut-offs are the
// ones of the map colours (W_GOOD and W_MODERATE of v2/config.js).
export function matchLevel(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return null
  const x = Number(v)
  return x >= W_GOOD ? 'Good' : x >= W_MODERATE ? 'Fair' : 'Poor'
}
export function matchText(v) {
  const l = matchLevel(v)
  return l === null ? 'Data Unavailable' : `${l} · ${Math.round(Number(v) * 100)}%`
}
export const SCORE_WORDS = { W: 'Overall match', S: 'Site fit', P: 'Purpose fit' }

// The one-sentence verdict of the point panel: "Good place for Kamagong: overall match 77%. In its planting months. Check the ground first."
export function verdictSentence(item, flags = [], opts = {}) {
  if (!item) return 'No species suits this spot.'
  const lvl = matchLevel(item.W)
  const place = item.eligible === false || lvl === null ? 'Not a suitable place' : lvl === 'Good' ? 'Good place' : lvl === 'Fair' ? 'Fair place' : 'Weak place'
  let s = item.eligible === false || lvl === null ? `${place} for ${item.common_name}.` : `${place} for ${item.common_name}: overall match ${Math.round(item.W * 100)}%.`
  const st = item.season?.status
  if (st === 'in_season') s += ' In its planting months.'
  else if (st === 'partly') s += ' Partly in its planting months.'
  else if (st === 'out_of_season') s += ' Outside its best months.'
  if (flags.some((f) => GROUND_FLAGS.includes(f)) || opts.check) s += ' Check the ground first.'
  return s
}

// "Why?" under a note of the plan result: one sentence, no code names.
const WHY = [
  [/^Single species|^Mostly one species|^Only \d+ species/i, 'When one kind of tree makes up most of a planting, a pest or disease that likes it can spread fast. Mixing species spreads that risk.'],
  [/^Caps relaxed|^You chose the tree count/i, 'Usually no species gets more than a fifth of the trees. With a short list that is not possible, so the share limits were loosened.'],
  [/season:.*planting month/i, 'Every species has its own planting months. Planting outside them means more watering and more losses.'],
  [/palette_smaller_than_min|^no species can be placed/i, 'Few species pass the site rules (altitude, slope, soil and wetness) in this area.'],
  [/caps_cannot_absorb/i, 'Each species can only take so many trees: its share limit and the number of squares that suit it.'],
  [/^Plant both male and female/i, 'These species have separate male and female trees. Seeds and fruit only form when both grow near each other.'],
  [/^These species suit each other|^Some of these species|^No partner rule/i, 'These are starting rules from the species data (height, shade, water, roots and planting months). The agriculturist will check them.'],
]
export function whyWarning(text) {
  const t = String(text ?? '')
  for (const [re, why] of WHY) if (re.test(t)) return why
  return 'This comes from the planning rules for your area and dates.'
}

// "6 to 30 Oct 2026", "28 Oct to 6 Nov 2026", "28 Dec 2026 to 5 Jan 2027" (empty when a date is missing).
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export function rangeWords(start, end) {
  const a = /^(\d{4})-(\d{2})-(\d{2})$/.exec(start ?? '')
  const b = /^(\d{4})-(\d{2})-(\d{2})$/.exec(end ?? '')
  if (!a || !b) return ''
  const [ya, ma, da] = [Number(a[1]), Number(a[2]) - 1, Number(a[3])]
  const [yb, mb, db] = [Number(b[1]), Number(b[2]) - 1, Number(b[3])]
  if (ya === yb && ma === mb) return da === db ? `${da} ${MON[ma]} ${ya}` : `${da} to ${db} ${MON[ma]} ${ya}`
  if (ya === yb) return `${da} ${MON[ma]} to ${db} ${MON[mb]} ${yb}`
  return `${da} ${MON[ma]} ${ya} to ${db} ${MON[mb]} ${yb}`
}

// The one sentence under the campaign name: "50 Apitong trees in 2 blocks, about 2 ha, Ampid II, 6 to 30 Oct 2026".
export function planSentence(result) {
  const s = result.summary
  const blocks = result.layout_mode === 'blocks'
  const placed = s.saplings_placed
  const planted = result.palette.filter((p) => p.placed > 0)
  const what = planted.length === 1 ? `${placed} ${planted[0].species} trees` : `${placed} trees`
  const where = s.area_choice?.display_name && s.area_choice.display_name !== 'The whole municipality' ? s.area_choice.display_name : 'San Mateo'
  const c = result.campaign
  const dates = c?.start && c?.end ? rangeWords(c.start, c.end) : ''
  const lay = s.layout
  const size = blocks && lay ? ` in ${lay.blocks} block${lay.blocks === 1 ? '' : 's'}, about ${lay.hectares_used} ha` : ' on separate squares'
  return `${what}${size}, ${where}${dates ? `, ${dates}` : ''}`
}
