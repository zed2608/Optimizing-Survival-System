// The small "Climate and soil (reference only)" section of the Species card (stage C1). Pure functions, tested in climateRef.test.mjs.
// DISPLAY ONLY: none of this is part of any score. The numbers come from the service (data/config/climate_reference.csv and the species table); nothing is typed here.
// English with the same line in Filipino under it, short everyday words. A missing number is "No data yet / Walang datos pa", never a zero.

export const TEXT = {
  title: { en: 'Climate and soil (reference only)', fil: 'Klima at lupa (reference lang)' },
  species: { en: 'This species', fil: 'Itong species' },
  sanMateo: { en: 'San Mateo reference', fil: 'Reference para sa San Mateo' },
  rain: { en: 'Rain', fil: 'Ulan' },
  temp: { en: 'Temperature', fil: 'Temperatura' },
  ph: { en: 'Soil pH', fil: 'pH ng lupa' },
  climate: { en: 'Climate type', fil: 'Uri ng klima' },
  perYear: { en: 'a year', fil: 'sa isang taon' },
  to: { en: 'to', fil: 'hanggang' },
  noData: { en: 'No data yet', fil: 'Walang datos pa' },
  fits: { en: 'Fits: San Mateo rain is inside the range', fil: 'Pasok: nasa saklaw ang ulan sa San Mateo' },
  below: { en: 'Under the listed range (not yet verified)', fil: 'Mababa sa saklaw na nakalista (hindi pa pirmado)' },
  above: { en: 'Beyond the listed range (not yet verified)', fil: 'Lampas sa saklaw na nakalista (hindi pa pirmado)' },
  refWord: { en: 'Reference', fil: 'Reference' },
  notScored: {
    en: 'This is not part of the score. The nearest station is used, not San Mateo itself.',
    fil: 'Hindi ito bahagi ng score. Pinakamalapit na istasyon ang gamit, hindi San Mateo mismo.',
  },
  provisional: { en: 'PROVISIONAL', fil: 'PROVISIONAL' },
  pending: { en: 'No data yet (asked from PAGASA)', fil: 'Walang datos pa (hihingin kay PAGASA)' },
  noLayer: { en: 'No data yet (there is no pH map)', fil: 'Walang datos pa (walang pH map)' },
  noReference: { en: 'The reference file could not be read.', fil: 'Hindi mabasa ang reference file.' },
  type1: { en: 'The sources list Type I for this species', fil: 'Nakalista ang Type I para sa species na ito' },
  phNone: { en: 'No pH estimate for this place', fil: 'Walang pH estimate sa lugar na ito' },
  phSite: { en: 'Estimated pH', fil: 'Tinatayang pH' },
  phRangeWord: { en: 'possibly', fil: 'posibleng' },
  phEstimate: { en: 'Estimate only, not measured in San Mateo', fil: 'Estimate lang, hindi sinukat sa San Mateo' },
  phUnverified: { en: 'Project species dataset', fil: 'Dataset ng proyekto' },
  phInside: { en: 'Inside the range (according to the model)', fil: 'Nasa saklaw (ayon sa modelo)' },
  phOutside: { en: 'Beyond the listed range (not yet verified)', fil: 'Labas sa saklaw na nakalista (hindi pa pirmado)' },
  phUncertain: { en: 'Not certain: the model is too unsure to say', fil: 'Hindi tiyak: masyadong malawak ang duda ng modelo para sabihin' },
  phModelName: { en: 'SoilGrids 2.0 (model, 250 m, not measured in San Mateo)', fil: 'SoilGrids 2.0 (modelo, 250 m, hindi sinukat sa San Mateo)' },
  phMunicipality: { en: 'Whole municipality (middle values of all squares)', fil: 'Buong bayan (gitnang halaga ng lahat ng square)' },
  phNoVerdict: { en: 'No verdict: no pH range is available for this species.', fil: 'Walang hatol: walang available na pH range ang species na ito.' },
  phNoRangeSpecies: { en: 'pH range not available', fil: 'Walang available na pH range' },
  phOutsideOptimal: { en: 'Outside the best range (not yet verified)', fil: 'Labas sa pinakamainam na saklaw (hindi pa pirmado)' },
  phNotScored: { en: 'This is not part of the score.', fil: 'Hindi ito kasama sa score.' },
  notType1: { en: 'The sources do not list Type I for this species', fil: 'Hindi nakalista ang Type I para sa species na ito' },
}

