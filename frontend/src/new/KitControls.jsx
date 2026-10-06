import { useState } from 'react'
import { API_BASE } from '../v2/config.js'
import { useApi } from '../v2/useApi.js'
import { apiPost } from './apiPost.js'
import HelpTip from './HelpTip.jsx'
import { formatBytes } from './season.js'

// "Build field kit" for a saved plan: builds it (POST /plans/{id}/field-kit), shows what was built and a download link (GET /kits/{id}.zip). Rebuilding is allowed and replaces the old kit.
export default function KitControls({ planId, onChanged }) {
  const [version, setVersion] = useState(0)
  const [building, setBuilding] = useState(false)
  const [error, setError] = useState('')
  const info = useApi(`/plans/${planId}/field-kit?v=${version}`)
  const k = info.status === 'ok' && info.data.built ? info.data : null

  async function build() {
    setBuilding(true)
    setError('')
    try {
      await apiPost(`/plans/${planId}/field-kit`, {})
      setVersion((v) => v + 1)
      if (onChanged) onChanged()
    } catch (e) {
      setError(e.message)
    } finally {
      setBuilding(false)
    }
  }

  return (
    <div className="nw-kit">
      <div className="nw-opt-head">
        <span className="nw-grow nw-kit-inside">Inside: points for GPS apps, a Google Earth file, the point list, a printed map and instructions.</span>
        <HelpTip label="Using the field kit">Open the README first. Fill the point list in the field and bring it back with Import field checks.</HelpTip>
      </div>
      <div className="nw-row">
        <button type="button" className="btn" onClick={build} disabled={building || info.status === 'loading'}>
          {building ? 'Building… a few seconds' : k ? 'Rebuild field kit' : 'Build field kit'}
        </button>
        {k && (
          <a className="btn btn-primary nw-kit-dl" href={`${API_BASE}${k.download_url}`} download>
            Download kit (.zip)
          </a>
        )}
      </div>
      {building && (
        <p className="nw-plain" role="status">
          Building the kit… a few seconds.
        </p>
      )}
      {k && !building && (
        <dl className="nw-kit-info" aria-label="Field kit details">
          <div>
            <dt>Built</dt>
            <dd>{k.built_at ? k.built_at.replace('T', ' ').slice(0, 16) : 'Data Unavailable'}</dd>
          </div>
          <div>
            <dt>Size</dt>
            <dd>{formatBytes(k.zip_size_bytes)}</dd>
          </div>
          <div>
            <dt>Check code</dt>
            <dd className="nw-mono-big">{k.check_code ?? 'Data Unavailable'}</dd>
          </div>
          <div>
            <dt>Printed map (PDF)</dt>
            <dd>{k.pdf_included ? 'Included' : `Not included. ${k.pdf_note ?? ''}`}</dd>
          </div>
        </dl>
      )}
      {k && !building && <p className="muted">Rebuilding replaces the old kit.</p>}
      {info.status === 'error' && <p className="fc-bad">The kit information could not be loaded: {info.error.message}</p>}
      {error && (
        <p className="fc-bad" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
