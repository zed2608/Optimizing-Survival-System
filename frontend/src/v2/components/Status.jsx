import { API_BASE, START_COMMAND } from '../config.js'

export function Loading({ what = 'Loading' }) {
  return (
    <p className="status loading" role="status">
      <span className="spinner" aria-hidden="true" /> {what}…
    </p>
  )
}

// An error with a retry button. If the API cannot be reached at all, say how to start it.
export function ErrorBox({ error, onRetry, title = 'Something went wrong', brief = false }) {
  const off = error?.network
  if (off && brief) {
    return (
      <div className="status error" role="alert">
        <p>
          The planning service is not running. Start it from the project folder with <code>{START_COMMAND}</code>, then press “Try again”.
        </p>
        {onRetry && (
          <button type="button" className="btn" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    )
  }
  return (
    <div className="status error" role="alert">
      <strong>{off ? 'The planning service is not running' : title}</strong>
      <p>{error?.message ?? 'Unknown error.'}</p>
      {off && (
        <p>
          Start it in a terminal, from the project folder, with:
          <br />
          <code>{START_COMMAND}</code>
          <br />
          Then press “Try again”. (Address used by this page: <code>{API_BASE}</code>)
        </p>
      )}
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}
