// Parse what a person types as a place: decimal degrees ("14.69, 121.12", "14.69 121.12", "14.69N 121.12E") or UTM zone 51N metres ("296799 1625091").
// Pure functions, no browser APIs, so they are tested with node (coords.test.mjs).
// Returns { ok: true, lat, lon, kind: 'latlon' | 'utm', note } or { ok: false, reason }. Anything it cannot read is rejected, never guessed.

const UTM_ZONE = 51 // San Mateo, Rizal (WGS84, northern hemisphere); central meridian 123 deg E
const K0 = 0.9996
const E0 = 500000
const A = 6378137
const F = 1 / 298.257223563

// Kruger series for the inverse transverse Mercator (accurate to well under a millimetre inside a zone).
export function utmToLatLon(easting, northing, zone = UTM_ZONE) {
  const n = F / (2 - F)
  const a1 = A / (1 + n) * (1 + n ** 2 / 4 + n ** 4 / 64)
  const beta = [n / 2 - (2 / 3) * n ** 2 + (37 / 96) * n ** 3, n ** 2 / 48 + n ** 3 / 15, (17 / 480) * n ** 3]
  const delta = [2 * n - (2 / 3) * n ** 2 - 2 * n ** 3, (7 / 3) * n ** 2 - (8 / 5) * n ** 3, (56 / 15) * n ** 3]
  const xi = northing / (K0 * a1)
  const eta = (easting - E0) / (K0 * a1)
  let xi0 = xi
  let eta0 = eta
  beta.forEach((b, i) => {
    const j = 2 * (i + 1)
    xi0 -= b * Math.sin(j * xi) * Math.cosh(j * eta)
    eta0 -= b * Math.cos(j * xi) * Math.sinh(j * eta)
  })
  const chi = Math.asin(Math.sin(xi0) / Math.cosh(eta0))
  let lat = chi
  delta.forEach((dl, i) => {
    lat += dl * Math.sin(2 * (i + 1) * chi)
  })
  const lon0 = (zone * 6 - 183) * (Math.PI / 180)
  const lon = lon0 + Math.atan2(Math.sinh(eta0), Math.cos(xi0))
  return { lat: (lat * 180) / Math.PI, lon: (lon * 180) / Math.PI }
}

const NUM = String.raw`[-+]?\d+(?:\.\d+)?`

function toNum(t) {
  return Number(t)
}

export function parseCoordinates(input) {
  if (typeof input !== 'string') return { ok: false, reason: 'Type two numbers, for example 14.69, 121.12.' }
  let t = input.trim()
  if (!t) return { ok: false, reason: 'Type two numbers, for example 14.69, 121.12.' }

  // UTM: two whole-ish numbers of 6-7 digits, optional zone token "51N" / "51" / "51 N" / "zone 51N" anywhere before or after.
  const utm = t.match(/^(?:zone\s*)?(?:(\d{1,2})\s*([NSns])?[\s,;]+)?(\d{5,7}(?:\.\d+)?)[\s,;]+(\d{6,8}(?:\.\d+)?)(?:[\s,;]+(\d{1,2})\s*([NSns])?)?$/i)
  if (utm) {
    const zone = Number(utm[1] ?? utm[5] ?? UTM_ZONE)
    const hemi = (utm[2] ?? utm[6] ?? 'N').toUpperCase()
    if (zone !== UTM_ZONE || hemi !== 'N') {
      return { ok: false, reason: `Only UTM zone ${UTM_ZONE}N (the zone of San Mateo) is supported; you typed zone ${zone}${hemi}.` }
    }
    const e = Number(utm[3])
    const n = Number(utm[4])
    if (e < 100000 || e > 900000 || n < 0 || n > 9500000) return { ok: false, reason: 'These UTM numbers are out of range (easting 100000-900000, northing 0-9500000).' }
    const { lat, lon } = utmToLatLon(e, n)
    return { ok: true, lat, lon, kind: 'utm', note: `UTM zone ${UTM_ZONE}N, easting ${e}, northing ${n}` }
  }

  // Decimal degrees with optional degree signs and N/S/E/W letters.
  t = t.replace(/[°º]/g, '')
  const m = t.match(new RegExp(`^(${NUM})\\s*([NSEWnsew])?\\s*[,;\\s]\\s*(${NUM})\\s*([NSEWnsew])?$`))
  if (!m) return { ok: false, reason: 'That does not look like coordinates. Try 14.69, 121.12 (latitude, longitude) or 296799 1625091 (UTM 51N).' }
  const a = toNum(m[1])
  const b = toNum(m[3])
  const la = (m[2] ?? '').toUpperCase()
  const lb = (m[4] ?? '').toUpperCase()
  // Letters decide which number is which; S and W make a number negative.
  let lat
  let lon
  if (la || lb) {
    const isLatLetter = (c) => c === 'N' || c === 'S'
    const isLonLetter = (c) => c === 'E' || c === 'W'
    if ((la && lb && isLatLetter(la) === isLatLetter(lb)) || (la && !lb) || (!la && lb)) {
      return { ok: false, reason: 'Put a letter on both numbers (for example 14.69N 121.12E), or on neither.' }
    }
    const sign = (v, c) => (c === 'S' || c === 'W' ? -Math.abs(v) : v)
    if (isLatLetter(la) && isLonLetter(lb)) {
      lat = sign(a, la)
      lon = sign(b, lb)
    } else {
      lon = sign(a, la)
      lat = sign(b, lb)
    }
  } else if (Math.abs(a) > 90 && Math.abs(b) <= 90) {
    lon = a // typed longitude first
    lat = b
  } else {
    lat = a
    lon = b
  }
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return { ok: false, reason: 'Those numbers could not be read.' }
  if (Math.abs(lat) > 90) return { ok: false, reason: 'Latitude must be between -90 and 90.' }
  if (Math.abs(lon) > 180) return { ok: false, reason: 'Longitude must be between -180 and 180.' }
  return { ok: true, lat, lon, kind: 'latlon', note: Math.abs(a) > 90 && !la && !lb ? 'Read as longitude, latitude (the first number is above 90).' : '' }
}
