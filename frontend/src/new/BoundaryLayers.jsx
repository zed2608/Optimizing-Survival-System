import { useEffect } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'

const PANE = 'nw-boundaries'

// The municipal outline and the barangay outlines (always on) with the barangay names as labels. Lines ignore the mouse,
// so clicks and hovers reach the points underneath. `boundaries` is the GeoJSON of GET /geo/boundaries.
export default function BoundaryLayers({ boundaries }) {
  const map = useMap()
  useEffect(() => {
    if (!boundaries) return undefined
    if (!map.getPane(PANE)) {
      const pane = map.createPane(PANE)
      pane.style.zIndex = 450 // above the grid points (400), below tooltips (650)
      pane.style.pointerEvents = 'none'
    }
    const municipality = boundaries.features.filter((f) => f.properties.kind === 'municipality')
    const barangays = boundaries.features.filter((f) => f.properties.kind === 'barangay')
    const group = L.layerGroup()
    const line = (features, style) => L.geoJSON({ type: 'FeatureCollection', features }, { pane: PANE, interactive: false, style: () => style })
    line(municipality, { color: '#0f172a', weight: 7, opacity: 0.55, fill: false }).addTo(group)
    line(barangays, { color: '#f8fafc', weight: 1.4, opacity: 0.9, dashArray: '5 4', fill: false }).addTo(group)
    line(municipality, { color: '#fde68a', weight: 3, opacity: 1, fill: false }).addTo(group)
    barangays.forEach((f) => {
      const p = f.properties
      L.tooltip({ permanent: true, direction: 'center', className: 'nw-brgy-label', interactive: false })
        .setLatLng([p.label_point.lat, p.label_point.lon])
        .setContent(p.display_name)
        .addTo(group)
    })
    group.addTo(map)
    return () => {
      group.remove()
    }
  }, [map, boundaries])
  return null
}
