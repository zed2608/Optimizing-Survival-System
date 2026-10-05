import { useState } from 'react'
import { ErrorBox, Loading } from './Status.jsx'
import ColorLegend from './ColorLegend.jsx'
import SpeciesRow from './SpeciesRow.jsx'
import { fmt } from '../scale.js'
import { DIRECTION, friendlyNotRankable, purposeLabel } from '../labels.js'

function ViableSuggestion({ status, onGo }) {
  if (status.status === 'idle') return null
  if (status.status === 'loading') return <Loading what="Looking for the nearest suitable spot" />
  if (status.status === 'error') {
    return status.error.status === 404 ? (
      <p className="notice" role="status">
        No suitable spot was found within 5 km of here.
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

// The ranking panel: idle hint, loading, friendly 404 messages with a nearest-spot offer, errors, or the ranked species.
export default function RankingPanel({ rank, purpose, onFindViable, viable, onGo }) {
  const [open, setOpen] = useState({})
  const toggle = (id) => setOpen((o) => ({ ...o, [id]: !o[id] }))

  if (rank.status === 'idle') {
    return (
      <div className="panel-body">
        <p>
          <strong>Start here:</strong> click a place on the map, or type its coordinates in the box above. You will see which trees suit that place for
          “{purposeLabel(purpose)}”.
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
      <ColorLegend />
      <ol className="species-list" aria-label={`Ranked species for ${purposeLabel(purpose)}`}>
        {ranking.map((item) => (
          <SpeciesRow key={item.species_id} item={item} point={point} open={!!open[item.species_id]} onToggle={() => toggle(item.species_id)} />
        ))}
      </ol>
    </div>
  )
}
