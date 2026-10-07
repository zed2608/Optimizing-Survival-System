import { useState } from 'react'
import Icon from './Icon.jsx'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import FlagBadges from '../v2/components/FlagBadges.jsx'
import ScoreChip from '../v2/components/ScoreChip.jsx'
import MatchChip from './MatchChip.jsx'
import { plainWarning } from './plainWords.js'
import { fmt, pct } from '../v2/scale.js'
import ColorLegend from '../v2/components/ColorLegend.jsx'
import HelpTip from './HelpTip.jsx'
import ViewSwitch from './ViewSwitch.jsx'
import { BEST_MONTHS_NOTE } from './season.js'
import SeasonBadge from './SeasonBadge.jsx'
import SeasonNotice from './SeasonNotice.jsx'
import SourceGroup from './SourceGroup.jsx'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MARKER = -1

// The API's 400/422 answers in plain words (with the API's own sentence kept below as the detail).
function friendly(error) {
  const m = error.message
  if (error.status === 400 && m.includes('no legal-zone grid points')) {
    return { title: 'Nothing to rank in this area', text: 'The area has no planting-zone grid points. Draw it over the coloured dots, or pick a barangay or zone from the lists.' }
  }
  if (error.status === 400 && m.includes('No species has eligible points')) {
    return { title: 'No suitable species in this area', text: 'No species can grow here for this purpose (S stays below 0.50 everywhere). Try another area or another purpose.' }
  }
  if (error.status === 422 && m.toLowerCase().includes('polygon')) {
    return { title: 'That shape cannot be used', text: 'The drawn area must have at least 3 corners and its edges must not cross each other. Press “Start again” and redraw it.' }
  }
  return null
}

function MissingOr({ v, f }) {
  return v === MARKER || v === null || v === undefined ? <span className="unavailable">Data Unavailable</span> : <>{f(v)}</>
}

