import { useState } from 'react'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { REASONS, REASON_LABEL, STATUS_LABEL, STATUS_SYMBOL, when } from './fieldLabels.js'
import { apiPost } from './apiPost.js'

// "Field check" of one point: the current status, the history (who, when, why) and the three buttons to add a new check.
// Nothing is ever edited or deleted: every button saves a NEW check, and the newest one is the current status.
export default function FieldCheckSection({ pointId, api, observer, onObserver, onSaved }) {
  const [reason, setReason] = useState('paved')
  const [note, setNote] = useState('')
  const [asNot, setAsNot] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null) // { ok, text }

  const current = api.status === 'ok' ? api.data.current : null
  const history = api.status === 'ok' ? [...api.data.history].reverse() : []
  const clearing = current?.status === 'not_plantable'

  async function save(status) {
    setMsg(null)
    if (observer.trim() === '') return setMsg({ ok: false, text: 'Please type your name first (it is saved with the check).' })
    if (clearing && status !== 'not_plantable' && note.trim() === '') return setMsg({ ok: false, text: 'A note is needed to clear a “not plantable” mark: say what you saw.' })
    setBusy(true)
    try {
      const body = { point_id: pointId, status, observer: observer.trim(), note: note.trim() || null }
      if (status === 'not_plantable') body.reason = reason
      const r = await apiPost('/field-checks', body)
      setMsg({ ok: true, text: `Saved. ${r.effect}` })
      setNote('')
      setAsNot(false)
      onSaved()
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="fc" aria-label="Field check">
      <h3>Field check</h3>
      {api.status === 'loading' && <Loading what="Loading the field checks" />}
      {api.status === 'error' && <ErrorBox error={api.error} onRetry={api.retry} title="Could not load the field checks" brief />}
      {api.status === 'ok' && (
        <>
          {!current ? (
            <p className="muted">Not checked in the field yet.</p>
          ) : (
            <div className={`fc-status fc-${current.status}`} role="status">
              <strong>
                <span aria-hidden="true">{STATUS_SYMBOL[current.status]} </span>
                {STATUS_LABEL[current.status]}
                {current.status === 'not_plantable' && ` (${REASON_LABEL[current.reason] ?? current.reason})`}
              </strong>
              <div className="muted">
                by {current.observer} · {when(current.observed_at)}
                {current.note ? ` · “${current.note}”` : ''}
              </div>
              {current.disputed && <div className="fc-warn">⚠ Disputed: the latest two checks come from different people and disagree. Please check again.</div>}
              {current.status === 'not_plantable' && <div className="muted">{current.left_out_of_rankings ? 'Left out of rankings and plans.' : 'The field-check switch is off: this point is still ranked.'}</div>}
              {current.status === 'verified_plantable' && <div className="muted">A badge only: the scores are not changed.</div>}
              {current.status === 'needs_recheck' && <div className="fc-warn">⚠ Needs a second look (still ranked).</div>}
            </div>
          )}

          <div className="fc-form">
            <label className="fc-label" htmlFor="fc-observer">
              Your name (saved in this browser)
            </label>
            <input id="fc-observer" className="fc-input" value={observer} maxLength={80} onChange={(e) => onObserver(e.target.value)} placeholder="e.g. Juan Dela Cruz" />
            <label className="fc-label" htmlFor="fc-note">
              Note {clearing ? '(required to clear a “not plantable” mark)' : '(optional)'}
            </label>
            <textarea id="fc-note" className="fc-input" rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What did you see?" />
            {asNot && (
              <>
                <label className="fc-label" htmlFor="fc-reason">
                  Why is it not plantable?
                </label>
                <select id="fc-reason" className="fc-input" value={reason} onChange={(e) => setReason(e.target.value)}>
                  {REASONS.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </>
            )}
            <div className="fc-buttons">
              <button type="button" className="btn btn-small" disabled={busy} onClick={() => save('verified_plantable')}>
                ◯ Verified plantable
              </button>
              {asNot ? (
                <button type="button" className="btn btn-small fc-danger" disabled={busy} onClick={() => save('not_plantable')}>
                  ✕ Save as not plantable
                </button>
              ) : (
                <button type="button" className="btn btn-small" disabled={busy} onClick={() => setAsNot(true)}>
                  ✕ Not plantable…
                </button>
              )}
              <button type="button" className="btn btn-small" disabled={busy} onClick={() => save('needs_recheck')}>
                △ Needs recheck
              </button>
            </div>
            {msg && (
              <p className={msg.ok ? 'fc-ok' : 'fc-bad'} role="status">
                {msg.text}
              </p>
            )}
            <p className="muted">There is no login yet: a check carries a name only, and anyone with access can add one.</p>
          </div>

          {history.length > 0 && (
            <details open>
              <summary>History ({history.length})</summary>
              <ol className="fc-history">
                {history.map((e) => (
                  <li key={e.check_id}>
                    <strong>
                      <span aria-hidden="true">{STATUS_SYMBOL[e.status]} </span>
                      {STATUS_LABEL[e.status]}
                    </strong>
                    {e.reason ? ` · ${REASON_LABEL[e.reason] ?? e.reason}` : ''} · {e.observer} · {when(e.observed_at)}
                    {e.source === 'kit_import' ? ' · from a field kit' : ''}
                    {e.note ? <div className="muted">“{e.note}”</div> : null}
                    {e.moved_lat != null && e.moved_lon != null ? (
                      <div className="muted">
                        Stake placed at {Number(e.moved_lat).toFixed(6)}, {Number(e.moved_lon).toFixed(6)}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ol>
            </details>
          )}
        </>
      )}
    </section>
  )
}
