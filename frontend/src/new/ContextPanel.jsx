import { useApi } from '../v2/useApi.js'
import LocationCard from './LocationCard.jsx'
import ViableSuggestion from './ViableSuggestion.jsx'

// A click on a grey square (a grid square that is not a planting zone): where it is, why it is not scored, and the nearest suitable spot. No field-check buttons.
export default function ContextPanel({ data, index, win, today, searched, viable, onFindViable, onGo, onIncludeUnzoned = null }) {
  const c = data.columns
  const pid = c.point_id[index]
  const zone = c.zone[index] >= 0 ? data.zones[c.zone[index]] : ''
  const barangay = c.barangay[index] >= 0 ? data.barangays_display[c.barangay[index]] : ''
  const reason = data.reason_labels[data.reasons[c.reason[index]]]
  const info = useApi(`/search/point?q=${pid}`)
  const d = info.status === 'ok' ? info.data : null
  return (
    <div className="nw-ppanel">
      <LocationCard barangay={barangay} zone={zone} pointId={pid} lat={c.lat[index]} lon={c.lon[index]} elev={d?.elev_m} slope={d?.slope_pct} win={win} today={today} searched={searched} />
      <section className="nw-pcard" aria-label="Why there is no score">
        <h3>Not a planting zone</h3>
        <p className="nw-plain">{reason}.</p>
        {data.reasons[c.reason[index]] === 'outside_zoning' && (
          <>
            <p className="nw-plain">This land is not covered by the zoning map. It is left out while “Include land outside the zoning map” is off.</p>
            {onIncludeUnzoned && (
              <button type="button" className="btn btn-small" onClick={onIncludeUnzoned}>
                Include land outside the zoning map
              </button>
            )}
          </>
        )}
        {data.reasons[c.reason[index]] !== 'outside_zoning' && zone && <p className="nw-plain">Ask the LGU whether this zone can be planted.</p>}
        <span className="nw-chip">Not scored</span>
      </section>
      <section className="nw-pcard" aria-label="Nearest suitable spot">
        <button type="button" className="btn" onClick={onFindViable} disabled={viable.status === 'loading'}>
          Find the nearest suitable spot
        </button>
        <ViableSuggestion status={viable} onGo={onGo} />
      </section>
    </div>
  )
}
