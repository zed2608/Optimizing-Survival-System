import { useEffect, useId, useRef, useState } from 'react'
import Icon from './Icon.jsx'

// One small "Map view" button at the top right of the map. Its menu holds the map type (satellite or street map) and the field-checked points layer.
// Escape or a click elsewhere closes it.
export default function MapViewMenu({ baseLayer, onBaseLayer, showField, onShowField, showOther, onShowOther, showPlan = true, onShowPlan = () => {}, hasPlan = false, detailed = false, onDetailed = () => {} }) {
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
        <Icon name="layers" /> Map view <Icon name={open ? 'up' : 'down'} size={14} />
      </button>
      {open && (
        <div id={id} className="nw-mapview-menu" role="group" aria-label="Map view">
          <div className="nw-detailseg" role="radiogroup" aria-label="How much to show on the map">
            {[
              [false, 'Simple'],
              [true, 'Detailed'],
            ].map(([v, l]) => (
              <button key={l} type="button" role="radio" aria-checked={detailed === v} className={`nw-detailbtn ${detailed === v ? 'is-active' : ''}`} onClick={() => onDetailed(v)}>
                {l}
              </button>
            ))}
          </div>
          <p className="nw-mapview-note">Simple: coloured squares, outlines and names. Detailed adds every field-check symbol, the tree codes and the grey squares. Your own plan and the points you mark always show.</p>
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
            <span>Field-checked points{detailed ? '' : ' (all: Detailed)'}</span>
          </label>
          <label className="nw-mapview-row">
            <input id="nw-show-plan" type="checkbox" checked={showPlan} onChange={(e) => onShowPlan(e.target.checked)} />
            <span>Planned trees{hasPlan ? '' : ' (no plan yet)'}</span>
          </label>
          <label className="nw-mapview-row">
            <input id="nw-show-other" type="checkbox" checked={showOther} onChange={(e) => onShowOther(e.target.checked)} />
            <span>Other map squares (not planting zones){detailed ? '' : ' (Detailed)'}</span>
          </label>
        </div>
      )}
    </div>
  )
}
