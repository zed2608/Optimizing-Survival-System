import { useMemo, useState } from 'react'
import Icon from './Icon.jsx'
import HelpTip from './HelpTip.jsx'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { useApi } from '../v2/useApi.js'
import { apiPost } from './apiPost.js'
import { formatDay } from './season.js'

const ROUND_WORDS = { '3_month': '3 months', '6_month': '6 months', '1_year': '1 year', '5_year': '5 years', '10_year': '10 years', '50_year': '50 years', other: 'Other check' }
const STATE_WORDS = { done: 'Checked', due: 'Due now', overdue: 'Overdue', upcoming: 'Upcoming' }
const STATE_ICON = { done: 'check', due: 'warn', overdue: 'warn', upcoming: 'calendar' }
const STATUS_WORDS = { survived: 'Survived', dead: 'Dead', not_found: 'Not found' }
const CAUSE_WORDS = { drought: 'Drought', pest_disease: 'Pest or disease', flooding: 'Flooding', typhoon_wind: 'Typhoon / wind', vandalism: 'Vandalism', construction: 'Construction', unknown: 'Unknown', other: 'Other' }

function Schedule({ rows }) {
  return (
    <ul className="nw-counts nw-pcounts" aria-label="Monitoring schedule">
      {rows.map((r) => (
        <li key={r.round_label}>
          <Icon name={STATE_ICON[r.state]} /> {ROUND_WORDS[r.round_label] ?? r.round_label}: <strong>{STATE_WORDS[r.state]}</strong>
          {r.state !== 'done' && <span className="muted"> (due {formatDay(r.due_date, true)})</span>}
        </li>
      ))}
    </ul>
  )
}

