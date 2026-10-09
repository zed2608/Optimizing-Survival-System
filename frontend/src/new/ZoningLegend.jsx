import { useState } from 'react'
import AskHelp from './tutorial/AskHelp.jsx'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import ProvisionalTag from './ProvisionalTag.jsx'
import { ZONE_CREDIT, ZONE_UNSTYLED_NOTE, legendOrder, zoneColor, zoneColorName, zoneHatch } from './zoneColors.js'

// The legend of the Zoning overlay: the colour, the zone name and the number of grid squares of each zone; a hint where a zone needs permission.
export default function ZoningLegend({ api, onHide, onExpand = () => {} }) {
  const [open, setOpen] = useState(false) // collapsed to one line until asked: the long list must not cover the map or the other legends
  const d = api.status === 'ok' ? api.data : null
  return (
    <div className="nw-zoning-legend v2 v2-embedded" role="group" aria-label="Zoning legend">
      <div className="nw-legend-head">
        <strong>Zoning</strong>
        <AskHelp id="zoning-layer" />
        <span className="nw-zbtns">
          <button type="button" className="btn btn-small" aria-expanded={open} onClick={() => { if (!open) onExpand(); setOpen(!open) }}>
            {open ? 'Hide list' : 'Show list'}
          </button>
          <button type="button" className="btn btn-small" onClick={onHide}>
            Hide layer
          </button>
        </span>
      </div>
      {api.status === 'loading' && <Loading what="Loading the zoning" />}
      {api.status === 'error' && <ErrorBox error={api.error} onRetry={api.retry} title="Could not load the zoning" brief />}
      {d && open && (
        <>
          <ul className="nw-zlist">
            {legendOrder(d.features).map((f) => {
              const p = f.properties
              return (
                <li key={p.name} title={`${zoneColorName(p.name)}${p.condition ? ': ' + p.condition : ''}`}>
                  <span className={`nw-zswatch${zoneHatch(p.name) ? ' nw-zswatch-hatch' : ''}`} style={{ '--zc': zoneColor(p.name), background: zoneHatch(p.name) ? undefined : zoneColor(p.name) }} aria-hidden="true" />
                  <span className="nw-zname">{p.name}</span>
                  <span className="nw-zcount">{p.grid_squares.toLocaleString('en-US')}</span>
                </li>
              )
            })}
            <li title={d.outside_map.condition}>
              <span className="nw-zswatch nw-zswatch-out" aria-hidden="true" />
              <span className="nw-zname">{d.outside_map.name}</span>
              <span className="nw-zcount">{d.outside_map.grid_squares.toLocaleString('en-US')}</span>
            </li>
          </ul>
          <div className="nw-legend-note">
            {ZONE_CREDIT}. {ZONE_UNSTYLED_NOTE}
          </div>
          <div className="nw-legend-note">
            Numbers are grid squares of 100 m. Hover a name for the condition. Rules from the MPDC form of 7 Oct 2026 <ProvisionalTag />
          </div>
        </>
      )}
    </div>
  )
}
