import { useEffect } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'
import { ZONE_FILL_OPACITY, ZONE_LINE_WEIGHT, zoneColor } from './zoneColors.js'

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
      style: (f) => ({ color: zoneColor(f.properties.name), weight: ZONE_LINE_WEIGHT, opacity: 0.85, fillColor: zoneColor(f.properties.name), fillOpacity: ZONE_FILL_OPACITY }),
    }).addTo(map)
    return () => {
      layer.remove()
    }
  }, [map, zoning, visible])
  return null
}
