import { useState } from 'react'
import Icon from './Icon.jsx'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { REASON_LABEL, STATUS_LABEL, STATUS_SYMBOL, when } from './fieldLabels.js'
import FieldChip from './FieldChip.jsx'
import { fieldClass } from './fieldStatus.js'
import { apiPost } from './apiPost.js'
import HelpTip from './HelpTip.jsx'

// Each choice is a NEW event of the existing POST /field-checks (never an edit of an old one).
const REASONS = [
  { label: 'Paved or road', reason: 'paved' },
  { label: 'Building', reason: 'building' },
  { label: 'River or creek', reason: 'creek_or_waterlogged' },
  { label: 'Rock or ledge', reason: 'rock_or_ledge' },
  { label: 'Too steep', reason: 'too_steep' },
  { label: 'Existing tree', reason: 'existing_tree' },
  { label: 'Owner refused', reason: 'owner_refused' },
  { label: 'Other', reason: 'other' },
]

const describe = (e) =>
  e.status === 'not_plantable' ? `Not plantable: ${REASON_LABEL[e.reason] ?? e.reason}` : e.status === 'planted' ? `Planted: ${e.trees_planted} trees` : STATUS_LABEL[e.status]

// The field-check card of the point panel: one short line (with a "?" for the full explanation), a compact row of three actions, the status chip and a collapsed history.
// block = { planId, trees, ref } when the point is a block of the open plan: the first action is then "Planted" with a count box (default: all the trees of the block).
export default function VerifyBar({ pointId, api, observer, onObserver, onSaved, block = null }) {
  const [count, setCount] = useState(() => (block ? String(block.trees) : ''))
  const [editing, setEditing] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [askName, setAskName] = useState(() => observer.trim() === '')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null) // { ok, text }

  const current = api.status === 'ok' ? api.data.current : null
  const history = api.status === 'ok' ? [...api.data.history].reverse() : []
  const foreign = !!block && current?.status === 'planted' && current.plan_id !== block.planId // planted for ANOTHER plan: it does not count for this one
  const showButtons = api.status === 'ok' && (!current || editing || foreign)
  const clearing = current?.status === 'not_plantable'

  async function save(choice) {
    setMsg(null)
    if (observer.trim() === '') return setMsg({ ok: false, text: 'Please type your name first (it is saved with the check).' })
    const status = choice.status ?? 'not_plantable'
    if (status === 'planted' && !(/^\d+$/.test(count.trim()) && Number(count) <= block.trees)) return setMsg({ ok: false, text: `Trees planted: a whole number from 0 to ${block.trees}.` })
    if (clearing && status !== 'not_plantable' && note.trim() === '') return setMsg({ ok: false, text: 'A note is needed to clear a “not plantable” mark: say what you saw.' })
    setBusy(true)
    try {
      const body = { point_id: pointId, status, observer: observer.trim(), note: note.trim() || null }
      if (status === 'not_plantable') body.reason = choice.reason
      if (block) body.plan_id = block.planId
      if (status === 'planted') body.trees_planted = Number(count)
      await apiPost('/field-checks', body)
      setMsg({ ok: true, text: status === 'planted' ? `Saved: ${count} of ${block.trees} trees planted` : `Saved: ${choice.label}` })
      setNote('')
      setEditing(false)
      setMenuOpen(false)
      setAskName(false)
      onSaved()
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="nw-pcard fc fc-top" aria-label="Check this spot">
      <div className="nw-pcard-head">
        <h3>Field check</h3>
        {current ? (
          <FieldChip cls={fieldClass(current.status, current.reason)} text={describe(current)} />
        ) : api.status === 'ok' ? (
          <span className="nw-chip">Not checked</span>
        ) : null}
      </div>
      <div className="nw-opt-head fc-warnrow">
        <span className="fc-warnline">Check this square on the ground before planting.</span>
        <HelpTip label="Check this square">This is a map square of about 100 m, not an exact tree spot. Check it on the ground before planting.</HelpTip>
      </div>
      {api.status === 'loading' && <Loading what="Loading the field checks" />}
      {api.status === 'error' && <ErrorBox error={api.error} onRetry={api.retry} title="Could not load the field checks" brief />}

      {msg && (
        <p className={msg.ok ? 'fc-ok fc-saved' : 'fc-bad'} role="status">
          {msg.ok && <Icon name="check" />} 
          {msg.text}
        </p>
      )}

      {current && (
        <div className="fc-status-line" role="status">
          <span className="muted">
            by {current.observer} · {when(current.observed_at)}
            {current.note ? ` · “${current.note}”` : ''}
          </span>
          {current.disputed && <div className="fc-warn"><Icon name="warn" /> Disputed: the latest two checks disagree.</div>}
          {current.status === 'needs_recheck' && <div className="fc-warn"><Icon name="warn" /> Needs a second look (still ranked).</div>}
          {foreign && <div className="fc-warn"><Icon name="warn" /> Planted for another plan ({current.plan_id ?? 'no plan'}): it does not count for this plan.</div>}
          {!editing && !foreign && (
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
                Your name (asked once, remembered)
              </label>
              <input id="nw-fc-name" className="fc-input" value={observer} maxLength={80} onChange={(e) => onObserver(e.target.value)} placeholder="e.g. Juan Dela Cruz" />
            </div>
          )}
          <div className="fc-row" role="group" aria-label="What did you find at this spot?">
            {block ? (
              <button type="button" className="fc-bigbtn fc-b-planted" disabled={busy} onClick={() => save({ label: 'Planted', status: 'planted' })}>
                <Icon name="tree" /> Planted
              </button>
            ) : (
              <button type="button" className="fc-bigbtn fc-b-verified_plantable" disabled={busy} onClick={() => save({ label: 'Plantable', status: 'verified_plantable' })}>
                <Icon name="ring" /> Plantable
              </button>
            )}
            <button type="button" className="fc-bigbtn fc-b-not_plantable" aria-expanded={menuOpen} aria-haspopup="true" disabled={busy} onClick={() => setMenuOpen((o) => !o)}>
              <Icon name="close" /> {block ? "Can't plant here" : 'Not plantable'} <Icon name="down" size={14} />
            </button>
            <button type="button" className="fc-bigbtn fc-b-needs_recheck" disabled={busy} onClick={() => save({ label: 'Needs recheck', status: 'needs_recheck' })}>
              <Icon name="triangle" /> Needs recheck
            </button>
          </div>
          {block && (
            <div className="fc-count">
              <label className="fc-label" htmlFor="nw-fc-count">
                Trees planted (of {block.trees})
              </label>
              <input id="nw-fc-count" type="number" min="0" max={block.trees} className="fc-input fc-count-input" value={count} onChange={(e) => setCount(e.target.value)} inputMode="numeric" />
            </div>
          )}
          {menuOpen && (
            <div className="fc-menu" role="group" aria-label="Why is it not plantable?">
              {REASONS.map((o) => (
                <button key={o.reason} type="button" className="fc-menubtn" disabled={busy} onClick={() => save({ ...o, status: 'not_plantable' })}>
                  <Icon name="close" size={14} /> {o.label}
                </button>
              ))}
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
        <details className="fc-hist">
          <summary>History ({history.length})</summary>
          <ol className="fc-history">
            {history.map((e) => (
              <li key={e.check_id}>
                <strong>
                  <Icon name={STATUS_SYMBOL[e.status]} /> 
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
