import { useState } from 'react'
import Icon from './Icon.jsx'
import { Loading } from '../v2/components/Status.jsx'
import ScoreChip from '../v2/components/ScoreChip.jsx'
import { TERM_LABEL, humanize } from '../v2/labels.js'
import { fmt, pct, wLevel } from '../v2/scale.js'
import MatchChip from './MatchChip.jsx'
import { matchText } from './plainWords.js'
import RowDetails from './RowDetails.jsx'
import SeasonBadge from './SeasonBadge.jsx'

const MAX_ROWS = 8

// Why a chosen species does or does not suit this spot, in plain words.
function verdict(item, full) {
  if (item.eligible) return { ok: true, text: full ? `Suitable here: site suitability S ${fmt(item.S)} is at least 0.50.` : 'Suitable here.' }
  const gates = item.site_breakdown?.gate_failed ?? []
  const why = gates.length ? ` It exceeds the species' limit for ${gates.map((g) => (TERM_LABEL[g] ?? humanize(g)).toLowerCase()).join(', ')}.` : ''
  return { ok: false, text: full ? `Not suitable here: site suitability S ${fmt(item.S)} is below 0.50.${why}` : `Not suitable here: the site fit is below 50%.${why}` }
}

// The card "Your chosen species here" (goal "I have species"): S, P, W, confidence, season and the verdict of every chosen species at the clicked spot,
// and the combined score with the rule the map uses. The numbers are visible in both views; Details holds the rest.
export default function ChosenHere({ api, selIds, combine, onlySeason, full, point, onInfo }) {
  const [showAll, setShowAll] = useState(false)
  let body
  if (api.status === 'loading' || api.status === 'idle') body = <Loading what="Looking up your chosen species" />
  else if (api.status === 'error') body = <p className="nw-plain">Your chosen species could not be looked up for this spot.</p>
  else {
    const byId = new Map(api.data.ranking.map((r) => [r.species_id, r]))
    const rows = selIds.map((id) => byId.get(id)).filter(Boolean)
    const eligibleAll = rows.length > 0 && rows.every((r) => r.eligible)
    const lowest = rows.reduce((a, r) => (a === null || r.W < a.W ? r : a), null)
    const highest = rows.reduce((a, r) => (a === null || r.W > a.W ? r : a), null)
    const combined = combine === 'all' ? (eligibleAll ? lowest.W : 0) : (highest?.W ?? 0)
    const limiting = rows.filter((r) => !r.eligible)
    const shown = showAll ? rows : rows.slice(0, MAX_ROWS)
    body = (
      <>
        <div className="nw-combined" role="status">
          <span className={`nw-chip ${combined > 0 ? 'fc-verified_plantable' : 'fc-not_plantable'}`}>{full ? `Combined score W ${fmt(combined)}` : `Combined match ${matchText(combined)}`}</span>
          <span className="nw-count-line">{combine === 'all' ? `Suits all: lowest ${full ? 'W' : 'match'} of your species` : `Suits at least one: highest ${full ? 'W' : 'match'} of your species`}</span>
          {combine === 'all' && limiting.length > 0 && <div className="muted">Not suitable here for: {limiting.map((r) => r.common_name).join(', ')}.</div>}
          {combine === 'any' && highest && highest.W > 0 && <div className="muted">Best of them here: {highest.common_name}.</div>}
        </div>
        <ul className="nw-plist">
          {shown.map((item) => {
            const v = verdict(item, full)
            return (
              <li key={`${item.species_id}|${full}`} className={`nw-prow level-${wLevel(item.W, item.eligible)}`}>
                <div className="nw-prow-main">
                  <button type="button" className="nw-namebtn nw-prow-name" onClick={() => onInfo(item.species_id)}>
                    {item.common_name}
                    <span className="sr-only"> (species information)</span>
                  </button>
                  {full ? <ScoreChip w={item.W} eligible={item.eligible} /> : <MatchChip w={item.W} eligible={item.eligible} />}
                  <SeasonBadge season={item.season} strip={false} best={false} />
                </div>
                {full && (
                  <div className="nw-nums">
                    Site S {fmt(item.S)} · Purpose P {fmt(item.P)} · Overall W {fmt(item.W)} · Confidence {pct(item.confidence) ?? 'Data Unavailable'}
                  </div>
                )}
                <div className={v.ok ? 'nw-verdict is-ok' : 'nw-verdict is-no'}>
                  <Icon name={v.ok ? 'check' : 'close'} /> 
                  {v.text}
                </div>
                {onlySeason && item.season?.status === 'out_of_season' && <div className="muted">Left out of the map colours by your dates filter.</div>}
                <details className="nw-pdetails" open={full || undefined}>
                  <summary>
                    Details<span className="sr-only"> for {item.common_name}</span>
                  </summary>
                  <RowDetails item={item} point={point} full={full} />
                </details>
              </li>
            )
          })}
        </ul>
        {rows.length > MAX_ROWS && (
          <div className="nw-more-row">
            <button type="button" className="btn btn-small" aria-pressed={showAll} onClick={() => setShowAll((s) => !s)}>
              {showAll ? `Show ${MAX_ROWS}` : 'Show all'}
            </button>
          </div>
        )}
      </>
    )
  }
  return (
    <section className="nw-pcard nw-chosen" aria-label="Your chosen species here">
      <div className="nw-pcard-head">
        <h3>Your chosen species here</h3>
        <span className="nw-chip">{selIds.length} chosen</span>
      </div>
      {body}
    </section>
  )
}
