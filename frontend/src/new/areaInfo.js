// What the "Area" step says about the chosen point, barangay, zone or drawn shape, and when "Continue" may be pressed. Pure functions (tested in areaInfo.test.mjs). English or Taglish through the last argument / `lang` (default: the page language).
import { geometryContains } from './geo.js'
import { getLang, tr } from './i18n.js'

const M_PER_DEG = 111320 // about; enough for a size in hectares

// vertices = [[lat, lon], ...] -> area in hectares (flat approximation around the shape; a few percent at most for San Mateo-sized shapes)
export function polygonHectares(vertices) {
  if (!vertices || vertices.length < 3) return 0
  const lat0 = vertices.reduce((a, v) => a + v[0], 0) / vertices.length
  const kx = M_PER_DEG * Math.cos((lat0 * Math.PI) / 180)
  const pts = vertices.map(([lat, lon]) => [lon * kx, lat * M_PER_DEG])
  let s = 0
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) s += pts[j][0] * pts[i][1] - pts[i][0] * pts[j][1]
  return Math.abs(s) / 2 / 10000
}

// GeoJSON Polygon geometry (the ring made by polygonFromVertices) -> hectares
export function geometryHectares(geometry) {
  const ring = geometry?.coordinates?.[0]
  if (!ring) return 0
  return polygonHectares(ring.slice(0, -1).map(([lon, lat]) => [lat, lon]))
}

const hasArea = (n) => (n >= 10 ? Math.round(n) : Math.round(n * 10) / 10)
export function haText(ha, lang = getLang()) {
  if (ha < 0.1) return tr('ha.tiny', {}, lang)
  const v = String(hasArea(ha))
  return tr('ha.value', { ha: lang === 'tl' ? v.replace('.', ',') : v }, lang)
}

// The barangays a drawn shape reaches, judged from its corners and its middle (not an exact overlay). features = barangay features with display_name.
export function barangaysOfShape(geometry, features) {
  const ring = geometry?.coordinates?.[0]
  if (!ring || !features?.length) return []
  const pts = ring.slice(0, -1)
  const mid = [pts.reduce((a, p) => a + p[0], 0) / pts.length, pts.reduce((a, p) => a + p[1], 0) / pts.length]
  const found = []
  for (const [lon, lat] of [mid, ...pts]) {
    const f = features.find((x) => geometryContains(x.geometry, lon, lat))
    if (f && !found.includes(f.properties.display_name ?? f.properties.name)) found.push(f.properties.display_name ?? f.properties.name)
  }
  return found
}