function LogForm({ planId, blocks, onSaved }) {
  const [pointId, setPointId] = useState(blocks[0]?.point_id ?? '')
  const [roundLabel, setRoundLabel] = useState('3_month')
  const [status, setStatus] = useState('survived')
  const [alive, setAlive] = useState('')
  const [dead, setDead] = useState('0')
  const [cause, setCause] = useState('')
  const [observer, setObserver] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState('')
  const block = blocks.find((b) => b.point_id === Number(pointId))

  async function submit(e) {
    e.preventDefault()
    setProblem('')
    setBusy(true)
    try {
      const body = {
        plan_id: planId, point_id: Number(pointId), round_label: roundLabel, status, observer,
        trees_total: block?.trees_planted ?? 0, trees_alive: alive === '' ? 0 : Number(alive), trees_dead: dead === '' ? 0 : Number(dead),
        cause: cause || null, note: note || null,
      }
      await apiPost('/survival-checks', body)
      setNote('')
      onSaved()
    } catch (err) {
      setProblem(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="nw-survival-form" onSubmit={submit} aria-label="Log a survival check">
      <label className="nw-label" htmlFor="sv-point">
        Block
      </label>
      <select id="sv-point" className="nw-select" value={pointId} onChange={(e) => setPointId(e.target.value)}>
        {blocks.map((b) => (
          <option key={b.point_id} value={b.point_id}>
            {b.species} - {b.trees_planted} trees (point {b.point_id})
          </option>
        ))}
      </select>
      <div className="nw-row">
        <div>
          <label className="nw-label" htmlFor="sv-round">
            Round
          </label>
          <select id="sv-round" className="nw-select" value={roundLabel} onChange={(e) => setRoundLabel(e.target.value)}>
            {Object.entries(ROUND_WORDS).map(([k, w]) => (
              <option key={k} value={k}>
                {w}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="nw-label" htmlFor="sv-status">
            Status
          </label>
          <select id="sv-status" className="nw-select" value={status} onChange={(e) => setStatus(e.target.value)}>
            {Object.entries(STATUS_WORDS).map(([k, w]) => (
              <option key={k} value={k}>
                {w}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="nw-row">
        <div>
          <label className="nw-label" htmlFor="sv-alive">
            Trees alive{block ? ` (of ${block.trees_planted})` : ''}
          </label>
          <input id="sv-alive" className="nw-input" type="number" min="0" value={alive} onChange={(e) => setAlive(e.target.value)} />
        </div>
        <div>
          <label className="nw-label" htmlFor="sv-dead">
            Trees dead
          </label>
          <input id="sv-dead" className="nw-input" type="number" min="0" value={dead} onChange={(e) => setDead(e.target.value)} />
        </div>
      </div>
      {Number(dead) > 0 && (
        <>
          <label className="nw-label" htmlFor="sv-cause">
            Cause
          </label>
          <select id="sv-cause" className="nw-select" value={cause} onChange={(e) => setCause(e.target.value)}>
            <option value="">Choose a cause</option>
            {Object.entries(CAUSE_WORDS).map(([k, w]) => (
              <option key={k} value={k}>
                {w}
              </option>
            ))}
          </select>
        </>
      )}
      <label className="nw-label" htmlFor="sv-observer">
        Observer
      </label>
      <input id="sv-observer" className="nw-input" value={observer} onChange={(e) => setObserver(e.target.value)} placeholder="Your name" required />
      <label className="nw-label" htmlFor="sv-note">
        Note (optional)
      </label>
      <textarea id="sv-note" className="nw-input" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
      <button type="submit" className="btn btn-primary" disabled={busy || !pointId || !observer.trim()}>
        {busy ? 'Saving…' : 'Save check'}
      </button>
      {problem && (
        <p className="fc-bad" role="alert">
          {problem}
        </p>
      )}
    </form>
  )
}

// Survival monitoring of one plan (round 22): the due/overdue/upcoming/done schedule per block, current status, and a form
// to log a new check. Only shown for plans made in blocks mode with at least one confirmed-planted block (the API says so in
// plain words otherwise - that is shown here, not hidden).
export default function SurvivalPanel({ planId, full = false }) {
  const [version, setVersion] = useState(0)
  const api = useApi(`/plans/${planId}/survival?v=${version}`)
  const [showForm, setShowForm] = useState(false)
  const rows = useMemo(() => (api.status === 'ok' ? api.data.blocks : []), [api])

  if (api.status === 'loading') return <Loading what="Loading survival monitoring" />
  if (api.status === 'error') {
    if (api.error.status === 400) {
      return (
        <p className="nw-hint" data-role="survival-unavailable">
          {api.error.message}
        </p>
      )
    }
    return <ErrorBox error={api.error} onRetry={api.retry} title="Could not load survival monitoring" brief />
  }
  if (api.status !== 'ok') return null
  const d = api.data
  const s = d.summary

  return (
    <div className="nw-survival" aria-label="Survival monitoring">
      <p className="muted">
        Periodic re-checks of what was actually planted, so this plan can show survival over time - 3 months, 6 months, 1 year, 5 years, and (as a placeholder, once there is anything to
        report) 10 and 50 years. <HelpTip label="About survival monitoring">Nothing here changes a score. A block with no check yet is shown as not yet checked, never assumed to have
        survived or died. A dead tree's check is kept forever; a replacement is logged as its own, separate check.</HelpTip>
      </p>
      <ul className="nw-counts nw-pcounts">
        <li>
          Checked: <strong>{s.points_checked}</strong> of {s.points_planned} planted blocks
        </li>
        <li>
          Survived: <strong>{s.points_survived}</strong>
        </li>
        <li>
          Dead: <strong>{s.points_dead}</strong>
        </li>
        {s.points_not_found > 0 && (
          <li>
            Not found: <strong>{s.points_not_found}</strong>
          </li>
        )}
        {s.replacement_events > 0 && (
          <li>
            Replanted after dying: <strong>{s.replacement_events}</strong>
          </li>
        )}
      </ul>
      <h4 className="nw-subhead">Overall schedule</h4>
      <Schedule rows={d.schedule_overall} />
      {!showForm ? (
        <button type="button" className="btn" onClick={() => setShowForm(true)}>
          Log a survival check
        </button>
      ) : (
        <LogForm
          planId={planId}
          blocks={d.blocks.map((b) => ({ point_id: b.point_id, species: b.species, trees_planted: b.trees_planted }))}
          onSaved={() => {
            setShowForm(false)
            setVersion((v) => v + 1)
          }}
        />
      )}
      <details className="nw-pdetails" open={full || undefined}>
        <summary>Blocks ({rows.length})</summary>
        <table className="nw-table">
          <thead>
            <tr>
              <th scope="col">Block</th>
              <th scope="col">Species</th>
              <th scope="col">Trees</th>
              <th scope="col">Latest check</th>
              <th scope="col">Next due</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => {
              const next = b.schedule.find((r) => r.state === 'due' || r.state === 'overdue') ?? b.schedule.find((r) => r.state === 'upcoming')
              return (
                <tr key={b.point_id}>
                  <th scope="row">{b.point_id}</th>
                  <td>{b.species}</td>
                  <td>{b.trees_planted}</td>
                  <td>{b.current ? `${STATUS_WORDS[b.current.status]} (${ROUND_WORDS[b.current.round_label] ?? b.current.round_label})` : 'Not yet checked'}</td>
                  <td>{next ? `${ROUND_WORDS[next.round_label]} - ${next.state === 'overdue' ? 'overdue' : formatDay(next.due_date, true)}` : '-'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </details>
    </div>
  )
}
