import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import { createGridLayer } from './gridLayer.js'

// React wrapper around the canvas layer: it only passes data in. Nothing is rendered per point.
//   columns   the `columns` of GET /grid (null while loading: the old points stay until new ones arrive, unless `clear` is set)
//   labeler   (index) -> lines of text for the hover tooltip
//   selected  index of the selected point (or -1), spot = {lat, lon} of the last click (or null)
export default function GridLayer({ columns, clear, labeler, selected, spot, onPick, meta, field, contextCols, contextVisible, contextLabeler, safeArea, planItems, planVisible, planLabeler, detailed = false, ground = null, groundOn = false }) {
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
    layerRef.current?.setPlan(planItems ?? null)
  }, [planItems])
  useEffect(() => {
    layerRef.current?.setPlanVisible(planVisible)
  }, [planVisible, planItems])
  useEffect(() => {
    layerRef.current?.setPlanLabeler(planLabeler)
  }, [planLabeler])
  useEffect(() => {
    layerRef.current?.setDetailed(detailed)
    layerRef.current?.setCorners(detailed)
  }, [detailed])
  useEffect(() => {
    layerRef.current?.setGround(ground)
  }, [ground, columns])
  useEffect(() => {
    layerRef.current?.setGroundMode(groundOn)
  }, [groundOn])
  useEffect(() => {
    if (safeArea) layerRef.current?.setSafeArea(safeArea)
  }, [safeArea])
  useEffect(() => {
    layerRef.current?.setContext(contextCols ?? null)
  }, [contextCols])
  useEffect(() => {
    layerRef.current?.setContextVisible(contextVisible)
  }, [contextVisible, contextCols])
  useEffect(() => {
    layerRef.current?.setContextLabeler(contextLabeler)
  }, [contextLabeler])
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
