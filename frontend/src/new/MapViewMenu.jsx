import { useEffect, useId, useRef, useState } from 'react'

// One small "Map view" button at the top right of the map. Its menu holds the map type (satellite or street map) and the field-checked points layer.
// Escape or a click elsewhere closes it.
export default function MapViewMenu({ baseLayer, onBaseLayer, showField, onShowField }) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const box = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => {
      if (box.current && !box.current.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])
  return (
    <div
      className="nw-mapview"
      ref={box}
      onKeyDown={(e) => {
        if (e.key === 'Escape') setOpen(false)
      }}
    >
      <button type="button" className="nw-mapview-btn" aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}>
        <span aria-hidden="true">▤</span> Map view <span aria-hidden="true">{open ? '▴' : '▾'}</span>
      </button>
      {open && (
        <div id={id} className="nw-mapview-menu" role="group" aria-label="Map view">
          <fieldset className="nw-fieldset">
            <legend className="nw-mapview-legend">Map type</legend>
            {[
              ['satellite', 'Satellite'],
              ['street', 'Street map'],
            ].map(([v, l]) => (
              <label key={v} className="nw-mapview-row">
                <input type="radio" name="nw-basemap" checked={baseLayer === v} onChange={() => onBaseLayer(v)} />
                <span>{l}</span>
              </label>
            ))}
          </fieldset>
          <label className="nw-mapview-row nw-mapview-check">
            <input id="nw-show-field" type="checkbox" checked={showField} onChange={(e) => onShowField(e.target.checked)} />
            <span>Field-checked points</span>
          </label>
        </div>
      )}
    </div>
  )
}
