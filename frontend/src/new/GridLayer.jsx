import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import { createGridLayer } from './gridLayer.js'

// React wrapper around the canvas layer: it only passes data in. Nothing is rendered per point.
//   columns   the `columns` of GET /grid (null while loading: the old points stay until new ones arrive, unless `clear` is set)
//   labeler   (index) -> lines of text for the hover tooltip
//   selected  index of the selected point (or -1), spot = {lat, lon} of the last click (or null)
export default function GridLayer({ columns, clear, labeler, selected, spot, onPick, meta, field }) {
  const map = useMap()
  const layerRef = useRef(null)

  useEffect(() => {
    const layer = createGridLayer()
    layer.addTo(map)
    layerRef.current = layer
    return () => {
      layer.remove()
      layerRef.current = null
    }
  }, [map])

  useEffect(() => {
    if (columns) layerRef.current?.setData(columns)
    else if (clear) layerRef.current?.setData(null)
  }, [columns, clear])

  useEffect(() => {
    layerRef.current?.setLabeler(labeler)
  }, [labeler])
  useEffect(() => {
    layerRef.current?.setHandlers({ onPick })
  }, [onPick])
  useEffect(() => {
    layerRef.current?.setSelected(selected)
  }, [selected, columns])
  useEffect(() => {
    layerRef.current?.setSpot(spot ? spot.lat : null, spot ? spot.lon : null)
  }, [spot])
  useEffect(() => {
    layerRef.current?.setMeta(meta)
  }, [meta, columns])
  useEffect(() => {
    layerRef.current?.setField(field)
  }, [field, columns])
  return null
}