// Mode 2: ranked species for a whole area, plus the suggested mix (shares from the palette code, with its caps).
export default function AreaResultPanel({ api, areaLabel, onShowAll, onChangeDates, onInfo, view = 'compact', onView = () => {} }) {
  const [show, setShow] = useState(5)
  const full = view === 'full'
  if (api.status === 'loading') return <div className="v2 v2-embedded"><div className="panel-body"><Loading what={`Ranking species for ${areaLabel}`} /></div></div>
  if (api.status === 'error') {
    const f = friendly(api.error)
    return (
      <div className="v2 v2-embedded">
        <div className="panel-body">
          {f ? (
            <div className="notice" role="status">
              <strong>{f.title}</strong>
              <p>{f.text}</p>
              <p className="muted">{api.error.message}</p>
            </div>
          ) : (
            <ErrorBox error={api.error} onRetry={api.retry} title="Could not rank the species for this area" brief />
          )}
        </div>
      </div>
    )
  }
  if (api.status !== 'ok') return null
  const r = api.data
  const mix = r.mix
  const sb = r.season
  return (
    <div className="v2 v2-embedded">
      <div className="panel-body">
        <ViewSwitch value={view} onChange={onView} />
        <h2 className="sr-only">Species for {r.area.display_name}</h2>
        <div className="nw-opt-head">
          <p className="nw-count-line nw-grow">
            {r.species_with_suitable_points} of {r.species_total} species suitable somewhere here
          </p>
          <HelpTip label="About this list">
            {r.area.legal_points} planting squares; {r.area.points_with_a_suitable_species} have at least one suitable species. Month strip: filled = planting months, ringed = your dates.
          </HelpTip>
        </div>
        {r.area.not_plantable_points > 0 && (
          <p className="notice" role="status">
            <Icon name="close" /> {r.area.not_plantable_points} point{r.area.not_plantable_points === 1 ? ' is' : 's are'} marked <strong>not plantable</strong> in the field and left out of this ranking.
          </p>
        )}
        {r.area.not_plantable_points === 0 && <p className="muted">No point of this area is marked not plantable in the field.</p>}

        {sb && r.ranking.length === 0 && sb.removed > 0 && (
          <SeasonNotice light kept={sb.kept} total={sb.species_total} start={sb.start} end={sb.end} onShowAll={onShowAll} onChangeDates={onChangeDates} />
        )}
        <section className="nw-mix" aria-label="Suggested mix">
          <h3>Suggested mix</h3>
          {mix.species.length === 0 ? (
            <p className="muted">No mix can be suggested for this area. {mix.warnings.map((w) => (full ? w : plainWarning(w))).join(' ')}</p>
          ) : (
            <>
              <ul className="nw-bars">
                {mix.species.map((s) => (
                  <li key={s.species_id}>
                    <span className="nw-bar-name">
                      <button type="button" className="nw-namebtn" onClick={() => onInfo(s.species_id)}>
                        {s.common_name}
                        <span className="sr-only"> (species information)</span>
                      </button>
                      {s.needs_both_sexes && <span className="nw-bar-flag"> · plant both sexes</span>}
                      {s.season && <SeasonBadge season={s.season} strip={false} className="nw-inline" />}
                    </span>
                    <span className="nw-bar" aria-hidden="true">
                      <span style={{ width: `${Math.round(s.share * 100)}%` }} />
                    </span>
                    <strong className="nw-bar-num">{pct(s.share)}</strong>
                  </li>
                ))}
              </ul>
              <p className="muted">
                For {mix.n_saplings} saplings. Every species is planted in {mix.common_planting_months.map((m) => MONTHS[m - 1]).join(', ') || 'no shared month'}. At most{' '}
                {pct(mix.caps.max_species_share)} of the trees per species and {pct(mix.caps.max_genus_share)} per genus (limits are provisional).
              </p>
              {mix.warnings.map((w) => (
                <p key={w} className="notice">{full ? w : plainWarning(w)}</p>
              ))}
            </>
          )}
        </section>

        <h3>Ranked species</h3>
        {full && (
          <div className="nw-fullnote">
            <div className="muted">Colours: green good, orange moderate, red poor, grey not suitable. {r.area.legal_points} planting squares; {r.area.points_with_a_suitable_species} have at least one suitable species.</div>
            <ColorLegend />
          </div>
        )}
        <ol className="nw-plist">
          {r.ranking.slice(0, show).map((s) => (
            <li key={`${s.species_id}|${full}`} className="nw-prow nw-sp">
              <div className="nw-prow-main">
                <span className="rank-no">{s.rank}</span>
                <button type="button" className="nw-namebtn nw-prow-name" onClick={() => onInfo(s.species_id)}>
                  {s.common_name}
                  <span className="sr-only"> (species information)</span>
                </button>
                {full ? <ScoreChip w={s.mean_W_where_suitable === MARKER ? null : s.mean_W_where_suitable} label="Average score W where suitable" /> : <MatchChip w={s.mean_W_where_suitable === MARKER ? null : s.mean_W_where_suitable} label="Average match where suitable" />}
                <SeasonBadge season={s.season} strip={false} best={false} />
              </div>
              <details className="nw-pdetails" open={full || undefined}>
                <summary>
                  Details<span className="sr-only"> for {s.common_name}</span>
                </summary>
                <dl className="scores">
                  <div>
                    <dt>Suitable on</dt>
                    <dd>
                      {pct(s.share_of_area_suitable)} <span className="muted">({s.suitable_points} points)</span>
                    </dd>
                  </div>
                  <div>
                    <dt>Average score (W) where suitable</dt>
                    <dd>
                      <MissingOr v={s.mean_W_where_suitable} f={fmt} />
                    </dd>
                  </div>
                  <div>
                    <dt>Purpose fitness (P)</dt>
                    <dd>
                      <MissingOr v={s.P} f={fmt} />
                    </dd>
                  </div>
                  <div>
                    <dt>Confidence</dt>
                    <dd>
                      site <MissingOr v={s.mean_site_confidence} f={pct} /> · purpose <MissingOr v={s.p_confidence} f={pct} />
                    </dd>
                  </div>
                </dl>
                <SeasonBadge season={s.season} />
                {full && s.season && <div className="muted">Month strip: filled = planting months, ringed = your dates. {BEST_MONTHS_NOTE}</div>}
                <FlagBadges flags={s.flags} />
                <details open={full || undefined}>
                  <summary>
                    Show sources<span className="sr-only"> for {s.common_name}</span>
                  </summary>
                  <SourceGroup title="Site suitability inputs" ids={s.source_ids.site_score} map={r.sources} />
                  <SourceGroup title="Purpose fitness inputs" ids={s.source_ids.purpose_score} map={r.sources} />
                </details>
              </details>
            </li>
          ))}
        </ol>
        {r.ranking.length > 5 && (
          <div className="nw-more-row" role="group" aria-label="How many species to show">
            <button type="button" className="btn btn-small" aria-pressed={show === 10} onClick={() => setShow((s) => (s === 10 ? 5 : 10))}>
              {show === 10 ? 'Show 5' : 'Show 10'}
            </button>
            {r.ranking.length > 10 && (
              <button type="button" className="btn btn-small" aria-pressed={show > 10} onClick={() => setShow((s) => (s > 10 ? 5 : 100))}>
                {show > 10 ? 'Show 5' : 'Show all'}
              </button>
            )}
          </div>
        )}
        <div className="nw-opt-head">
          <span className="muted nw-grow">How the score is worked out</span>
          <HelpTip label="How the score is worked out">{r.score_definition}</HelpTip>
        </div>
      </div>
    </div>
  )
}
