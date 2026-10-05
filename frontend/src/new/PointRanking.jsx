import { useState } from 'react'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import ColorLegend from '../v2/components/ColorLegend.jsx'
import Explanation from '../v2/components/Explanation.jsx'
import FlagBadges from '../v2/components/FlagBadges.jsx'
import ScoreChip from '../v2/components/ScoreChip.jsx'
import { fmt, pct, wLevel } from '../v2/scale.js'
import { DIRECTION, friendlyNotRankable, purposeLabel } from '../v2/labels.js'
import SeasonBadge, { SeasonDetail } from './SeasonBadge.jsx'

function ViableSuggestion({ status, onGo }) {
  if (status.status === 'idle') return null
  if (status.status === 'loading') return <Loading what="Looking for the nearest suitable spot" />
  if (status.status === 'error') {
    return status.error.status === 404 ? (
      <p className="notice" role="status">
        {status.error.message.includes('planted between') ? status.error.message : 'No suitable spot was found within 5 km of here.'}
      </p>
    ) : (
      <ErrorBox error={status.error} onRetry={status.retry} title="Could not look for a nearby spot" brief />
    )
  }
  const v = status.data
  return (
    <div className="suggestion" role="status">
      <p>
        {v.already_viable ? 'This spot is already suitable.' : <>The nearest suitable spot is about <strong>{Math.round(v.distance_m)} m to the {DIRECTION[v.direction] ?? v.direction}</strong>.</>}{' '}
        Best species there: <strong>{v.best_species.common_name}</strong> (overall score {fmt(v.best_species.W)}).
      </p>
      <button type="button" className="btn" onClick={() => onGo(v.point.lat, v.point.lon)}>
        Go to this spot and rank the species
      </button>
    </div>
  )
}

// One species of the ranking, with its season badge and strip, and the season in full sentences inside "Why this score?".
function SpeciesRowNew({ item, point, open, onToggle, onInfo }) {
  const panelId = `explain-${item.species_id}`
  return (
    <li className={`species level-${wLevel(item.W, item.eligible)}`}>
      <div className="species-head">
        <span className="rank-no" aria-label={`Rank ${item.rank}`}>
          {item.rank}
        </span>
        <div className="species-main">
          <h3 className="species-name">
            <button type="button" className="nw-namebtn" onClick={() => onInfo(item.species_id)}>
              {item.common_name}
              <span className="sr-only"> (species information)</span>
            </button>
          </h3>
          <ScoreChip w={item.W} eligible={item.eligible} />
          <dl className="scores">
            <div>
              <dt>Site suitability (S)</dt>
              <dd>{fmt(item.S) ?? 'Data Unavailable'}</dd>
            </div>
            <div>
              <dt>Purpose fitness (P)</dt>
              <dd>{fmt(item.P) ?? 'Data Unavailable'}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{pct(item.confidence) ?? 'Data Unavailable'}</dd>
            </div>
          </dl>
          <SeasonBadge season={item.season} />
          <FlagBadges flags={item.flags} />
          {!item.eligible && <p className="muted">Not suitable here: site suitability is below 0.50, so the overall score is 0.</p>}
        </div>
        <button type="button" className="btn btn-small" aria-expanded={open} aria-controls={panelId} onClick={onToggle}>
          {open ? 'Hide explanation' : 'Why this score?'}
          <span className="sr-only"> for {item.common_name}</span>
        </button>
      </div>
      {open && (
        <div id={panelId} className="explain-wrap" role="region" aria-label={`Explanation for ${item.common_name}`}>
          <SeasonDetail season={item.season} />
          <Explanation item={item} point={point} />
        </div>
      )}
    </li>
  )
}

// The ranking of species for one spot (the earlier RankingPanel, plus the season of every species and a notice when the season filter leaves nothing).
export default function PointRanking({ rank, purpose, onFindViable, viable, onGo, seasonNote, onInfo }) {
  const [open, setOpen] = useState({})
  const toggle = (id) => setOpen((o) => ({ ...o, [id]: !o[id] }))

  if (rank.status === 'idle') {
    return (
      <div className="panel-body">
        <p>
          <strong>Start here:</strong> click a place on the map, or search for it. You will see which trees suit that place for “{purposeLabel(purpose)}”.
        </p>
        <ColorLegend />
      </div>
    )
  }
  if (rank.status === 'loading') return <div className="panel-body"><Loading what="Ranking species for this spot" /></div>
  if (rank.status === 'error') {
    if (rank.error.status === 404) {
      const f = friendlyNotRankable(rank.error.message)
      return (
        <div className="panel-body">
          <div className="notice" role="status">
            <strong>{f.title}</strong>
            <p>{f.text}</p>
          </div>
          <button type="button" className="btn" onClick={onFindViable} disabled={viable.status === 'loading'}>
            Find the nearest suitable spot
          </button>
          <ViableSuggestion status={viable} onGo={onGo} />
        </div>
      )
    }
    return <div className="panel-body"><ErrorBox error={rank.error} onRetry={rank.retry} title="Could not rank the species" brief /></div>
  }

  const { point, ranking } = rank.data
  return (
    <div className="panel-body">
      <section className="place" aria-label="The place that was ranked">
        <h2>Species for this spot</h2>
        <p className="muted">
          Grid point {point.point_id} ({Math.round(point.distance_m)} m from where you clicked) · {point.zone ?? 'zone not stated'}
          {point.elev_m != null ? ` · ${point.elev_m} m above sea level` : ''}
          {point.slope_pct != null ? ` · slope ${Number(point.slope_pct).toFixed(0)} %` : ''}
        </p>
        <p className="muted">
          Each point stands for a 100 m × 100 m cell. Showing the top {ranking.length} of {rank.data.species_total} species; {rank.data.species_eligible} are suitable here.
        </p>
      </section>
      {ranking.length === 0 && seasonNote}
      <ColorLegend />
      {rank.data.season && <p className="muted">Month strip: filled = planting months, ringed = your dates.</p>}
      {rank.data.left_out_by_field_check && (
        <p className="notice" role="status">
          <span aria-hidden="true">✕ </span>Left out of plans because of a field check. The ranking below is shown greyed out for information only.
        </p>
      )}
      <ol className={`species-list ${rank.data.left_out_by_field_check ? 'is-greyed' : ''}`} aria-label={`Ranked species for ${purposeLabel(purpose)}`}>
        {ranking.map((item) => (
          <SpeciesRowNew key={item.species_id} item={item} point={point} open={!!open[item.species_id]} onToggle={() => toggle(item.species_id)} onInfo={onInfo} />
        ))}
      </ol>
    </div>
  )
}
