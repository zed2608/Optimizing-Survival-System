import { useApi } from '../v2/useApi.js'
import Icon from './Icon.jsx'

const GLYPH = { good_to_plant: 'check', plant_with_care: 'warn', avoid_this_week: 'close', unknown: 'question' }

// In the plan result card: a short weather summary for this week at the middle of the planned trees, and a link to the Weather tab for the details.
export default function PlanWeather({ result, includeUnzoned, onOpenWeather }) {
  const lat = result.plan.reduce((a, x) => a + x.lat, 0) / result.plan.length
  const lon = result.plan.reduce((a, x) => a + x.lon, 0) / result.plan.length
  const api = useApi(`/weather/week?purpose=${result.purpose}&lat=${lat.toFixed(5)}&lon=${lon.toFixed(5)}&include_unzoned=${includeUnzoned}`)
  const d = api.status === 'ok' ? api.data : null
  return (
    <div className="nw-planweather">
      {api.status === 'loading' && <p className="nw-plain">Loading this week's weather…</p>}
      {api.status === 'error' && <p className="nw-plain">{api.error.network ? 'The planning service could not be reached, so there is no weather now.' : 'Weather is not available now.'}</p>}
      {d && (
        <p className="nw-plain" role="status">
          <strong>
            <Icon name={GLYPH[d.verdict.code] ?? 'question'} /> This week: {d.verdict.label}.
          </strong>{' '}
          {d.week.rain_total_mm === null ? 'Rain for the week: Data Unavailable.' : `${d.week.rain_total_mm} mm of rain in the next ${d.week.n_days} days.`}
          {d.cached ? ' (a saved forecast)' : ''}
        </p>
      )}
      <button type="button" className="btn" onClick={onOpenWeather}>
        Open weather tab
      </button>
    </div>
  )
}
