import { useMemo } from 'react'
import Icon from './Icon.jsx'
import { useApi } from '../v2/useApi.js'
import { PURPOSE_SHORT } from './labelsNew.js'
import FlagList from './FlagList.jsx'
import SeasonBadge from './SeasonBadge.jsx'
import SourceGroup from './SourceGroup.jsx'
import ViewSwitch from './ViewSwitch.jsx'
import { formatDay } from './season.js'

const VERDICT = {
  good_to_plant: { glyph: 'check', cls: 'good' },
  plant_with_care: { glyph: 'warn', cls: 'care' },
  avoid_this_week: { glyph: 'close', cls: 'avoid' },
  unknown: { glyph: 'question', cls: 'unknown' },
}
const WARN = { heavy_rain: { icon: 'rain', label: 'Heavy rain' }, dry_spell: { icon: 'sun', label: 'Dry spell' }, enso_manual: { icon: 'wave', label: 'El Nino watch' } }

// A day in words, from the rain only: dry under 1 mm, light rain 1 to 10 mm, rainy 10 mm or more, heavy rain above the heavy-rain threshold of the service. A missing value is "No forecast", never a guess.
function dayWord(mm, heavy) {
  if (mm === null || mm === undefined) return { icon: 'question', word: 'No forecast' }
  if (mm > heavy) return { icon: 'rain', word: 'Heavy rain' }
  if (mm >= 10) return { icon: 'cloud', word: 'Rainy' }
  if (mm >= 1) return { icon: 'cloud', word: 'Light rain' }
  return { icon: 'sun', word: 'Dry' }
}
const weekday = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { weekday: 'short' })
const num = (v, unit) => (v === null || v === undefined ? <span className="unavailable">Data Unavailable</span> : `${v}${unit}`)

function ageText(min) {
  return min >= 120 ? `${Math.round(min / 60)} hours` : `${Math.round(min)} minutes`
}

function SpeciesRow({ item, pos, full, sources, onInfo }) {
  return (
    <li className="nw-wrow">
      <div className="nw-wrow-main">
        <span className="rank-no" aria-label={`Number ${pos}`} title={`Rank ${item.rank} in the municipality for this purpose`}>
          {pos}
        </span>
        <button type="button" className="nw-namebtn nw-prow-name" onClick={() => onInfo(item.species_id)}>
          {item.common_name}
          <span className="sr-only"> (species information)</span>
        </button>
        <span className="chip" title="Species score for this purpose (rank in the municipality)">
          <strong>{item.species_score.toFixed(2)}</strong>
          <span className="chip-word">Species score</span>
        </span>
      </div>
      <div className="nw-wrow-reason">{item.reason}</div>
      {item.warnings.length > 0 && (
        <ul className="nw-warnlist">
          {item.warnings.map((w) => (
            <li key={w.code}>
              <Icon name={WARN[w.code]?.icon ?? 'flag'} /> <strong>{WARN[w.code]?.label ?? w.code}:</strong> {w.message}
            </li>
          ))}
        </ul>
      )}
      {full && (
        <div className="nw-wrow-full">
          <SeasonBadge season={item.season} />
          <div className="muted">
            Drought tolerance: {item.drought_tol ?? <span className="unavailable">Data Unavailable</span>} · Planting months: {item.planting_months_names.join(', ')}
          </div>
          <FlagList flags={item.flags} />
          <SourceGroup title="Sources (planting months, drought tolerance)" ids={Object.values(item.source_ids)} map={sources} />
        </div>
      )}
    </li>
  )
}

function SpeciesList({ title, help, block, full, sources, onInfo, id }) {
  return (
    <section className="v2 v2-embedded nw-wcard" aria-label={title} id={id}>
      <h3>
        {title} <span className="muted">({block.count})</span>
      </h3>
      {help && <p className="nw-plain">{help}</p>}
      {block.count === 0 ? (
        <p className="nw-plain nw-wempty" role="status">
          {block.empty_reason?.message ?? 'None this week.'}
        </p>
      ) : (
        <ol className="nw-wlist">
          {block.items.map((it, k) => (
            <SpeciesRow key={it.species_id} item={it} pos={k + 1} full={full} sources={sources} onInfo={onInfo} />
          ))}
        </ol>
      )}
    </section>
  )
}

