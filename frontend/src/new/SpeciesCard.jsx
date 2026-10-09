import { useEffect, useRef } from 'react'
import Icon from './Icon.jsx'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import FlagBadges from '../v2/components/FlagBadges.jsx'
import SourceLink from '../v2/components/SourceLink.jsx'
import { useApi } from '../v2/useApi.js'
import MonthStrip from './MonthStrip.jsx'
import AdviceSection from './AdviceSection.jsx'
import PartnersSection from './PartnersSection.jsx'
import ProvisionalTag from './ProvisionalTag.jsx'
import SeasonBadge from './SeasonBadge.jsx'
import WeatherCard from './WeatherCard.jsx'
import { BEST_MONTHS_NOTE, monthsText, parseMonths, seasonQuery } from './season.js'

const sourceOf = (f) => ({ url: f.source_url, rank: f.source_rank, rank_basis: f.rank_basis, off_list: f.off_list, flags: f.flags })
const present = (v) => v !== null && v !== undefined && String(v).trim() !== '' && String(v).toLowerCase() !== 'nan'
const cap = (t) => (present(t) ? String(t).charAt(0).toUpperCase() + String(t).slice(1) : null)

// One fact: its label, the value (exactly as written in the dataset where it is a source value), its sources with rank badges, and "Data Unavailable" for a gap.
// A value whose source is flagged (file not provided, off the project list, badly cited) is marked "draft".
function Fact({ label, rows = [], text, large = false, extra = null, note = '' }) {
  const found = rows.filter(Boolean)
  const shown = text !== undefined ? text : found.length ? found.map((r) => r.value_as_written).join(' · ') : null
  const sources = [...new Map(found.filter((r) => r.source_url).map((r) => [`${r.source_url}|${r.source_rank}`, r])).values()]
  const draft = found.some((r) => r.flags)
  return (
    <div className={`nw-fact ${large ? 'is-large' : ''}`}>
      <dt>{label}</dt>
      <dd>
        <span className="nw-fact-val">{present(shown) ? shown : <span className="unavailable">Data Unavailable</span>}</span>
        {draft && (
          <span className="nw-draft" title="The source of this value is flagged (file not provided, off the project list or badly cited) and it is not signed off.">
            draft
          </span>
        )}
        {extra}
        {note && <div className="muted">{note}</div>}
        {present(shown) &&
          (sources.length > 0 ? (
            <ul className="plain-list nw-fact-src">
              {sources.map((r) => (
                <li key={`${r.source_url}|${r.source_rank}`}>
                  <SourceLink source={sourceOf(r)} />
                </li>
              ))}
            </ul>
          ) : (
            <div className="muted nw-fact-src">
              Source: <span className="unavailable">Data Unavailable</span>
            </div>
          ))}
      </dd>
    </div>
  )
}

function Section({ title, big = false, children }) {
  return (
    <section className={`nw-card-sec ${big ? 'is-big' : ''}`} aria-label={title}>
      <h3>{title}</h3>
      <dl className="nw-facts">{children}</dl>
    </section>
  )
}

