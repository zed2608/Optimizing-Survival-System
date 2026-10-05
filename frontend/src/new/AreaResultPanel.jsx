import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import FlagBadges from '../v2/components/FlagBadges.jsx'
import ScoreChip from '../v2/components/ScoreChip.jsx'
import { fmt, pct } from '../v2/scale.js'
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
export default function AreaResultPanel({ api, areaLabel }) {
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
  return (
    <div className="v2 v2-embedded">
      <div className="panel-body">
        <h2>Species for {r.area.display_name}</h2>
        <p className="muted">
          {r.area.legal_points} planting-zone grid points; {r.area.points_with_a_suitable_species} have at least one suitable species. {r.species_with_suitable_points} of{' '}
          {r.species_total} species are suitable somewhere here. Showing the top {r.returned}.
        </p>
        {r.area.not_plantable_points > 0 && (
          <p className="notice" role="status">
            ✕ {r.area.not_plantable_points} point{r.area.not_plantable_points === 1 ? ' is' : 's are'} marked <strong>not plantable</strong> in the field and left out of this ranking.
          </p>
        )}
        {r.area.not_plantable_points === 0 && <p className="muted">No point of this area is marked not plantable in the field.</p>}

        <section className="nw-mix" aria-label="Suggested mix">
          <h3>Suggested mix</h3>
          {mix.species.length === 0 ? (
            <p className="muted">No mix can be suggested for this area. {mix.warnings.join(' ')}</p>
          ) : (
            <>
              <ul className="nw-bars">
                {mix.species.map((s) => (
                  <li key={s.species_id}>
                    <span className="nw-bar-name">
                      {s.common_name}
                      {s.needs_both_sexes && <span className="nw-bar-flag"> · plant both sexes</span>}
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
                <p key={w} className="notice">{w}</p>
              ))}
            </>
          )}
        </section>

        <h3>Ranked species</h3>
        <ol className="nw-spp">
          {r.ranking.map((s) => (
            <li key={s.species_id} className="nw-sp">
              <div className="nw-sp-head">
                <span className="rank-no">{s.rank}</span>
                <strong>{s.common_name}</strong>
                <ScoreChip w={s.mean_W_where_suitable === MARKER ? null : s.mean_W_where_suitable} label="Average score W where suitable" />
              </div>
              <dl className="scores">
                <div>
                  <dt>Suitable on</dt>
                  <dd>
                    {pct(s.share_of_area_suitable)} <span className="muted">({s.suitable_points} points)</span>
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
              <FlagBadges flags={s.flags} />
              <details>
                <summary>
                  Show sources<span className="sr-only"> for {s.common_name}</span>
                </summary>
                <SourceGroup title="Site suitability inputs" ids={s.source_ids.site_score} map={r.sources} />
                <SourceGroup title="Purpose fitness inputs" ids={s.source_ids.purpose_score} map={r.sources} />
              </details>
            </li>
          ))}
        </ol>
        <p className="muted">{r.score_definition}</p>
      </div>
    </div>
  )
}
