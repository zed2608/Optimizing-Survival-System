import { useState } from 'react'
import Icon from './Icon.jsx'
import { useApi } from '../v2/useApi.js'
import { formatDay, windowForecastMessage } from './season.js'

const GROUPS = [
  { code: 'not_in_planting_window', icon: 'clock', label: 'Not in planting window' },
  { code: 'dry_spell', icon: 'sun', label: 'Dry spell' },
  { code: 'heavy_rain', icon: 'rain', label: 'Heavy rain' },
  { code: 'enso_manual', icon: 'wave', label: 'El Nino watch' },
]

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const mm = (v) => (v === null || v === undefined ? null : `${v} mm`)
const orNA = (v) => (v === null || v === undefined || v === '' ? <span className="unavailable">Data Unavailable</span> : v)

// The numbers behind one warning, in words.
function numbersText(w) {
  const n = w.numbers ?? {}
  if (w.code === 'dry_spell') return `${n.forecast_rain_mm} mm of rain in ${n.days} days (threshold ${n.threshold_mm} mm), drought tolerance ${String(n.drought_tol).toLowerCase()}`
  if (w.code === 'heavy_rain') return `up to ${n.max_daily_rain_mm} mm on ${formatDay(n.date)} (threshold ${n.threshold_mm} mm in one day)`
  if (w.code === 'not_in_planting_window') {
    const pm = (n.planting_months ?? []).map((m) => MONTHS[m - 1]).join(', ')
    return n.window_months ? `planting months ${pm}; your dates cover ${n.window_months.map((m) => MONTHS[m - 1]).join(', ')}` : `planting months ${pm}; this month is ${MONTHS[(n.current_month ?? 1) - 1]}`
  }
  if (w.code === 'enso_manual') return `El Nino setting: ${n.enso_status}`
  return ''
}

// Group the warnings of all species by kind; one sentence is shown once with the species it applies to.
function group(speciesList) {
  return GROUPS.map((g) => {
    const byMsg = new Map()
    speciesList.forEach((s) => (s.warnings ?? []).filter((w) => w.code === g.code).forEach((w) => {
      const e = byMsg.get(w.message) ?? { message: w.message, nums: numbersText(w), species: [] }
      e.species.push({ code: s.code, name: s.common_name })
      byMsg.set(w.message, e)
    }))
    return { ...g, items: [...byMsg.values()] }
  })
}

// One shape for the two services: GET /plans/{id}/advisory (every species of a plan) and GET /advisory/seasonal (one species at one point).
function normalise(d, win) {
  if (d.species && Array.isArray(d.species) && d.forecast && 'first_day' in d.forecast) {
    const f = d.forecast
    return {
      windowMessage: d.window_message, covered: d.window_covered_by_forecast, forecastRange: f.first_day && f.last_day ? `${formatDay(f.first_day)} - ${formatDay(f.last_day, true)}` : null,
      rain7: f.rain_next_days_mm, rainDays: f.rain_next_days, maxRain: f.max_daily_rain_mm, maxRainDate: f.max_daily_rain_date, tmax: f.tmax_c_max, tmin: f.tmin_c_min,
      groups: group(d.species), nSpecies: d.species.length, nWarnings: d.n_warnings, enso: d.enso, missingNote: f.missing_note,
    }
  }
  const rows = d.forecast ?? []
  const first = rows[0]?.date
  const last = rows[rows.length - 1]?.date
  const known = rows.filter((r) => r.rain_mm !== null && r.rain_mm !== undefined)
  const wet = known.reduce((a, r) => (a === null || r.rain_mm > a.rain_mm ? r : a), null)
  const wm = win && first ? windowForecastMessage(win.start, win.end, first, last) : null
  const sp = [{ code: null, common_name: d.species?.common_name, warnings: d.warnings }]
  return {
    windowMessage: wm?.message ?? null, covered: wm?.covered ?? null, forecastRange: first ? `${formatDay(first)} - ${formatDay(last, true)}` : null,
    rain7: d.summary?.rain_next_window_mm, rainDays: d.summary?.rain_window_days, maxRain: d.summary?.max_daily_rain_mm, maxRainDate: wet?.date, tmax: d.summary?.tmax_c_max, tmin: d.summary?.tmin_c_min,
    groups: group(sp), nSpecies: 1, nWarnings: (d.warnings ?? []).length, enso: { ...d.enso, is_default: d.enso?.status === 'none' && String(d.enso?.source ?? '').startsWith('not set') },
    missingNote: (d.not_assessed ?? []).length ? 'Some forecast values are missing: the warnings that need them were not checked.' : '',
  }
}

