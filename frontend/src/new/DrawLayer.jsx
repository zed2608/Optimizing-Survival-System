import { useEffect } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'

const PANE = 'nw-draw'

// The area being drawn: the clicked corners, joined by a line, with the closing edge dashed once there are three corners.
// (Our own small tool: no drawing package and no changes to the global Leaflet object.)
export default function DrawLayer({ vertices }) {
  const map = useMap()
  useEffect(() => {
    if (!vertices || vertices.length === 0) return undefined
    if (!map.getPane(PANE)) {
      const pane = map.createPane(PANE)
      pane.style.zIndex = 460
      pane.style.pointerEvents = 'none'
    }
    const group = L.featureGroup()
    const style = { pane: PANE, interactive: false, color: '#fbbf24', weight: 3 }
    if (vertices.length >= 3) L.polygon(vertices, { ...style, dashArray: '6 5', fillColor: '#fbbf24', fillOpacity: 0.12 }).addTo(group)
    else if (vertices.length === 2) L.polyline(vertices, style).addTo(group)
    vertices.forEach((v, i) => {
      L.circleMarker(v, { pane: PANE, interactive: false, radius: i === 0 ? 7 : 5, color: '#0f172a', weight: 2, fillColor: i === 0 ? '#22c55e' : '#fbbf24', fillOpacity: 1 }).addTo(group)
    })
    group.addTo(map)
    return () => {
      group.remove()
    }
  }, [map, vertices])
  return null
}