// The "Weather" tab: the next 7 days at one place, one plain verdict for planting that week, and the species to plant (or to hold back) for the chosen purpose.
// One column, big headings. Compact | Full details like the other panels.
//   loc: 'centre' | 'point' | 'plan' | 'b:<barangay name>'; planLoc / spot: {lat, lon, label} for the last two.
export default function WeatherTab({ purpose, onPurpose, view, onView, loc, onLoc, barangays, spot, planLoc, onInfo, includeUnzoned }) {
  const full = view === 'full'
  const place = useMemo(() => {
    if (loc === 'point' && spot) return { lat: spot.lat, lon: spot.lon, label: 'the last point you clicked' }
    if (loc === 'plan' && planLoc) return planLoc
    if (loc.startsWith('b:')) {
      const f = barangays.find((b) => b.properties.name === loc.slice(2))
      if (f) return { lat: f.properties.label_point.lat, lon: f.properties.label_point.lon, label: f.properties.display_name }
    }
    return null // the centre of San Mateo: the service uses it when no coordinates are sent
  }, [loc, spot, planLoc, barangays])
  const url = `/weather/week?purpose=${purpose}${place ? `&lat=${place.lat.toFixed(5)}&lon=${place.lon.toFixed(5)}` : ''}&include_unzoned=${includeUnzoned}`
  const api = useApi(url)
  const d = api.status === 'ok' ? api.data : null
  const v = d ? (VERDICT[d.verdict.code] ?? VERDICT.unknown) : null
  const heavy = d?.thresholds.heavy_rain_mm ?? 80

  return (
    <div className="nw-wtab">
      <div className="nw-wbar">
        <div className="nw-wfield">
          <label className="nw-wlabel" htmlFor="nw-wloc">
            Where
          </label>
          <select id="nw-wloc" className="fc-input" value={loc} onChange={(e) => onLoc(e.target.value)}>
            <option value="centre">San Mateo centre</option>
            {spot && <option value="point">The last point I clicked</option>}
            {planLoc && <option value="plan">{planLoc.label}</option>}
            <optgroup label="Barangay">
              {barangays.map((b) => (
                <option key={b.properties.name} value={`b:${b.properties.name}`}>
                  {b.properties.display_name}
                </option>
              ))}
            </optgroup>
          </select>
        </div>
        <div className="nw-wfield">
          <span className="nw-wlabel" id="nw-wpurpose">
            Purpose
          </span>
          <div className="nw-seg" role="radiogroup" aria-labelledby="nw-wpurpose">
            {Object.keys(PURPOSE_SHORT).map((p) => (
              <button key={p} type="button" role="radio" aria-checked={purpose === p} className={`nw-segbtn ${purpose === p ? 'is-active' : ''}`} onClick={() => onPurpose(p)}>
                {PURPOSE_SHORT[p]}
              </button>
            ))}
          </div>
        </div>
        <ViewSwitch value={view} onChange={onView} />
      </div>

      {api.status === 'loading' && (
        <p className="nw-plain nw-wlight" role="status">
          Loading the forecast…
        </p>
      )}
      {api.status === 'error' && (
        <section className="v2 v2-embedded nw-wcard" role="alert">
          <h3>Weather is not available now</h3>
          <p className="nw-plain">{api.error.network ? 'The planning service could not be reached, so there is no forecast now.' : api.error.message}</p>
          <button type="button" className="btn" onClick={api.retry}>
            Try again
          </button>
        </section>
      )}

      {d && (
        <>
          {d.cached && (
            <p className="notice nw-wnotice" role="status">
              {d.network_error ? 'The weather service could not be reached, so this is a saved forecast, ' : 'This is a saved forecast, '}
              {ageText(d.cache_age_minutes)} old.
            </p>
          )}
          <h2 className="nw-wtitle">
            The next {d.week.n_days} days · {place ? place.label : d.location.note}
          </h2>
          {d.week.short_note && <p className="notice">{d.week.short_note}</p>}
          <ol className="nw-days" aria-label="Daily forecast">
            {d.week.days.map((x) => {
              const w = dayWord(x.rain_mm, heavy)
              return (
                <li key={x.date} className="nw-day">
                  <div className="nw-day-date">
                    {weekday(x.date)} {formatDay(x.date)}
                  </div>
                  <div className="nw-day-word">
                    <Icon name={w.icon} /> {w.word}
                  </div>
                  <div>Rain {num(x.rain_mm, ' mm')}</div>
                  <div>
                    {x.tmax_c === null || x.tmin_c === null ? <span className="unavailable">Temperature: Data Unavailable</span> : `${Math.round(x.tmin_c)}–${Math.round(x.tmax_c)} °C`}
                  </div>
                </li>
              )
            })}
          </ol>
          {d.week.missing_note && <p className="muted nw-wlight">{d.week.missing_note}</p>}

          <section className={`v2 v2-embedded nw-wcard nw-verdict nw-verdict-${v.cls}`} aria-label="Week verdict">
            <h3 className="nw-verdict-title">
              <Icon name={v.glyph} size={22} /> {d.verdict.label}
            </h3>
            <ul className="nw-warnlist">
              {d.verdict.reasons.map((r) => (
                <li key={r.code}>{r.message}</li>
              ))}
            </ul>
            <dl className="nw-wnums" aria-label="The week in numbers">
              <div>
                <dt>Rain, 7 days</dt>
                <dd>{num(d.week.rain_total_mm, ' mm')}</dd>
              </div>
              <div>
                <dt>Wettest day</dt>
                <dd>{d.week.wettest_day ? `${d.week.wettest_day.rain_mm} mm on ${formatDay(d.week.wettest_day.date)}` : <span className="unavailable">Data Unavailable</span>}</dd>
              </div>
              <div>
                <dt>Hottest day</dt>
                <dd>{d.week.hottest_day ? `${d.week.hottest_day.tmax_c} °C on ${formatDay(d.week.hottest_day.date)}` : <span className="unavailable">Data Unavailable</span>}</dd>
              </div>
              <div>
                <dt>Thresholds</dt>
                <dd>
                  dry spell under {d.thresholds.dry_spell_mm} mm in {d.thresholds.dry_spell_days} days · heavy rain over {d.thresholds.heavy_rain_mm} mm in a day
                </dd>
              </div>
            </dl>
          </section>

          <SpeciesList id="nw-w-best" title="In their best months this week" block={d.species.best_months} full={full} sources={d.sources} onInfo={onInfo} />
          <SpeciesList
            id="nw-w-water"
            title="Only if you can water"
            help="Outside their best months, but with High drought tolerance."
            block={d.species.only_if_you_can_water}
            full={full}
            sources={d.sources}
            onInfo={onInfo}
          />
          {d.species.held_back.length > 0 && (
            <section className="v2 v2-embedded nw-wcard" aria-label="Held back by the weather" id="nw-w-held">
              <details>
                <summary>
                  <strong>Held back by the weather</strong> <span className="muted">({d.species.held_back.length})</span>
                </summary>
                <p className="nw-plain">These species would fit this week, but a weather warning applies.</p>
                <ol className="nw-wlist">
                  {d.species.held_back.map((it, k) => (
                    <SpeciesRow key={it.species_id} item={it} pos={k + 1} full={full} sources={d.sources} onInfo={onInfo} />
                  ))}
                </ol>
              </details>
            </section>
          )}

          <div className="nw-wfoot">
            <p className="muted">Forecast: Open-Meteo ({d.forecast_source.url}). This is a planning aid, not a guarantee.</p>
            <p className="muted">{d.enso.is_default ? 'El Nino status is set by hand: none (source not set)' : `El Nino status is set by hand: ${d.enso.status} (${d.enso.source})`}</p>
            <p className="muted">
              Species are ranked by their municipal score for {PURPOSE_SHORT[purpose].toLowerCase()}. {d.species.n_species_total} species in all; {d.species.species_with_planting_months} have planting months recorded.
            </p>
          </div>
        </>
      )}
    </div>
  )
}
