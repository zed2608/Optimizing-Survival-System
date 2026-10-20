// What the "Area" step says about the chosen point, barangay, zone or drawn shape, and when "Continue" may be pressed. Pure functions (tested in areaInfo.test.mjs). Filipino first.
import { geometryContains } from './geo.js'

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
export const haText = (ha) => (ha < 0.1 ? 'mas mababa sa 0,1 ektarya' : `${String(hasArea(ha)).replace('.', ',')} ektarya`)

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

const TYPE = { barangay: 'barangay', zone: 'zone (uri ng lupa sa zoning map)', polygon: 'iginuhit na lugar', point: 'isang puntos' }

// lines of the summary: [{label, value}] for the chosen point (tool 'point'), barangay, zone or drawn shape.
// ctx = { tool, area, spot, geometry, barangayFeatures, zoneFeatures, squares } ; squares = the number of planting squares the service found in the area (or null)
export function describeArea({ tool, area, spot, barangayFeatures = [], zoneFeatures = [], squares = null, selection = null }) {
  const rows = []
  if (area) {
    if (area.kind === 'barangay') {
      const f = barangayFeatures.find((b) => b.properties.name === area.name)
      rows.push({ label: 'Paraan', value: tool === 'barangay' ? 'Barangay (pinili sa mapa o sa listahan)' : 'Barangay' })
      rows.push({ label: 'Pangalan', value: f?.properties.display_name ?? area.name })
      rows.push({ label: 'Uri', value: TYPE.barangay })
    } else if (area.kind === 'zone') {
      rows.push({ label: 'Paraan', value: 'Zone (pinili sa listahan)' })
      rows.push({ label: 'Pangalan', value: area.name })
      rows.push({ label: 'Uri', value: TYPE.zone })
    } else {
      const ha = geometryHectares(area.geometry)
      const bs = barangaysOfShape(area.geometry, barangayFeatures)
      rows.push({ label: 'Paraan', value: 'Iginuhit sa mapa' })
      rows.push({ label: 'Pangalan', value: 'Iginuhit na lugar' })
      if (bs.length) rows.push({ label: bs.length > 1 ? 'Mga barangay' : 'Barangay', value: `${bs.join(', ')} (batay sa mga sulok at gitna)` })
      rows.push({ label: 'Uri', value: TYPE.polygon })
      rows.push({ label: 'Laki ng iginuhit', value: ha < 0.1 ? haText(ha) : `mga ${haText(ha)}` })
    }
    if (squares != null) rows.push({ label: 'Mga planting square', value: `${squares} (bawat isa ay mga 1 ektarya)` })
    if (selection === 'touching') rows.push({ label: 'Paalala', value: 'Mas maliit ito sa isang square, kaya ginamit ang mga square na tinatamaan ng lugar.' })
    return rows
  }
  if (tool === 'point' && spot) {
    const b = barangayFeatures.find((f) => geometryContains(f.geometry, spot.lon, spot.lat))
    const z = zoneFeatures.find((f) => geometryContains(f.geometry, spot.lon, spot.lat))
    rows.push({ label: 'Paraan', value: 'Isang puntos (pinili sa mapa)' })
    rows.push({ label: 'Barangay', value: b?.properties.display_name ?? 'Wala sa mapa ng barangay' })
    rows.push({ label: 'Zone', value: z?.properties.name ?? 'Wala sa zoning map (Forest Reserve ayon sa CLUP)' })
    rows.push({ label: 'Uri', value: TYPE.point })
  }
  return rows
}

// May the person go on to the next step? mode 'area': a chosen area that holds at least one planting square. areaRank = { status, error: { status, message } } of POST /rank/area.
export function continueState({ mode, area, areaRank }) {
  if (mode !== 'area') return { ok: true, reason: '' }
  if (!area) return { ok: false, reason: 'Pumili muna ng lugar: pindutin ang isang barangay, pumili sa listahan, o gumuhit sa mapa.' }
  const e = areaRank?.status === 'error' ? areaRank.error : null
  if (e && e.status === 400 && String(e.message).includes('no legal-zone grid points')) {
    return { ok: false, reason: 'Walang planting square sa lugar na ito. Iguhit ito sa ibabaw ng mga may kulay na parisukat, o pumili ng barangay o zone.' }
  }
  if (areaRank?.status === 'loading') return { ok: false, reason: 'Sinusuri ang lugar…' }
  return { ok: true, reason: '' }
}
