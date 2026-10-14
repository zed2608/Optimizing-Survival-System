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
  below: { en: 'Lower than the species range', fil: 'Mas mababa kaysa saklaw ng species' },
  above: { en: 'Higher than the species range', fil: 'Mas mataas kaysa saklaw ng species' },
  notScored: {
    en: 'This is not part of the score. The nearest station is used, not San Mateo itself.',
    fil: 'Hindi ito bahagi ng score. Pinakamalapit na istasyon ang gamit, hindi San Mateo mismo.',
  },
  provisional: { en: 'PROVISIONAL', fil: 'PROVISIONAL' },
  pending: { en: 'No data yet (asked from PAGASA)', fil: 'Walang datos pa (hihingin kay PAGASA)' },
  noLayer: { en: 'No data yet (there is no pH map)', fil: 'Walang datos pa (walang pH map)' },
  noReference: { en: 'The reference file could not be read.', fil: 'Hindi mabasa ang reference file.' },
  type1: { en: 'The sources list Type I for this species', fil: 'Nakalista ang Type I para sa species na ito' },
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
export function buildClimate(cref, cv) {
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