// lines of the summary: [{label, value}] for the chosen point (tool 'point'), barangay, zone or drawn shape.
// ctx = { tool, area, spot, geometry, barangayFeatures, zoneFeatures, squares, lang } ; squares = the number of planting squares the service found in the area (or null)
export function describeArea({ tool, area, spot, barangayFeatures = [], zoneFeatures = [], squares = null, selection = null, split = null, ph = null, lang = getLang() }) {
  const t = (k, p) => tr(k, p, lang)
  const rows = []
  const r1 = (v) => Math.round(v * 10) / 10
  if (area) {
    if (area.kind === 'barangay') {
      const f = barangayFeatures.find((b) => b.properties.name === area.name)
      rows.push({ label: t('area.method'), value: tool === 'barangay' ? t('area.m.barangayPicked') : t('area.m.barangay') })
      rows.push({ label: t('area.name'), value: f?.properties.display_name ?? area.name })
      rows.push({ label: t('area.type'), value: t('area.type.barangay') })
    } else if (area.kind === 'zone') {
      rows.push({ label: t('area.method'), value: t('area.m.zone') })
      rows.push({ label: t('area.name'), value: area.name })
      rows.push({ label: t('area.type'), value: t('area.type.zone') })
    } else {
      const ha = geometryHectares(area.geometry)
      const bs = barangaysOfShape(area.geometry, barangayFeatures)
      rows.push({ label: t('area.method'), value: t('area.m.drawn') })
      rows.push({ label: t('area.name'), value: t('area.n.drawn') })
      if (bs.length) rows.push({ label: bs.length > 1 ? t('area.barangays') : t('area.barangay'), value: t('area.fromCorners', { names: bs.join(', ') }) })
      rows.push({ label: t('area.type'), value: t('area.type.polygon') })
      rows.push({ label: t('area.size'), value: ha < 0.1 ? haText(ha, lang) : t('ha.about', { text: haText(ha, lang) }) })
    }
    if (squares != null) rows.push({ label: t('area.squares'), value: t('area.squaresValue', { n: squares }) })
    if (split) rows.push({ label: t('area.split'), value: split })
    if (ph) rows.push({ label: t('area.ph'), value: t('area.phValue', { mean: r1(ph.mean), lo: r1(ph.q05), hi: r1(ph.q95) }) })
    if (selection === 'touching') rows.push({ label: t('area.note'), value: t('area.small') })
    return rows
  }
  if (tool === 'point' && spot) {
    const b = barangayFeatures.find((f) => geometryContains(f.geometry, spot.lon, spot.lat))
    const z = zoneFeatures.find((f) => geometryContains(f.geometry, spot.lon, spot.lat))
    rows.push({ label: t('area.method'), value: t('area.m.point') })
    rows.push({ label: t('area.barangay'), value: b?.properties.display_name ?? t('area.noBarangay') })
    rows.push({ label: t('area.zone'), value: z?.properties.name ?? t('area.noZone') })
    rows.push({ label: t('area.type'), value: t('area.type.point') })
  }
  return rows
}

// May the person go on to the next step? mode 'area': a chosen area that holds at least one planting square. areaRank = { status, error: { status, message } } of POST /rank/area.
export function continueState({ mode, area, areaRank, lang = getLang() }) {
  if (mode !== 'area') return { ok: true, reason: '' }
  if (!area) return { ok: false, reason: tr('cont.pick', {}, lang) }
  const e = areaRank?.status === 'error' ? areaRank.error : null
  if (e && e.status === 400 && String(e.message).includes('no legal-zone grid points')) {
    return { ok: false, reason: tr('cont.none', {}, lang) }
  }
  if (areaRank?.status === 'loading') return { ok: false, reason: tr('cont.loading', {}, lang) }
  return { ok: true, reason: '' }
}

// UX round 2 (A3): the split of the squares of an area in plain words (English or Taglish). diag = the answer of POST /area/diagnostic.
// Example (English): "5 squares touched by the drawn area: 2 suitable, 1 with a low match, 2 not a planting zone (cemetery)."
export function diagnosticText(diag, lang = getLang()) {
  if (!diag || !diag.touched) return null
  const t = (k, p) => tr(k, p, lang)
  const parts = []
  if (diag.suitable) parts.push(t('diag.suitable', { n: diag.suitable }))
  if (diag.low_match) parts.push(t('diag.low', { n: diag.low_match }))
  if (diag.not_planting.total) {
    const entries = Object.entries(diag.not_planting.by_reason)
    const word = (k) => (t(`diag.reason.${k}`) === `diag.reason.${k}` ? k : t(`diag.reason.${k}`))
    const why = entries.map(([k, n]) => `${word(k)}${entries.length > 1 ? ` ${n}` : ''}`).join(', ')
    parts.push(t('diag.notPlanting', { n: diag.not_planting.total, why }))
  }
  if (diag.left_out_by_field_check) parts.push(t('diag.leftOut', { n: diag.left_out_by_field_check }))
  const what = t(diag.kind === 'polygon' ? 'diag.what.polygon' : diag.kind === 'zone' ? 'diag.what.zone' : 'diag.what.barangay')
  let text = t('diag.touched', { n: diag.touched, what, parts: parts.join(', ') })
  if (diag.kind === 'polygon' && diag.squares) {
    text += ` ${t('diag.counted', { n: diag.counted_squares })}`
    if (diag.partial_squares > 0) text += ` ${t('diag.partial', { n: diag.partial_squares })}`
  }
  return text
}
