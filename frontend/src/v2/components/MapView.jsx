import { useEffect } from 'react'
import { CircleMarker, LayersControl, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { MAP_BOUNDS, MAP_CENTER, MAP_MIN_ZOOM, MAP_ZOOM } from '../config.js'

function ClickHandler({ onPick }) {
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) })
  return null
}

// The map is kept mounted when another tab is shown, so it must be resized when it comes back.
function Resizer({ visible }) {
  const map = useMap()
  useEffect(() => {
    if (!visible) return undefined
    const t = setTimeout(() => map.invalidateSize(), 60)
    return () => clearTimeout(t)
  }, [visible, map])
  return null
}

function FlyTo({ target }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.flyTo([target.lat, target.lon], Math.max(map.getZoom(), 15), { duration: 0.8 })
  }, [target, map])
  return null
}

// Leaflet map of San Mateo. Click = choose a spot. Blue dot: where you clicked. Black ring: the 100 m grid point used. Green dashed ring: suggested spot.
export default function MapView({ spot, grid, viable, onPick, visible, flyTarget }) {
  return (
    <div className="map-wrap">
      <MapContainer
        center={MAP_CENTER}
        zoom={MAP_ZOOM}
        minZoom={MAP_MIN_ZOOM}
        maxBounds={MAP_BOUNDS}
        maxBoundsViscosity={0.9}
        style={{ height: '100%', width: '100%' }}
        aria-label="Map of San Mateo. Click a place to rank the species there, or type coordinates in the box next to the map."
      >
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Street map">
            <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" maxZoom={19} />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Satellite">
            <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" attribution="&copy; Esri &mdash; World Imagery" maxZoom={19} />
          </LayersControl.BaseLayer>
        </LayersControl>
        <ClickHandler onPick={onPick} />
        <Resizer visible={visible} />
        <FlyTo target={flyTarget} />
        {grid && (
          <CircleMarker center={[grid.lat, grid.lon]} radius={15} pathOptions={{ color: '#111111', weight: 3, fillOpacity: 0 }}>
            <Tooltip>Grid point used (a 100 m cell)</Tooltip>
          </CircleMarker>
        )}
        {viable && (
          <CircleMarker center={[viable.lat, viable.lon]} radius={13} pathOptions={{ color: '#1b5e20', weight: 3, dashArray: '4 4', fillColor: '#2e7d32', fillOpacity: 0.35 }}>
            <Tooltip>Suggested nearby spot</Tooltip>
          </CircleMarker>
        )}
        {spot && (
          <CircleMarker center={[spot.lat, spot.lon]} radius={7} pathOptions={{ color: '#ffffff', weight: 2, fillColor: '#0b4f9c', fillOpacity: 1 }}>
            <Tooltip>Where you clicked</Tooltip>
          </CircleMarker>
        )}
      </MapContainer>
      <p className="map-key" aria-hidden="true">
        <span className="dot dot-blue" /> clicked &nbsp; <span className="dot dot-ring" /> grid point used &nbsp; <span className="dot dot-green" /> suggested spot
      </p>
    </div>
  )
}
