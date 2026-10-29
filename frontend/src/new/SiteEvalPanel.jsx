import { useState } from 'react'
import Icon from './Icon.jsx'
import HelpTip from './HelpTip.jsx'
import FlagBadges from '../v2/components/FlagBadges.jsx'
import { fmt } from '../v2/scale.js'
import { usePost } from './usePost.js'

// round 23 (panel feedback): "it's much better if there's a planting site evaluation to manually input the
// characteristics before proceeding with a plan." A planter who has measured the real elevation, slope or soil at a
// spot - something that can differ from the grid's own 100 m estimate - can check what the system would say about
// THAT measurement. Nothing here is saved, nothing on the map or in any plan changes: it is a one-off calculation
// against the rule score only (never the Random Forest, which is only trained on real grid squares).
const SOIL_OPTIONS = [
  { value: '', label: 'Not measured' },
  { value: 'clay', label: 'Clay' },
  { value: 'clay loam', label: 'Clay loam' },
  { value: 'loam', label: 'Loam' },
  { value: 'sandy loam', label: 'Sandy loam' },
  { value: 'silt loam', label: 'Silt loam' },
]

export default function SiteEvalPanel({ purpose, pointId }) {
  const [open, setOpen] = useState(false)
  const [elev, setElev] = useState('')
  const [slope, setSlope] = useState('')
  const [soil, setSoil] = useState('')
  const [body, setBody] = useState(null)

  const run = (e) => {
    e.preventDefault()
    const b = { purpose }
    if (elev.trim() !== '') b.elev_m = Number(elev)
    if (slope.trim() !== '') b.slope_pct = Number(slope)
    if (soil !== '') b.soil_texture = soil
    if (pointId) b.point_id = pointId
    setBody(b)
  }

  const res = usePost('/site-eval', body)
  const nothingTyped = elev.trim() === '' && slope.trim() === '' && soil === ''

  return (
    <section className="nw-pcard nw-siteeval" aria-label="Planting site evaluation">
      <div className="nw-pcard-head">
        <button type="button" className="nw-siteeval-toggle" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          <Icon name="sliders" />
          <h3>Planting site evaluation</h3>
          <Icon name={open ? 'up' : 'down'} />
        </button>
        <HelpTip label="About this check">
          If you measured the elevation, slope or soil texture yourself and it differs from this square's own estimate, type what you
          measured to see the species ranking recomputed from it. This is your own one-off check: it is never saved, never shown on the
          map, and never counted in a plan. A box you leave blank is simply not evaluated, the same as a missing grid value.
        </HelpTip>
      </div>
      {open && (
        <>
          <form className="nw-siteeval-form" onSubmit={run}>
            <label className="nw-label" htmlFor="nw-eval-elev">Measured elevation (m)</label>
            <input id="nw-eval-elev" className="nw-input" type="number" min="0" max="2000" step="1" value={elev} onChange={(e) => setElev(e.target.value)} placeholder="not measured" />
            <label className="nw-label" htmlFor="nw-eval-slope">Measured slope (%)</label>
            <input id="nw-eval-slope" className="nw-input" type="number" min="0" max="200" step="1" value={slope} onChange={(e) => setSlope(e.target.value)} placeholder="not measured" />
            <label className="nw-label" htmlFor="nw-eval-soil">Measured soil texture</label>
            <select id="nw-eval-soil" className="nw-input" value={soil} onChange={(e) => setSoil(e.target.value)}>
              {SOIL_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <button type="submit" className="btn" disabled={nothingTyped}>
              Check this measurement
            </button>
            {nothingTyped && <p className="muted">Type at least one measured value.</p>}
          </form>

          {res.status === 'loading' && <p className="muted" role="status">Checking…</p>}
          {res.status === 'error' && <p className="notice" role="alert">{res.error.message}</p>}
          {res.status === 'ok' && (
            <div className="nw-siteeval-result">
              <p className="muted">{res.data.note}</p>
              <ol className="nw-plist">
                {res.data.ranking.slice(0, 10).map((r) => (
                  <li key={r.species_id} className="nw-prow nw-sp">
                    <div className="nw-prow-main">
                      <span className="rank-no">{r.rank}</span>
                      <span className="nw-prow-name">{r.common_name}</span>
                      <span className="muted">S {fmt(r.S)} · W {fmt(r.W)}</span>
                    </div>
                    {'grid_S' in r && (
                      <p className="muted">
                        Grid estimate for point {res.data.compared_to_point?.point_id}: S {fmt(r.grid_S)} ({r.delta_S >= 0 ? '+' : ''}{fmt(r.delta_S)} from your measurement)
                      </p>
                    )}
                    <FlagBadges flags={r.flags} />
                  </li>
                ))}
              </ol>
              {res.data.ranking.length === 0 && <p className="muted">No species is suitable for exactly what you measured.</p>}
            </div>
          )}
        </>
      )}
    </section>
  )
}
