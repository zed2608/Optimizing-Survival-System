import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { DIRECTION } from '../v2/labels.js'
import { fmt } from '../v2/scale.js'

// The answer of GET /nearest-viable: where the nearest suitable spot is, with a button to go there (shared by the point panel and the grey-square panel).
export default function ViableSuggestion({ status, onGo }) {
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
