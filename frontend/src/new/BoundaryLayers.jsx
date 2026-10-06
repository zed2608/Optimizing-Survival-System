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
    line(municipality, { color: '#0f172a', weight: 4, opacity: 0.3, fill: false }).addTo(group)
    line(barangays, { color: '#f1f5f9', weight: 1, opacity: 0.5, dashArray: '4 4', fill: false }).addTo(group)
    line(municipality, { color: '#fde68a', weight: 1.8, opacity: 0.85, fill: false }).addTo(group)
    const labels = []
    barangays.forEach((f) => {
      const p = f.properties
      const tip = L.tooltip({ permanent: true, direction: 'center', className: 'nw-brgy-label', interactive: false })
        .setLatLng([p.label_point.lat, p.label_point.lon])
        .setContent(p.display_name)
        .addTo(group)
      const b = p.bbox
      labels.push({ tip, area: (b[2] - b[0]) * (b[3] - b[1]) })
    })
    group.addTo(map)
    // hide the labels that would overlap an already shown one (the larger barangays win)
    const declutter = () => {
      const placed = []
      labels
        .slice()
        .sort((a, b) => b.area - a.area)
        .forEach(({ tip }) => {
          const el = tip.getElement()
          if (!el) return
          el.style.visibility = 'visible'
          const r = el.getBoundingClientRect()
          const hit = placed.some((q) => !(r.right + 4 < q.left || r.left - 4 > q.right || r.bottom + 2 < q.top || r.top - 2 > q.bottom))
          if (hit) el.style.visibility = 'hidden'
          else placed.push(r)
        })
    }
    const later = () => requestAnimationFrame(declutter)
    map.on('zoomend moveend resize', later)
    later()
    setTimeout(declutter, 300)
    return () => {
      map.off('zoomend moveend resize', later)
      group.remove()
    }
  }, [map, boundaries])
  return null
}