function cacheLine(d) {
  if (!d.cached) return null
  const age = d.cache_age_minutes >= 120 ? `${Math.round(d.cache_age_minutes / 60)} hours` : `${Math.round(d.cache_age_minutes)} minutes`
  return d.network_error ? `The weather service could not be reached, so this is a saved forecast, ${age} old.` : `This is a saved forecast, ${age} old.`
}

// The "Weather advice" card: collapsed it is one line; opening it asks the service for the forecast (once).
export default function WeatherCard({ url, title = 'Weather advice', win = null }) {
  const [open, setOpen] = useState(false)
  const [asked, setAsked] = useState(false)
  const api = useApi(asked ? url : null)
  const d = api.status === 'ok' ? normalise(api.data, win) : null
  const toggle = () => {
    setOpen((o) => !o)
    setAsked(true)
  }
  const summary = d ? `${d.rain7 !== null && d.rain7 !== undefined ? `Rain next ${d.rainDays} days ${d.rain7} mm` : 'Rain: Data Unavailable'} · ${d.nWarnings} warning${d.nWarnings === 1 ? '' : 's'}` : 'tap to load'
  return (
    <section className="nw-weather" aria-label={title}>
      <button type="button" className="nw-weather-toggle" aria-expanded={open} onClick={toggle}>
        <Icon name="cloud" /> <strong>{title}</strong> <span className="muted">{summary}</span> <Icon name={open ? 'down' : 'right'} size={14} />
      </button>
      {open && (
        <div className="nw-weather-body">
          {api.status === 'loading' && <p className="nw-plain">Loading the forecast…</p>}
          {api.status === 'error' && (
            <p className="fc-bad" role="alert">
              {api.error.network ? 'The planning service could not be reached, so there is no weather advice now.' : `Weather advice is not available now. ${api.error.message}`}
            </p>
          )}
          {d && (
            <>
              {d.windowMessage && (
                <p className={`notice nw-window-msg ${d.covered === false ? 'is-beyond' : ''}`} role="status">
                  {d.windowMessage}
                </p>
              )}
              {cacheLine(api.data) && <p className="muted nw-cache-line">{cacheLine(api.data)}</p>}
              <dl className="nw-wnums" aria-label="Forecast numbers">
                <div>
                  <dt>Rain, next {d.rainDays ?? 7} days</dt>
                  <dd>{orNA(mm(d.rain7))}</dd>
                </div>
                <div>
                  <dt>Highest daily rain</dt>
                  <dd>{d.maxRain === null || d.maxRain === undefined ? orNA(null) : `${d.maxRain} mm${d.maxRainDate ? ` on ${formatDay(d.maxRainDate)}` : ''}`}</dd>
                </div>
                <div>
                  <dt>Temperature</dt>
                  <dd>{d.tmin === null || d.tmin === undefined || d.tmax === null || d.tmax === undefined ? orNA(null) : `${Math.round(d.tmin)} to ${Math.round(d.tmax)} °C`}</dd>
                </div>
                <div>
                  <dt>Forecast dates</dt>
                  <dd>{orNA(d.forecastRange)}</dd>
                </div>
              </dl>
              {d.missingNote && <p className="muted">{d.missingNote}</p>}
              {d.nWarnings === 0 ? (
                <p className="nw-plain nw-nowarn">No warnings for {d.nSpecies === 1 ? 'this species' : 'the species of this plan'} in this forecast.</p>
              ) : (
                d.groups
                  .filter((g) => g.items.length)
                  .map((g) => (
                    <div key={g.code} className="nw-wgroup">
                      <h4>
                        <Icon name={g.icon} /> {g.label}
                      </h4>
                      <ul>
                        {g.items.map((it) => (
                          <li key={it.message}>
                            {it.message}
                            <div className="muted">{it.nums}</div>
                            {it.species.some((s) => s.code) && <div className="nw-wsp">Species: {it.species.map((s) => `${s.code} ${s.name}`).join(', ')}</div>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))
              )}
              <p className="muted">
                {d.enso?.is_default ? 'El Nino status is set by hand: none (source not set)' : `El Nino status is set by hand: ${d.enso?.status} (${d.enso?.source})`}
              </p>
              <p className="muted">Forecast: Open-Meteo. This is a planning aid, not a guarantee.</p>
            </>
          )}
        </div>
      )}
    </section>
  )
}
