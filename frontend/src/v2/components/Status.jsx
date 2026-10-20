import { API_BASE, START_COMMAND } from '../config.js'
import Icon from '../../new/Icon.jsx'

export function Loading({ what = 'Loading' }) {
  return (
    <div className="status loading" role="status">
      <p>
        <span className="spinner" aria-hidden="true" /> {what}…
      </p>
      <span className="cy-skel-lines" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
    </div>
  )
}

// An error with a retry button. If the API cannot be reached at all, say how to start it.
export function ErrorBox({ error, onRetry, title = 'Something went wrong', brief = false }) {
  const off = error?.network
  if (off && brief) {
    return (
      <div className="status error" role="alert">
        <Icon name="warn" size={20} />
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
      <Icon name="warn" size={20} />
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
