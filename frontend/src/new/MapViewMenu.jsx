import { useEffect, useId, useRef, useState } from 'react'
import Icon from './Icon.jsx'
import HelpTip from './HelpTip.jsx'

// One small "Map view" button at the top right of the map. Its menu holds the map type (satellite or street map) and the field-checked points layer.
// Escape or a click elsewhere closes it.
export default function MapViewMenu({ baseLayer, onBaseLayer, showField, onShowField, showOther, onShowOther, showPlan = true, onShowPlan = () => {}, hasPlan = false, detailed = false, onDetailed = () => {}, showGround = false, onShowGround = () => {}, showZoning = false, onShowZoning = () => {}, satellite = null }) {
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
      <button type="button" className="nw-mapview-btn" data-tour="m-mapview" aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}>
        <Icon name="layers" /> Map view <Icon name={open ? 'up' : 'down'} size={14} />
      </button>
      {open && (
        <div id={id} className="nw-mapview-menu" role="group" aria-label="Map view" data-tour="m-mapview-menu">
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
            <legend className="nw-mapview-legend">
              Map type <HelpTip label="About the satellite view">This is an aerial imagery basemap (Esri World Imagery), not a live feed - satellites don't provide real-time video. Coverage dates vary by area and the provider doesn't publish an exact capture date per tile, so a change on the ground (a new building, a cleared lot, a tree that grew in) may not show here yet. Use it to judge terrain and existing cover, not as today's picture.</HelpTip>
            </legend>
            {[
              ['satellite', 'Satellite', null],
              ['street', 'Street map', null],
              ...(satellite?.available
                ? [
                    ['optical', 'Recent satellite photo', satellite.layers?.optical?.note],
                    ['radar', 'Radar change view', satellite.layers?.radar?.note],
                  ]
                : []),
            ].map(([v, l, note]) => (
              <label key={v} className="nw-mapview-row">
                <input type="radio" name="nw-basemap" checked={baseLayer === v} onChange={() => onBaseLayer(v)} />
                <span>{l}</span>
                {note ? <HelpTip label={`About ${l.toLowerCase()}`}>{note}</HelpTip> : null}
              </label>
            ))}
            {!satellite?.available && (
              <p className="nw-mapview-note">A recent-satellite-photo and radar view can be added here once Sentinel Hub credentials are set up for this deployment.</p>
            )}
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
            <input id="nw-show-zoning" type="checkbox" checked={showZoning} onChange={(e) => onShowZoning(e.target.checked)} />
            <span>Zoning (MPDC colours)</span>
          </label>
          <label className="nw-mapview-row">
            <input id="nw-show-ground" type="checkbox" checked={showGround} onChange={(e) => onShowGround(e.target.checked)} />
            <span>Ground cover (satellite 2021)</span>
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
