import { useEffect } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'
import { ZONE_FILL_OPACITY, ZONE_LINE_WEIGHT, zoneColor, zoneHatch } from './zoneColors.js'

const HATCH_ID = 'nw-zone-hatch'
// One hidden SVG pattern (zone colour at low opacity + blue lines at 45 degrees), made once and used by the Agricultural Zone polygons.
function ensureHatch() {
  if (document.getElementById(HATCH_ID)) return
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('width', '0')
  svg.setAttribute('height', '0')
  svg.style.position = 'absolute'
  svg.innerHTML = `<defs><pattern id="${HATCH_ID}" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="8" fill="${zoneColor('Agricultural Zone')}" fill-opacity="0.25"/><line x1="0" y1="0" x2="0" y2="8" stroke="#0000ff" stroke-width="1.5" stroke-opacity="0.55"/></pattern></defs>`
  document.body.appendChild(svg)
}

const PANE = 'nw-zoning'

// The optional Zoning overlay: every zone of the land-use layer in its MPDC colour, a thin outline and a low-opacity fill. The pane lies BELOW the grid squares and ignores the mouse,
// so the suitability dots keep their own scale and every click and hover still reaches them. `zoning` = the GeoJSON of GET /geo/zoning.
export default function ZoningLayer({ zoning, visible }) {
  const map = useMap()
  useEffect(() => {
    if (!zoning || !visible) return undefined
    if (!map.getPane(PANE)) {
      const pane = map.createPane(PANE)
      pane.style.zIndex = 380 // above the base map (200 to 300), below the grid squares (400)
      pane.style.pointerEvents = 'none'
    }
    const layer = L.geoJSON(zoning, {
      pane: PANE,
      interactive: false,
      style: (f) => {
        const n = f.properties.name
        if (zoneHatch(n)) {
          ensureHatch()
          return { color: zoneColor(n), weight: ZONE_LINE_WEIGHT, opacity: 0.85, fillColor: `url(#${HATCH_ID})`, fillOpacity: 1 }
        }
        return { color: zoneColor(n), weight: ZONE_LINE_WEIGHT, opacity: 0.85, fillColor: zoneColor(n), fillOpacity: ZONE_FILL_OPACITY }
      },
    }).addTo(map)
    return () => {
      layer.remove()
    }
  }, [map, zoning, visible])
  return null
}