const has = (v) => v !== null && v !== undefined && String(v).trim() !== '' && String(v).toLowerCase() !== 'nan' && Number.isFinite(Number(v))
const numText = (v) => String(Math.round(Number(v) * 100) / 100)

// "1200 to 3000 mm" / "from 5 up" / "up to 7.5" / null
function rangeLines(lo, hi, unitEn, unitFil = unitEn) {
  const ue = unitEn ? ` ${unitEn}` : ''
  const uf = unitFil ? ` ${unitFil}` : ''
  if (has(lo) && has(hi)) return { en: `${numText(lo)} to ${numText(hi)}${ue}`, fil: `${numText(lo)} hanggang ${numText(hi)}${uf}` }
  if (has(lo)) return { en: `from ${numText(lo)}${ue}`, fil: `mula ${numText(lo)}${uf}` }
  if (has(hi)) return { en: `up to ${numText(hi)}${ue}`, fil: `hanggang ${numText(hi)}${uf}` }
  return null
}

// Where the reference came from, in one short line: "PAGASA Climatological Normals, Science Garden, Quezon City, provisional stand-in".
export function sourceLine(item) {
  if (!item) return null
  const parts = [item.source, item.station_or_scope].filter((x) => x && String(x).trim() !== '')
  return parts.join(', ')
}

const STATUS_WORDS = { provisional_proxy: { en: 'provisional stand-in', fil: 'pansamantalang kapalit' }, provisional: { en: 'provisional', fil: 'pansamantala' }, pending: null, no_layer: null }

