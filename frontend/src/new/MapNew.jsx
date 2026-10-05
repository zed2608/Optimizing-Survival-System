import { useEffect } from 'react'
import L from 'leaflet'
import { MapContainer, TileLayer, useMap, ZoomControl } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { MAP_BOUNDS, MAP_CENTER } from '../v2/config.js'
import BoundaryLayers from './BoundaryLayers.jsx'
import DrawLayer from './DrawLayer.jsx'
import GridLayer from './GridLayer.jsx'
import HighlightLayer from './HighlightLayer.jsx'
import { RIGHT_PANEL_WIDTH, SIDEBAR_WIDTH } from './layout.js'

const MARGIN = 0.06 // panning may go this much (share of the size) beyond the municipality
const TOP_PAD = 84 // room for the top bar when fitting
const SIDE_PAD = 24
const ZOOM_OUT_EXTRA = 0.5 // how far beyond the fitted zoom the user may zoom out

function bboxToBounds(b) {
  return L.latLngBounds([b[1], b[0]], [b[3], b[2]])
}

// Fits the whole municipality in the free part of the map (not under the sidebar), then limits panning to that view plus the municipality
// and a small margin, and limits zooming out to half a zoom level beyond the fit. Uses the bbox of GET /geo/boundaries (the config box
// if the API is off). The pan limit is set AFTER the fit and includes the fitted view: Leaflet would otherwise re-centre the map in the
// full window and push part of the municipality under the sidebar.
function FitToMunicipality({ bbox }) {
  const map = useMap()
  useEffect(() => {
    const bounds = bbox ? bboxToBounds(bbox) : L.latLngBounds(MAP_BOUNDS)
    map.setMaxBounds(null)
    map.setMinZoom(0)
    map.fitBounds(bounds, { paddingTopLeft: [SIDEBAR_WIDTH + SIDE_PAD, TOP_PAD], paddingBottomRight: [SIDE_PAD, SIDE_PAD], animate: false })
    map.setMaxBounds(map.getBounds().extend(bounds.pad(MARGIN)))
    map.setMinZoom(map.getZoom() - ZOOM_OUT_EXTRA)
  }, [map, bbox])
  return null
}

// Zoom to an area (a clicked table row, a chosen barangay or zone): fit its bbox between the sidebar and the right-hand panel.
function FitTarget({ target }) {
  const map = useMap()
  useEffect(() => {
    if (!target) return
    const b = L.latLngBounds([target.bbox[1], target.bbox[0]], [target.bbox[3], target.bbox[2]])
    map.fitBounds(b, { paddingTopLeft: [SIDEBAR_WIDTH + SIDE_PAD, TOP_PAD], paddingBottomRight: [RIGHT_PANEL_WIDTH + 2 * SIDE_PAD, SIDE_PAD], maxZoom: 17, animate: false })
  }, [target, map])
  return null
}

// "Go to this spot": jump to a place and zoom in (no animation, so the canvas layer never shows a stale frame).
function GoTo({ target }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.setView([target.lat, target.lon], Math.max(map.getZoom(), 16), { animate: false })
  }, [target, map])
  return null
}

// Satellite (default) or street map (chosen in the sidebar Options), zoom buttons, the outlines + names, and the grid layer.
const BASE_LAYERS = {
  satellite: { url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attribution: '&copy; Esri &mdash; World Imagery' },
  street: { url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: '&copy; OpenStreetMap contributors' },
}

export default function MapNew({ bbox, boundaries, grid, clearGrid, labeler, selected, spot, onPick, meta, goTarget, fitTarget, highlight, draft, drawing, field, baseLayer = 'satellite' }) {
  const base = BASE_LAYERS[baseLayer] ?? BASE_LAYERS.satellite
  return (
    <MapContainer
      center={MAP_CENTER}
      zoom={12}
      zoomSnap={0.25}
      zoomDelta={0.5}
      zoomAnimation={false}
      maxBoundsViscosity={1.0}
      zoomControl={false}
      className={drawing ? 'nw-drawing' : ''}
      style={{ height: '100%', width: '100%', background: '#0b1220' }}
    >
      <TileLayer key={baseLayer} url={base.url} attribution={base.attribution} maxZoom={19} />
      <ZoomControl position="topright" />
      <FitToMunicipality bbox={bbox} />
      <GoTo target={goTarget} />
      <FitTarget target={fitTarget} />
      <BoundaryLayers boundaries={boundaries} />
      <HighlightLayer geometry={highlight} />
      <DrawLayer vertices={draft} />
      <GridLayer columns={grid} clear={clearGrid} labeler={labeler} selected={selected} spot={spot} onPick={onPick} meta={meta} field={field} />
    </MapContainer>
  )
}
