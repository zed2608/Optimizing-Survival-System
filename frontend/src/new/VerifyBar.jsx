import { useState } from 'react'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { REASON_LABEL, STATUS_LABEL, STATUS_SYMBOL, when } from './fieldLabels.js'
import { apiPost } from './apiPost.js'

// One tap = one saved check. Each choice is a NEW event of the existing POST /field-checks (never an edit of an old one).
const CHOICES = [
  { key: 'ok', label: 'Plantable', symbol: '◯', status: 'verified_plantable' },
  { key: 'paved', label: 'Paved or road', symbol: '✕', status: 'not_plantable', reason: 'paved' },
  { key: 'building', label: 'Building', symbol: '✕', status: 'not_plantable', reason: 'building' },
  { key: 'creek', label: 'River or creek', symbol: '✕', status: 'not_plantable', reason: 'creek_or_waterlogged' },
]
const OTHER = [
  { label: 'Rock or ledge', reason: 'rock_or_ledge' },
  { label: 'Too steep', reason: 'too_steep' },
  { label: 'Existing tree', reason: 'existing_tree' },
  { label: 'Owner refused', reason: 'owner_refused' },
  { label: 'Other', reason: 'other' },
]

const describe = (e) => (e.status === 'not_plantable' ? `Not plantable: ${REASON_LABEL[e.reason] ?? e.reason}` : STATUS_LABEL[e.status])

// The top of the point panel: the 100 m warning, the big one-tap buttons, the current field status and the short history.
export default function VerifyBar({ pointId, api, observer, onObserver, onSaved }) {
  const [editing, setEditing] = useState(false)
  const [otherOpen, setOtherOpen] = useState(false)
  const [askName, setAskName] = useState(() => observer.trim() === '')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null) // { ok, text }

  const current = api.status === 'ok' ? api.data.current : null
  const history = api.status === 'ok' ? [...api.data.history].reverse() : []
  const showButtons = api.status === 'ok' && (!current || editing)
  const clearing = current?.status === 'not_plantable'

  async function save(choice) {
    setMsg(null)
    if (observer.trim() === '') return setMsg({ ok: false, text: 'Please type your name first (it is saved with the check).' })
    const status = choice.status ?? 'not_plantable'
    if (clearing && status !== 'not_plantable' && note.trim() === '') return setMsg({ ok: false, text: 'A note is needed to clear a “not plantable” mark: say what you saw.' })
    setBusy(true)
    try {
      const body = { point_id: pointId, status, observer: observer.trim(), note: note.trim() || null }
      if (status === 'not_plantable') body.reason = choice.reason
      await apiPost('/field-checks', body)
      setMsg({ ok: true, text: `Saved: ${choice.label}` })
      setNote('')
      setEditing(false)
      setOtherOpen(false)
      setAskName(false)
      onSaved()
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    } finally {
      setBusy(false)
    }
  }

  const bigBtn = (c) => (
    <button key={c.key ?? c.reason} type="button" className={`fc-bigbtn fc-b-${c.status ?? 'not_plantable'}`} disabled={busy} onClick={() => save(c)}>
      <span aria-hidden="true">{c.symbol} </span>
      {c.label}
    </button>
  )

  return (
    <section className="fc fc-top" aria-label="Check this spot">
      <p className="fc-warnline">
        <span aria-hidden="true">⚠ </span>This is a map square of about 100 m, not an exact tree spot. Check it on the ground before planting.
      </p>
      {api.status === 'loading' && <Loading what="Loading the field checks" />}
      {api.status === 'error' && <ErrorBox error={api.error} onRetry={api.retry} title="Could not load the field checks" brief />}

      {msg && (
        <p className={msg.ok ? 'fc-ok fc-saved' : 'fc-bad'} role="status">
          {msg.ok && <span aria-hidden="true">✔ </span>}
          {msg.text}
        </p>
      )}

      {current && (
        <div className={`fc-status fc-${current.status}`} role="status">
          <strong>
            <span aria-hidden="true">{STATUS_SYMBOL[current.status]} </span>
            {describe(current)}
          </strong>
          <div className="muted">
            by {current.observer} · {when(current.observed_at)}
            {current.note ? ` · “${current.note}”` : ''}
          </div>
          {current.disputed && <div className="fc-warn">⚠ Disputed: the latest two checks come from different people and disagree. Please check again.</div>}
          {current.status === 'needs_recheck' && <div className="fc-warn">⚠ Needs a second look (still ranked).</div>}
          {current.status === 'verified_plantable' && <div className="muted">A badge only: the scores are not changed.</div>}
          {!editing && (
            <button type="button" className="fc-link" onClick={() => setEditing(true)}>
              Change
            </button>
          )}
        </div>
      )}

      {showButtons && (
        <div className="fc-choose">
          {askName && (
            <div className="fc-name">
              <label className="fc-label" htmlFor="nw-fc-name">
                Your name (asked once, remembered in this browser)
              </label>
              <input id="nw-fc-name" className="fc-input" value={observer} maxLength={80} onChange={(e) => onObserver(e.target.value)} placeholder="e.g. Juan Dela Cruz" />
            </div>
          )}
          <div className="fc-big" role="group" aria-label="What did you find at this spot?">
            {CHOICES.map(bigBtn)}
            <button type="button" className="fc-bigbtn fc-b-other" aria-expanded={otherOpen} disabled={busy} onClick={() => setOtherOpen((o) => !o)}>
              <span aria-hidden="true">✕ </span>Other problem…
            </button>
            <button type="button" className="fc-bigbtn fc-b-needs_recheck" disabled={busy} onClick={() => save({ label: 'Needs recheck', status: 'needs_recheck' })}>
              <span aria-hidden="true">△ </span>Needs recheck
            </button>
          </div>
          {otherOpen && (
            <div className="fc-big fc-other" role="group" aria-label="Other problems">
              {OTHER.map((o) => bigBtn({ ...o, symbol: '✕', status: 'not_plantable' }))}
            </div>
          )}
          <details className="fc-notebox" open={clearing}>
            <summary>Add a note{clearing ? ' (needed to clear a “not plantable” mark)' : ' (optional)'}</summary>
            <textarea id="nw-fc-note" className="fc-input" rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What did you see?" aria-label="Note" />
          </details>
          {editing && (
            <button type="button" className="fc-link" onClick={() => setEditing(false)}>
              Keep the current check
            </button>
          )}
        </div>
      )}

      {history.length > 0 && (
        <details className="fc-hist" open>
          <summary>Field history ({history.length})</summary>
          <ol className="fc-history">
            {history.map((e) => (
              <li key={e.check_id}>
                <strong>
                  <span aria-hidden="true">{STATUS_SYMBOL[e.status]} </span>
                  {describe(e)}
                </strong>{' '}
                · {e.observer} · {when(e.observed_at)}
                {e.source === 'kit_import' ? ' · from a field kit' : ''}
                {e.note ? <span className="muted"> · “{e.note}”</span> : null}
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  )
}