// cref = the "climate_reference" object of GET /species/{id}; cv = its clean_values. Returns { rows, notice, title, scored: false } or { error } when the service sent nothing.
// phRef (4th argument) = the evidence-file reference of the species (ph_reference): the species pH range and the "no verdict" case come from it, never from cv.ph_min / cv.ph_max.
// Left out (undefined) = the earlier behaviour (the range of cv), kept for the older tests.
export function buildClimate(cref, cv, sitePh = null, phRef = undefined) {
  if (!cref || !Array.isArray(cref.items) || cref.items.length === 0) return { error: TEXT.noReference, title: TEXT.title, notice: TEXT.notScored, rows: [], scored: false }
  const by = Object.fromEntries(cref.items.map((i) => [i.key, i]))
  const rainItem = by.annual_rainfall_mm
  const tempItem = by.annual_mean_temperature_c
  const phItem = by.soil_ph
  const typeItem = by.climate_type
  const rain = cref.rain || {}
  const rows = []

  // rain: the only one that is compared (a number exists)
  const rainRef = rainItem && has(rainItem.value) ? { en: `${numText(rainItem.value)} mm ${TEXT.perYear.en}`, fil: `${numText(rainItem.value)} mm ${TEXT.perYear.fil}` } : null
  const verdictKey = { fits: 'fits', below: 'below', above: 'above' }[rain.assessment] ?? null
  rows.push({
    id: 'rain',
    label: TEXT.rain,
    species: rangeLines(rain.species_min_mm, rain.species_max_mm, 'mm a year', 'mm sa isang taon'),
    reference: rainRef ?? TEXT.noData,
    source: rainRef ? sourceLine(rainItem) : null,
    status: rainItem ? rainItem.status : null,
    statusWords: rainItem ? STATUS_WORDS[rainItem.status] ?? null : null,
    asOf: rainRef ? rainItem.accessed_date : null,
    verdict: verdictKey ? TEXT[verdictKey] : TEXT.noData,
    verdictCode: verdictKey ?? 'no_data',
    verdictRef: verdictKey && rainRef ? { name: sourceLine(rainItem), status: rainItem.status, statusWords: STATUS_WORDS[rainItem.status] ?? null } : null,
  })
  // temperature and pH: the species range, and "no data yet" for San Mateo (nothing is compared)
  for (const [id, label, item, lo, hi, unit] of [
    ['temp', TEXT.temp, tempItem, cv?.temp_min_c, cv?.temp_max_c, '°C'],
    ['ph', TEXT.ph, phItem, cv?.ph_min, cv?.ph_max, ''],
  ]) {
    const have = item && has(item.value)
    rows.push({
      id,
      label,
      species: rangeLines(lo, hi, unit),
      reference: have ? { en: `${numText(item.value)} ${unit}`.trim(), fil: `${numText(item.value)} ${unit}`.trim() } : item && item.status === 'no_layer' ? TEXT.noLayer : TEXT.pending,
      source: have ? sourceLine(item) : null,
      status: item ? item.status : null,
      statusWords: item ? STATUS_WORDS[item.status] ?? null : null,
      asOf: have ? item.accessed_date : null,
      verdict: TEXT.noData,
      verdictCode: 'no_data',
    })
  }
  // pH of the site from SoilGrids (a model estimate, display only): the line, the species range tagged "not yet verified", inside / outside, and the credit
  const phRow = rows.find((r) => r.id === 'ph')
  if (sitePh && sitePh.available && has(sitePh.ph_mean)) {
    const lo = has(sitePh.ph_q05) ? sitePh.ph_q05 : null
    const hi = has(sitePh.ph_q95) ? sitePh.ph_q95 : null
    const one = (v) => Number(v).toFixed(1)
    const span = lo !== null && hi !== null ? ` (${TEXT.phRangeWord.en} ${one(lo)}–${one(hi)})` : ''
    const spanF = lo !== null && hi !== null ? ` (${TEXT.phRangeWord.fil} ${one(lo)}–${one(hi)})` : ''
    phRow.reference = { en: `${TEXT.phSite.en}: ${one(sitePh.ph_mean)}${span}`, fil: `${TEXT.phSite.fil}: ${one(sitePh.ph_mean)}${spanF}` }
    phRow.status = 'model_estimate'
    phRow.statusWords = TEXT.phEstimate
    phRow.source = null
    phRow.attribution = sitePh.attribution
    phRow.scope = sitePh.scope === 'municipality' ? TEXT.phMunicipality : null
    phRow.speciesTag = phRow.species ? TEXT.phUnverified : null
    const code = { inside: 'inside', outside: 'outside', outside_optimal: 'outside_optimal', uncertain: 'uncertain', no_confirmed_range: 'no_confirmed_range' }[sitePh.verdict] ?? 'no_data'
    phRow.verdictCode = code
    phRow.verdict =
      code === 'inside' ? TEXT.phInside : code === 'outside' ? TEXT.phOutside : code === 'outside_optimal' ? TEXT.phOutsideOptimal : code === 'uncertain' ? TEXT.phUncertain : code === 'no_confirmed_range' ? TEXT.phNoVerdict : TEXT.noData
    phRow.extraNote = TEXT.phNotScored
    phRow.verdictRef = code === 'no_data' ? null : { name: TEXT.phModelName, status: 'model_estimate', statusWords: TEXT.phEstimate }
  } else if (sitePh && sitePh.available === false && (sitePh.reason === 'no_value_here' || sitePh.reason === 'no_values')) {
    phRow.reference = TEXT.phNone
  }
  if (phRow && phRef !== undefined) {
    // the species range comes from the evidence file only
    if (!phRef || phRef.status !== 'sourced') {
      phRow.species = TEXT.phNoRangeSpecies
      phRow.speciesTag = null
      phRow.verdictCode = 'no_confirmed_range'
      phRow.verdict = TEXT.phNoVerdict
      phRow.verdictRef = null
    } else {
      const f = (v) => String(Math.round(Number(v) * 10) / 10)
      const t = `${f(phRef.verdict_min)} to ${f(phRef.verdict_max)}`
      phRow.species = { en: t, fil: `${f(phRef.verdict_min)} hanggang ${f(phRef.verdict_max)}` }
      phRow.speciesTag = TEXT.phUnverified
    }
  }
  // climate type: a plain reference line (the species' own list of climate types comes from its sources)
  const t1 = cv?.corona_has_type_I
  rows.push({
    id: 'climate',
    label: TEXT.climate,
    species: t1 === true || t1 === 'True' ? TEXT.type1 : t1 === false || t1 === 'False' ? TEXT.notType1 : null,
    reference: typeItem && typeItem.value ? { en: typeItem.value.startsWith('Type I') ? 'Type I (dry from December to May)' : typeItem.value, fil: typeItem.value } : TEXT.noData,
    source: typeItem && typeItem.value ? sourceLine(typeItem) : null,
    status: typeItem ? typeItem.status : null,
    statusWords: typeItem ? STATUS_WORDS[typeItem.status] ?? null : null,
    asOf: typeItem && typeItem.value ? typeItem.accessed_date : null,
    verdict: null,
    verdictCode: null,
  })
  return { title: TEXT.title, notice: TEXT.notScored, rows, scored: cref.scored === true }
}
