import { useEffect } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'

const PANE = 'nw-areasq'
const M_PER_DEG = 111320

// After a drawn area is finished: the squares that were COUNTED (solid cyan) and the planting squares the area only touches a little (dashed grey, not counted: less than half covered and the
// centre outside). squares = { counted: [[lon, lat]], partial: [[lon, lat]], half_size_m } from POST /area/diagnostic. Display only; nothing here changes a score.
// Each kind is ONE multi-polygon (two map elements in all, however many squares: a large area has more than a thousand).
export default function AreaSquaresLayer({ squares }) {
  const map = useMap()
  useEffect(() => {
    if (!squares || (squares.counted.length === 0 && squares.partial.length === 0)) return undefined
    if (!map.getPane(PANE)) {
      const pane = map.createPane(PANE)
      pane.style.zIndex = 455
      pane.style.pointerEvents = 'none'
    }
    const half = squares.half_size_m ?? 50
    const ring = ([lon, lat]) => {
      const dlat = half / M_PER_DEG
      const dlon = half / (M_PER_DEG * Math.cos((lat * Math.PI) / 180))
      return [[[lat - dlat, lon - dlon], [lat - dlat, lon + dlon], [lat + dlat, lon + dlon], [lat + dlat, lon - dlon]]]
    }
    const group = L.featureGroup()
    if (squares.partial.length) L.polygon(squares.partial.map(ring), { pane: PANE, interactive: false, color: '#e5e7eb', weight: 1.5, dashArray: '4 4', fill: false, opacity: 0.95 }).addTo(group)
    if (squares.counted.length) L.polygon(squares.counted.map(ring), { pane: PANE, interactive: false, color: '#22d3ee', weight: 2, fillColor: '#22d3ee', fillOpacity: 0.28 }).addTo(group)
    group.addTo(map)
    return () => {
      group.remove()
    }
  }, [map, squares])
  return null
}
