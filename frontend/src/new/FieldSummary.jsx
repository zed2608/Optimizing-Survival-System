import { useRef, useState } from 'react'
import { API_BASE } from '../v2/config.js'
import { REASON_LABEL, STATUS_LABEL, STATUS_SYMBOL } from './fieldLabels.js'
import { apiPostText } from './apiPost.js'
import HelpTip from './HelpTip.jsx'

// Inside the "More" menu: counts of the saved field checks, Download (CSV) and Import (CSV) with the accepted / rejected report.
export default function FieldSummary({ summary, observer, onObserver, onChanged }) {
  const fileRef = useRef(null)
  const [report, setReport] = useState(null)
  const [problem, setProblem] = useState('')
  const [busy, setBusy] = useState(false)
  const s = summary.status === 'ok' ? summary.data : null

  async function onFile(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setReport(null)
    setProblem('')
    if (observer.trim() === '') return setProblem('Please type your name first: it is saved with the imported checks.')
    setBusy(true)
    try {
      const text = await file.text()
      const r = await apiPostText(`/field-checks/import?observer=${encodeURIComponent(observer.trim())}`, text)
      setReport(r)
      if (r.accepted > 0) onChanged()
    } catch (err) {
      setProblem(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div aria-label="Field checks">
      {summary.status === 'loading' && <p className="nw-hint">Loading…</p>}
      {summary.status === 'error' && <p className="nw-hint nw-warn">Field checks are not available (the planning service is not reachable).</p>}
      {s && (
        <>
          <ul className="nw-counts">
            {['verified_plantable', 'not_plantable', 'needs_recheck'].map((k) => (
              <li key={k}>
                <span aria-hidden="true">{STATUS_SYMBOL[k]}</span> {STATUS_LABEL[k]}: <strong>{s.by_status[k]}</strong>
              </li>
            ))}
          </ul>
          <p className="nw-hint">
            {s.points_checked} point{s.points_checked === 1 ? '' : 's'} checked
            {s.disputed_points > 0 ? ` · ⚠ ${s.disputed_points} disputed` : ''}
            {s.exclude_not_plantable ? ` · ${s.left_out_of_rankings} left out` : ' · exclusion is off'}.
          </p>
          {s.by_status.not_plantable > 0 && (
            <p className="nw-hint">
              Not plantable:{' '}
              {Object.entries(s.by_reason)
                .filter(([, n]) => n > 0)
                .map(([r, n]) => `${REASON_LABEL[r] ?? r} ${n}`)
                .join(', ')}
            </p>
          )}
        </>
      )}
      <label className="nw-label nw-label-gap" htmlFor="nw-fc-observer">
        Your name
      </label>
      <input id="nw-fc-observer" className="nw-input" value={observer} maxLength={80} onChange={(e) => onObserver(e.target.value)} placeholder="e.g. Juan Dela Cruz" />
      <div className="nw-opt-head">
        <div className="nw-row nw-grow">
          <a className="nw-btn nw-btn-small nw-linkbtn" href={`${API_BASE}/field-checks/export.csv`} download="field_checks.csv">
            Download (CSV)
          </a>
          <button type="button" className="nw-btn nw-btn-small" disabled={busy} onClick={() => fileRef.current?.click()}>
            Import field checks (CSV)
          </button>
        </div>
        <HelpTip label="Import field checks">
          Import the point-list.csv of a field kit after the team filled in its status and moved_lat / moved_lon columns. Your name is saved in this browser and with each imported check. Importing the same file again adds
          nothing.
        </HelpTip>
      </div>
      <input ref={fileRef} type="file" accept=".csv,text/csv" className="sr-only" tabIndex={-1} onChange={onFile} aria-label="Choose the filled point-list.csv of a field kit" />
      {busy && <p className="nw-hint" role="status">Importing…</p>}
      {problem && (
        <p className="nw-hint nw-warn" role="alert">
          {problem}
        </p>
      )}
      {report && (
        <div className="nw-report" role="status">
          <strong>Import report</strong> (plan {report.plan_id})
          <div>
            Accepted <strong>{report.accepted}</strong> · Rejected <strong>{report.rejected}</strong> · Already imported <strong>{report.duplicates}</strong> · Not filled in{' '}
            <strong>{report.blank}</strong>
          </div>
          {report.rows.filter((r) => r.outcome === 'rejected').length > 0 && (
            <ul>
              {report.rows
                .filter((r) => r.outcome === 'rejected')
                .slice(0, 15)
                .map((r) => (
                  <li key={r.line}>
                    Line {r.line} ({r.point_ref || r.point_id}): {r.reason}
                  </li>
                ))}
            </ul>
          )}
          <button type="button" className="nw-btn nw-btn-small" onClick={() => setReport(null)}>
            Close report
          </button>
        </div>
      )}
    </div>
  )
}