// The species card: a right-hand drawer with everything the dataset says about one species (GET /species/{id}), every value with its source and rank.
export default function SpeciesCard({ speciesId, window: win, onClose, onFindAreas, point = null, view = 'compact', pointId = null }) {
  const api = useApi(`/species/${speciesId}?${seasonQuery(win, false)}`)
  const advice = useApi(`/species/${speciesId}/advice?${seasonQuery(win, false)}${pointId ? `&point_id=${pointId}` : ''}`) // ways to improve survival: advice only, hidden when it cannot be loaded
  const closeRef = useRef(null)
  const closeFn = useRef(onClose)
  useEffect(() => {
    closeFn.current = onClose
  })
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e) => {
      if (e.key === 'Escape') closeFn.current()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [speciesId])

  const d = api.status === 'ok' ? api.data : null
  const F = d ? Object.fromEntries(d.fields.map((f) => [f.field_name, f])) : {}
  const cv = d?.clean_values ?? {}
  const range = (a, b, unit) => {
    const x = F[a]?.value_as_written
    const y = F[b]?.value_as_written
    const u = unit ? ` ${unit}` : ''
    if (present(x) && present(y)) return `${x} to ${y}${u}`
    if (present(x)) return `${x}${u} (upper end: Data Unavailable)`
    if (present(y)) return `up to ${y}${u} (lower end: Data Unavailable)`
    return null
  }
  const one = (name, unit = '') => (present(F[name]?.value_as_written) ? `${F[name].value_as_written}${unit ? ` ${unit}` : ''}` : null)
  const months = parseMonths(cv.planting_months)
  const dioecious = cv.is_dioecious === true || String(cv.is_dioecious).toLowerCase() === 'true'

  let endangered = null
  if (d) {
    const parts = []
    if (present(cv.endangered_denr)) parts.push(`${cv.endangered_denr} (DENR)`)
    if (present(cv.endangered_iucn)) parts.push(`${cv.endangered_iucn} (IUCN)`)
    if (parts.length) endangered = parts.join(', ')
    else if (present(cv.endangered_unspecified)) endangered = `${cv.endangered_unspecified} (scheme not stated)`
    else if (present(F.endangered_raw?.value_as_written)) endangered = `${F.endangered_raw.value_as_written} (scheme not stated)`
  }

  return (
    <aside className="nw-card v2 v2-embedded" role="dialog" aria-label={d ? `About ${d.common_name}` : 'Species information'}>
      <div className="nw-card-head">
        <div>
          <h2>{d ? d.common_name : 'Species information'}</h2>
          {d && <div className="nw-card-sci">{d.scientific_name}</div>}
        </div>
        <button type="button" className="btn btn-small" onClick={onClose} ref={closeRef}>
          <Icon name="close" /> Close<span className="sr-only"> (Escape)</span>
        </button>
      </div>
      <div className="nw-card-body">
        <p className="nw-card-note">Data comes from the sources linked below; values marked draft are not yet signed off by the agriculturist.</p>
        {api.status === 'loading' && <Loading what="Loading the species information" />}
        {api.status === 'error' && <ErrorBox error={api.error} onRetry={api.retry} title="Could not load the species information" brief />}
        {d && (
          <>
            <Section title="Header">
              <Fact label="Common name" rows={[F.common_name]} />
              <Fact label="Scientific name" rows={[F.scientific_name]} />
              <Fact label="Category" rows={[F.category]} />
              <Fact label="Endangered status" rows={[F.endangered_raw]} text={endangered} />
              <Fact
                label="High-value crop"
                text={cv.is_high_value_crop === true || String(cv.is_high_value_crop).toLowerCase() === 'true' ? 'Yes' : cv.is_high_value_crop === null || cv.is_high_value_crop === undefined ? null : 'No'}
                note="A team decision, not a sourced fact."
              />
              <FlagBadges flags={d.flags} />
              <div className="nw-card-tags" aria-label="Purpose tags and nursery">
                {(d.purpose_tags ?? []).length > 0 && (
                  <div className="nw-tagrow">
                    <span className="nw-tagrow-label">Purpose</span>
                    {d.purpose_tags.map((t) => (
                      <span key={t} className="nw-chip nw-chip-tag">
                        {t}
                      </span>
                    ))}
                    <ProvisionalTag title="Purpose tags are filters from rules over the type text; to be confirmed by the agriculturist" />
                  </div>
                )}
                {d.in_nursery === true && (
                  <div className="nw-tagrow">
                    <span className="nw-chip nw-chip-nursery">
                      <Icon name="check" size={12} /> Available in LGU nursery
                    </span>
                    <span className="muted">Stock quantities unknown</span>
                  </div>
                )}
                {d.in_nursery === false && d.nursery_note && (
                  <div className="nw-tagrow">
                    <span className="muted">{d.nursery_note}. Stock quantities unknown</span>
                  </div>
                )}
              </div>
            </Section>

            <Section title="Planting stage and timing" big>
              <Fact label="Deployment stage" rows={[F.deployment_stage]} large />
              <Fact
                label="Planting months"
                rows={[F.months_raw]}
                text={months ? monthsText(months) : null}
                large
                extra={
                  <div className="nw-card-season">
                    <MonthStrip filled={months ?? []} ring={d.season?.window_months ?? null} size="large" />
                    <SeasonBadge season={d.season} strip={false} />
                  </div>
                }
                note={BEST_MONTHS_NOTE}
              />
              <Fact label="Germination time" rows={[F.germination_raw]} large />
              <Fact label="Propagation method" rows={[F.propagation_method]} large />
              <Fact label="Planting depth" rows={[F.planting_depth]} large />
              <Fact label="Planting method" rows={[F.planting_method]} large />
              <Fact label="Spacing" rows={[F.spacing_min_m, F.spacing_max_m]} text={range('spacing_min_m', 'spacing_max_m', 'm')} large />
            </Section>

            <Section title="Where it grows">
              <Fact label="Elevation" rows={[F.elev_min_m, F.elev_max_m]} text={range('elev_min_m', 'elev_max_m', 'm')} />
              <Fact label="Rainfall" rows={[F.rain_min_mm, F.rain_max_mm]} text={range('rain_min_mm', 'rain_max_mm', 'mm')} />
              <Fact label="Temperature" rows={[F.temp_min_c, F.temp_max_c]} text={range('temp_min_c', 'temp_max_c', '°C')} />
              <Fact label="Steepest slope" rows={[F.max_slope_pct]} text={one('max_slope_pct', '%')} />
              <Fact label="Soil types" rows={[F.soil_raw]} />
              <Fact label="Soil pH" rows={[F.ph_min, F.ph_max]} text={range('ph_min', 'ph_max', '')} />
              <Fact label="Shade tolerance" rows={[F.shade_tol]} />
              <Fact label="Drought tolerance" rows={[F.drought_tol]} />
              <Fact label="Waterlogging tolerance" rows={[F.waterlog_tol]} />
              <Fact label="Typhoon resistance" rows={[F.typhoon_res]} />
              <Fact label="Preferred climate" rows={[F.preferred_climate_seasons]} />
              <Fact label="Dry-season tolerance" rows={[F.dry_season_raw]} />
            </Section>

            <Section title="The tree">
              <Fact label="Mature height" rows={[F.mature_height_m]} text={one('mature_height_m', 'm')} />
              <Fact label="Canopy spread" rows={[F.canopy_spread_m]} text={one('canopy_spread_m', 'm')} />
              <Fact label="Root type" rows={[F.root_type]} />
              <Fact label="Growth rate" rows={[F.growth_rate_raw]} />
              <Fact label="Growth form" rows={[F.growth_form]} />
              <Fact label="Foliage" rows={[F.growth_form]} text={cap(cv.foliage)} note="Read from the growth form." />
              <Fact label="Timber density" rows={[F.timber_density_raw]} />
              <Fact label="Nitrogen fixing" rows={[F.mode_of_nutrition]} />
            </Section>

            <Section title="Uses and care">
              <Fact label="Common uses" rows={[F.common_uses]} />
              <Fact label="Special care" rows={[F.special_care_notes]} />
              <Fact label="Common problems" rows={[F.common_problems]} />
              <Fact label="Plant partners" rows={[F.plant_partners]} />
              <Fact label="Variants" rows={[F.variants]} />
              {dioecious && (
                <Fact label="Both sexes needed" rows={[F.sexuality_raw]} text="This species has separate male and female trees. Plant both sexes near each other." />
              )}
            </Section>

            {(d.interview_notes ?? []).length > 0 && (
              <section className="nw-card-sec" aria-label="From the agriculturist (provisional)">
                <h3>
                  From the agriculturist <span className="nw-prov">(provisional)</span>
                </h3>
                <ul className="nw-notes">
                  {d.interview_notes.map((n) => (
                    <li key={n.note}>
                      {n.note}
                      <div className="muted">{n.source}</div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {advice.status === 'ok' && <AdviceSection key={view} items={advice.data.advice} note={advice.data.note} view={view} limit={advice.data.limit_simple_species} />}
            <PartnersSection speciesId={speciesId} query={seasonQuery(win, false)} />

            {point && (
              <section className="nw-card-sec" aria-label="Weather advice for this species">
                <h3>Weather advice</h3>
                <WeatherCard url={`/advisory/seasonal?species_id=${speciesId}&lat=${point.lat.toFixed(5)}&lon=${point.lon.toFixed(5)}`} title={`Weather advice for ${point.label}`} win={win} />
              </section>
            )}
          </>
        )}
      </div>
      <div className="nw-card-foot">
        <button type="button" className="btn btn-primary" onClick={() => onFindAreas(speciesId)} disabled={!d}>
          Find areas for this species
        </button>
        <button type="button" className="btn btn-small" onClick={onClose}>
          Close
        </button>
      </div>
    </aside>
  )
}
