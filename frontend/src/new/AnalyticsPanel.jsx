import { useApi } from '../v2/useApi.js'
import Icon from './Icon.jsx'

function Counter({ title, value, label, extra, status }) {
  return (
    <section className="v2 v2-embedded nw-counter" aria-label={title}>
      <h3>{title}</h3>
      <div className="nw-counter-num">{status === 'loading' ? '…' : value}</div>
      <p className="nw-plain">{label}</p>
      {extra}
    </section>
  )
}

const n = (v) => (typeof v === 'number' ? v.toLocaleString('en-US') : 'Data Unavailable')

// The "System Analytics" tab: small counter cards, all from the planning service. A card whose service is not reachable says so instead of showing a number.
export default function AnalyticsPanel({ includeUnzoned = true }) {
  const uz = `include_unzoned=${includeUnzoned}`
  const health = useApi(`/health?${uz}`)
  const ctx = useApi(`/grid/context?${uz}`)
  const field = useApi('/field-checks/summary')
  const plans = useApi('/plans?limit=100')
  const ok = (a) => a.status === 'ok'
  const down = (a) => (a.status === 'error' ? 'Not available (the planning service is not reachable)' : null)
  const placed = ok(plans) ? plans.data.plans.reduce((a, p) => a + (p.n_placed ?? 0), 0) : null
  const kits = ok(plans) ? plans.data.plans.filter((p) => p.field_kit_built).length : null
  const partial = ok(plans) && plans.data.total_saved > plans.data.plans.length
  const f = ok(field) ? field.data : null
  return (
    <div className="nw-counters">
      <Counter
        title="Map squares"
        value={ok(ctx) ? n(ctx.data.total_points) : down(ctx) ?? '…'}
        status={ctx.status}
        label={ok(ctx) ? `${n(ctx.data.legal_points)} planting squares + ${n(ctx.data.n)} other squares. Each square is about 100 m.` : 'Every 100 m square of the map.'}
        extra={ok(ctx) && !includeUnzoned && <p className="nw-plain">Land outside the zoning map is left out (switched off in step 4).</p>}
      />
      <Counter
        title="Field checks"
        value={f ? n(f.points_checked) : down(field) ?? '…'}
        status={field.status}
        label="Points that a person has checked on the ground."
        extra={
          f && (
            <ul className="nw-counter-list">
              <li><Icon name="ring" /> Verified plantable: <strong>{n(f.by_status.verified_plantable)}</strong></li>
              <li><Icon name="close" /> Not plantable: <strong>{n(f.by_status.not_plantable)}</strong></li>
              <li><Icon name="triangle" /> Needs recheck: <strong>{n(f.by_status.needs_recheck)}</strong></li>
              <li><Icon name="warn" /> Disputed: <strong>{n(f.disputed_points)}</strong></li>
            </ul>
          )
        }
      />
      <Counter title="Saved plans" value={ok(plans) ? n(plans.data.total_saved) : down(plans) ?? '…'} status={plans.status} label="Planting plans saved so far." />
      <Counter title="Trees planned" value={ok(plans) ? n(placed) : down(plans) ?? '…'} status={plans.status} label={partial ? 'Trees placed in the newest 100 saved plans.' : 'Trees placed in all saved plans.'} />
      <Counter title="Field kits built" value={ok(plans) ? n(kits) : down(plans) ?? '…'} status={plans.status} label={partial ? 'Plans with a kit among the newest 100.' : 'Plans that have a field kit.'} />
      <Counter
        title="Dataset"
        value={ok(health) ? (health.data.dataset_version ?? 'Data Unavailable') : down(health) ?? '…'}
        status={health.status}
        label={ok(health) ? `${n(health.data.counts.species)} species. Draft data: weights are provisional.` : 'The version of the species data.'}
        extra={ok(health) && <div className="nw-mono nw-counter-hash">hash {health.data.dataset_file_hash ?? 'Data Unavailable'}</div>}
      />
    </div>
  )
}
