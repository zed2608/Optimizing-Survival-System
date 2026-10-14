import { useMemo, useState } from 'react'
import { API_BASE } from '../v2/config.js'
import { useApi } from '../v2/useApi.js'
import { apiDelete, apiPost } from './apiPost.js'
import Icon from './Icon.jsx'
import { TEXT, boxState, expiryLines, fullUrl, isLocalAddress } from './planterLink.js'
import { qrSvg } from './planterQr.js'

// "Make a link for the planter" (stage A2). POST /plans/{id}/field-pack makes the Field Pack page of the plan and keeps it under a random token; the link and its QR code open it on a phone
// WITHOUT the access code. The link stops after at most 24 hours, when the server restarts, or when it is switched off here (DELETE). One live link per plan: a new one replaces the old one.
// Everything is in two languages (English, with the Filipino under it). The words and the decisions are in planterLink.js (tested).
function T({ k }) {
  return (
    <>
      {TEXT[k].en}
      <span className="nw-fil">{TEXT[k].fil}</span>
    </>
  )
}

export default function PlanterLink({ planId }) {
  const [version, setVersion] = useState(0)
  const [making, setMaking] = useState(false)
  const [error, setError] = useState('')
  const [asking, setAsking] = useState(false)
  const [copied, setCopied] = useState(false)
  const [fresh, setFresh] = useState(null) // the answer of the last POST (the info call follows a moment later)
  const read = useApi(`/plans/${planId}/field-pack?v=${version}`)
  const info = fresh && fresh.live ? fresh : read.status === 'ok' ? read.data : null
  const state = boxState({ making, error, info })
  const address = info && info.url ? fullUrl(API_BASE, window.location.origin, info.url) : ''
  const qr = useMemo(() => (address ? qrSvg(address) : null), [address])
  const when = info && info.expires_at ? expiryLines(info.expires_at) : null

  async function make() {
    setMaking(true)
    setError('')
    setAsking(false)
    setCopied(false)
    try {
      const out = await apiPost(`/plans/${planId}/field-pack`, {})
      setFresh(out)
      setVersion((v) => v + 1)
    } catch (e) {
      setError(e.message)
    } finally {
      setMaking(false)
    }
  }

  async function switchOff() {
    setAsking(false)
    setError('')
    try {
      await apiDelete(`/plans/${planId}/field-pack`)
      setFresh({ live: false })
      setVersion((v) => v + 1)
    } catch (e) {
      setError(e.message)
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(address)
      setCopied(true)
    } catch {
      const box = document.getElementById(`plink-url-${planId}`)
      if (box) { box.focus(); box.select() } // the person can press Ctrl+C / long-press
    }
  }

  return (
    <div className="nw-plink" data-state={state}>
      <h4>
        <T k="make" />
      </h4>
      {state === 'making' && (
        <p className="nw-plain" role="status">
          <T k="making" />
        </p>
      )}
      {(state === 'none' || state === 'live' || state === 'error' || state === 'making') && (
        <button type="button" className="nw-btn nw-btn-go nw-plink-main" onClick={make} disabled={making} data-act="make">
          <Icon name="mappin" /> <span>{state === 'live' ? <T k="again" /> : <T k="make" />}</span>
        </button>
      )}
      {state === 'error' && (
        <div role="alert" className="fc-bad">
          <p>{error}</p>
          <button type="button" className="nw-btn" onClick={make} data-act="retry">
            <T k="retry" />
          </button>
        </div>
      )}
      {state === 'live' && (
        <div className="nw-plink-box">
          <p className="nw-plain">
            <T k="hint" />
          </p>
          <div className="nw-plink-url">
            <input id={`plink-url-${planId}`} type="text" readOnly value={address} aria-label="Planter link" onFocus={(e) => e.target.select()} />
            <button type="button" className="nw-btn" onClick={copy} data-act="copy">
              {copied ? <T k="copied" /> : <T k="copy" />}
            </button>
          </div>
          {isLocalAddress(address) && (
            <p className="fc-bad" role="note">
              {TEXT.localOnly.en}
              <span className="nw-fil">{TEXT.localOnly.fil}</span>
            </p>
          )}
          {qr && (
            <svg className="nw-plink-qr" viewBox={qr.viewBox} role="img" aria-label={TEXT.qrLabel.en} data-qr={qr.size}>
              <path d={qr.d} />
            </svg>
          )}
          {when && (
            <p className="nw-plain" data-role="expiry">
              {when.en}
              <span className="nw-fil">{when.fil}</span>
            </p>
          )}
          <p className="nw-plink-warn" role="note">
            {TEXT.warn.en}
            <span className="nw-fil">{TEXT.warn.fil}</span>
          </p>
          {!asking && (
            <button type="button" className="nw-btn" onClick={() => setAsking(true)} data-act="off">
              <T k="off" />
            </button>
          )}
          {asking && (
            <div className="nw-plink-ask" role="alertdialog" aria-label={TEXT.off.en}>
              <p>
                {TEXT.offAsk.en}
                <span className="nw-fil">{TEXT.offAsk.fil}</span>
              </p>
              <div className="nw-row">
                <button type="button" className="nw-btn" onClick={switchOff} data-act="off-yes">
                  <T k="offYes" />
                </button>
                <button type="button" className="nw-btn nw-btn-go" onClick={() => setAsking(false)} data-act="off-no">
                  <T k="offNo" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
