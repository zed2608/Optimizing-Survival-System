import { useEffect } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'

const PANE = 'nw-highlight'

// Highlights one area (a barangay, a zone or a drawn polygon): a thick cyan outline over a light fill. It ignores the mouse.
export default function HighlightLayer({ geometry }) {
  const map = useMap()
  useEffect(() => {
    if (!geometry) return undefined
    if (!map.getPane(PANE)) {
      const pane = map.createPane(PANE)
      pane.style.zIndex = 455
      pane.style.pointerEvents = 'none'
    }
    const layer = L.geoJSON(geometry, { pane: PANE, interactive: false, style: () => ({ color: '#22d3ee', weight: 4, opacity: 1, fillColor: '#22d3ee', fillOpacity: 0.12 }) })
    layer.addTo(map)
    return () => {
      layer.remove()
    }
  }, [map, geometry])
  return null
}
