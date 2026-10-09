import { useState } from 'react'
import Icon from './Icon.jsx'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { useApi } from '../v2/useApi.js'
import { apiPost } from './apiPost.js'
import { FIELD_ORDER, fieldColor, fieldIcon, fieldLabel } from './fieldStatus.js'

// The progress of a plan in blocks, from the saved field checks: a bar, trees planted / remaining / problem, blocks done / partly / problem / to do, trees per species, and the
// "Plan top-up" button that makes a new plan for the trees lost to problem blocks. version changes after every saved field check, so the numbers reload.
export default function PlanProgress({ planId, version = 0, full = false, onTopUp, onOpenPlan }) {
  const api = useApi(`/plans/${planId}/progress?v=${version}`)
  const [also, setAlso] = useState(false)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState('')

  if (api.status === 'loading') return <Loading what="Loading the progress" />
  if (api.status === 'error') return api.error.status === 400 ? null : <ErrorBox error={api.error} onRetry={api.retry} title="Could not load the progress" brief />
  if (api.status !== 'ok') return null
  const p = api.data
  const t = p.trees
  const b = p.blocks
  const lost = p.shortfall.trees
  const canTop = lost > 0 || (also && t.remaining > 0)

  async function topUp() {
    setBusy(true)
    setProblem('')
    try {
      const r = await apiPost(`/plans/${planId}/top-up`, { include_remaining: also })
      onTopUp(r)
    } catch (e) {
      setProblem(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="nw-progress" aria-label="Progress">
      <div className="nw-pbar" role="progressbar" aria-label="Trees planted" aria-valuemin={0} aria-valuemax={t.planned} aria-valuenow={t.planted} aria-valuetext={`${t.planted} of ${t.planned} trees planted`}>
        <span style={{ width: `${Math.min(100, t.percent_planted)}%` }} />
      </div>
      <div className="nw-pnum">
        <strong>{t.planted}</strong> of {t.planned} trees planted ({t.percent_planted}%)
      </div>
      <ul className="nw-counts nw-pcounts">
        <li style={{ color: fieldColor('planted') }}>
          <Icon name={fieldIcon('planted')} /> Planted: <strong>{t.planted}</strong>
        </li>
        <li>
          <Icon name="clock" /> Remaining: <strong>{t.remaining}</strong>
        </li>
        <li style={{ color: fieldColor('not_plantable') }}>
          <Icon name={fieldIcon('not_plantable')} /> Problem: <strong>{t.problem}</strong>
        </li>
      </ul>
      {t.problem > 0 && p.by_class && (
        <ul className="nw-counts nw-pcounts nw-problemclasses" aria-label="Problem blocks by reason">
          {FIELD_ORDER.filter((k) => ['not_plantable', 'water', 'hard'].includes(k) && p.by_class[k]?.blocks > 0).map((k) => (
            <li key={k} style={{ color: fieldColor(k) }}>
              <Icon name={fieldIcon(k)} /> {fieldLabel(k)}: <strong>{p.by_class[k].blocks}</strong> block{p.by_class[k].blocks === 1 ? '' : 's'}
            </li>
          ))}
        </ul>
      )}
      <div className="nw-loc-line">
        Blocks: {b.done} done · {b.partly} partly done · {b.problem} problem · {b.to_do} to do (of {b.total})
      </div>
      {p.parent_plan_id && (
        <div className="nw-loc-line">
          Top-up of{' '}
          <button type="button" className="fc-link" onClick={() => onOpenPlan?.(p.parent_plan_id)}>
            {p.parent_plan_id}
          </button>
        </div>
      )}
      {p.child_plan_ids.length > 0 && (
        <div className="nw-loc-line">
          Top-ups:{' '}
          {p.child_plan_ids.map((id) => (
            <button key={id} type="button" className="fc-link" onClick={() => onOpenPlan?.(id)}>
              {id}
            </button>
          ))}
        </div>
      )}
      <details className="nw-pdetails" open={full || undefined}>
        <summary>Trees per species</summary>
        <table className="nw-table">
          <thead>
            <tr>
              <th scope="col">Species</th>
              <th scope="col">Planted</th>
              <th scope="col">Planned</th>
              <th scope="col">Problem</th>
            </tr>
          </thead>
          <tbody>
            {p.per_species.map((e) => (
              <tr key={e.species_id}>
                <th scope="row">{e.species}</th>
                <td>{e.planted}</td>
                <td>{e.planned}</td>
                <td>{e.problem_trees}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
      <div className="nw-topup">
        <label className="nw-check">
          <input type="checkbox" checked={also} onChange={(e) => setAlso(e.target.checked)} /> Also plan the trees not planted yet
        </label>
        <button type="button" className="btn" disabled={!canTop || busy} onClick={topUp}>
          {busy ? 'Planning…' : 'Plan top-up'}
        </button>
        <p className="nw-hint" role="status">
          {lost > 0 ? `${lost} trees were lost to problem blocks.` : also && t.remaining > 0 ? `${t.remaining} trees are not planted yet.` : 'No block is marked as a problem, so there is nothing to top up.'}
        </p>
        {problem && (
          <p className="fc-bad" role="alert">
            {problem}
          </p>
        )}
      </div>
    </div>
  )
}
