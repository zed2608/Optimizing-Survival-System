import { ErrorBox, Loading } from './Status.jsx'

// Collapsible "Known limits" box, filled from GET /health. The button is in the header, so it is always reachable.
export default function LimitsBox({ health, open }) {
  if (!open) return null
  return (
    <section id="limits-panel" className="limits-panel" aria-label="Known limits">
      <h2>Known limits of this tool</h2>
      {health.status === 'loading' && <Loading what="Loading the known limits" />}
      {health.status === 'error' && <ErrorBox error={health.error} onRetry={health.retry} title="Could not load the known limits" brief />}
      {health.status === 'ok' && (
        <ul>
          {health.data.limits.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
