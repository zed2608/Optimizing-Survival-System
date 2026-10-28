import { useState } from 'react'
import HelpTip from './HelpTip.jsx'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import { useApi } from '../v2/useApi.js'
import { formatDay } from './season.js'
import { LogForm, Schedule, STATUS_WORDS, CAUSE_WORDS, ROUND_WORDS } from './SurvivalPanel.jsx'

const FIELD_STATUS_WORDS = { verified_plantable: 'Confirmed plantable', not_plantable: 'Marked not plantable', needs_recheck: 'Needs a recheck', planted: 'Planted' }

// One planting event's full field-check entry: who logged it, when, and what they saw - this is the "who planted and other
// details" the field check already carries (round 10a onward), just shown here per point instead of only inside a plan.
function FieldEvent({ ev }) {
  return (
    <li>
      <strong>{FIELD_STATUS_WORDS[ev.status] ?? ev.status}</strong>
      {ev.status === 'planted' && ev.trees_planted != null ? ` - ${ev.trees_planted} trees` : ''}
      {' · '}{formatDay(ev.observed_at, true)} · {ev.observer || 'no name given'}
      {ev.reason ? ` · ${ev.reason}` : ''}
      {ev.note ? <span className="muted"> - {ev.note}</span> : null}
    </li>
  )
}

function SurvivalEvent({ ev }) {
  return (
    <li>
      <strong>{STATUS_WORDS[ev.status] ?? ev.status}</strong>
      {` (${ROUND_WORDS[ev.round_label] ?? ev.round_label})`}
      {ev.status !== 'not_found' ? ` - ${ev.trees_alive} of ${ev.trees_total} alive` : ''}
      {ev.cause ? ` · ${CAUSE_WORDS[ev.cause] ?? ev.cause}` : ''}
      {' · '}{formatDay(ev.observed_at, true)} · {ev.observer || 'no name given'}
      {ev.note ? <span className="muted"> - {ev.note}</span> : null}
    </li>
  )
}

function Planting({ p, onLogged }) {
  const [logging, setLogging] = useState(false)
  return (
    <div className="nw-pcard nw-planting">
      <div className="nw-pcard-head">
        <h4 className="nw-subhead">
          {p.species} - {p.trees_planted} trees
        </h4>
        <HelpTip label="About this planting">From plan {p.plan_id}{p.campaign.name ? ` ("${p.campaign.name}")` : ''}. Planted {formatDay(p.planted_observed_at, true)} by {p.planted_by || 'no name given'}.</HelpTip>
      </div>
      <p className="nw-loc-line">
        Planted {formatDay(p.planted_observed_at, true)} by <strong>{p.planted_by || 'no name given'}</strong>
        {p.planted_note ? <span className="muted"> - {p.planted_note}</span> : null}
      </p>
      <h5 className="nw-subhead">Survival schedule</h5>
      <Schedule rows={p.survival_schedule} />
      {p.survival_history.length > 0 && (
        <>
          <h5 className="nw-subhead">Survival checks ({p.survival_history.length})</h5>
          <ul className="nw-counts nw-pcounts">
            {p.survival_history.map((ev) => (
              <SurvivalEvent key={ev.check_id} ev={ev} />
            ))}
          </ul>
        </>
      )}
      {!logging ? (
        <button type="button" className="btn btn-small" onClick={() => setLogging(true)}>
          Log a survival check
        </button>
      ) : (
        <LogForm
          planId={p.plan_id}
          blocks={[{ point_id: p.point_id, species: p.species, trees_planted: p.trees_planted }]}
          onSaved={() => {
            setLogging(false)
            onLogged()
          }}
        />
      )}
    </div>
  )
}

// The map's own "who planted this, and how is it doing" card: reachable by clicking ANY planted (or not-plantable) point,
// whether or not that point belongs to the plan presently open. Backed by GET /points/{point_id}/history, which looks across
// every plan that ever confirmed planting this point - not just the one on screen.
export default function PlantingHistoryCard({ pointId }) {
  const api = useApi(pointId != null ? `/points/${pointId}/history` : null)
  if (api.status === 'idle' || api.status === 'loading') return <Loading what="Loading this point's history" />
  if (api.status === 'error') return <ErrorBox error={api.error} onRetry={api.retry} title="Could not load this point's history" brief />
  const d = api.data
  if (!d.current && d.plantings.length === 0) return null // never checked, never planted: nothing to show, never guessed

  return (
    <section className="nw-pcard nw-history" aria-label="Planting and survival history for this point">
      <div className="nw-pcard-head">
        <h3>Planting and survival history</h3>
        <HelpTip label="About this history">Everything on record for this exact 100 m square: every field check (who looked at it and when, including who marked it planted), and, for each planting, its own survival-check schedule and history. A square never checked shows nothing here - nothing is assumed.</HelpTip>
      </div>
      {d.field_history.length > 0 && (
        <details className="nw-pdetails">
          <summary>
            Field-check history ({d.field_history.length}){d.current ? ` - currently: ${FIELD_STATUS_WORDS[d.current.status] ?? d.current.status}` : ''}
          </summary>
          <ul className="nw-counts nw-pcounts">
            {d.field_history.map((ev) => (
              <FieldEvent key={ev.check_id} ev={ev} />
            ))}
          </ul>
        </details>
      )}
      {d.plantings.length === 0 ? (
        <p className="nw-plain">This point has not been confirmed planted in any saved plan yet.</p>
      ) : (
        d.plantings.map((p) => <Planting key={p.plan_id} p={{ ...p, point_id: d.point_id }} onLogged={api.retry} />)
      )}
    </section>
  )
}
