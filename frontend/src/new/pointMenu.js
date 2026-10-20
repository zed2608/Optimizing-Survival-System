// The lines at the top of the map menu of a square (right-click, long press): where it is, what zone, the planting window and the day of viewing, and how far the click was from the square's centre.
// Pure (tested in pointMenu.test.mjs). The wording is the one of the point panel's header card (LocationCard.jsx).
import { formatDay } from './season.js'
import { geometryContains } from './geo.js'

const R = 6371000

// metres between two points (haversine)
export function distanceM(lat1, lon1, lat2, lon2) {
  const rad = (d) => (d * Math.PI) / 180
  const a = Math.sin(rad(lat2 - lat1) / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

const nameOf = (features, lon, lat, key) => {
  const f = (features ?? []).find((x) => geometryContains(x.geometry, lon, lat))
  return f ? (f.properties[key] ?? f.properties.name ?? null) : null
}

// the three lines: "Guinayang" / "Agricultural Zone, grid 1921" / "Planting window 20 Oct - 29 Dec 2026, viewed 20 Oct 2026" and, from 1 m, "1 m from where you clicked".
// square = { lat, lon, pointId } (centre of the square), click = { lat, lon }
export function menuLines({ square, click, barangayFeatures, zoneFeatures, win, today }) {
  const barangay = nameOf(barangayFeatures, square.lon, square.lat, 'display_name') ?? 'Outside the barangay outlines'
  const zone = nameOf(zoneFeatures, square.lon, square.lat, 'name') ?? 'Outside our zoning map'
  const away = Math.round(click ? distanceM(click.lat, click.lon, square.lat, square.lon) : 0)
  const lines = [`${barangay} / ${zone}, grid ${square.pointId}`, `Planting window ${formatDay(win.start)} - ${formatDay(win.end, true)}, viewed ${formatDay(today, true)}`]
  if (away >= 1) lines.push(`${away} m from where you clicked`)
  return { title: barangay, barangay, zone, lines }
}
