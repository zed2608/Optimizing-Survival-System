import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import ScoreChip from '../v2/components/ScoreChip.jsx'
import { fmt, pct } from '../v2/scale.js'

const MARKER = -1 // the API's documented "no value" marker

function AreaTable({ title, kind, api, activeKey, onSelect, onPlan }) {
  if (api.status === 'loading') return <Loading what={`Ranking the ${title.toLowerCase()}`} />
  if (api.status === 'error') return <ErrorBox error={api.error} onRetry={api.retry} title={`Could not rank the ${title.toLowerCase()}`} brief />
  if (api.status !== 'ok') return null
  const rows = api.data.areas
  return (
    <section className="nw-areatable">
      <h3>{title}</h3>
      <table className="nw-table">
        <caption className="sr-only">
          {title} ranked by mean score W for the selected species ({api.data.mode === 'all' ? 'must suit all' : 'suits at least one'})
        </caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">{kind === 'barangay' ? 'Barangay' : 'Zone'}</th>
            <th scope="col">Mean W</th>
            <th scope="col">Suitable on</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className={activeKey === `${kind}|${r.name}` ? 'is-active' : ''}>
              <td>{r.rank}</td>
              <th scope="row">
                <button type="button" className="nw-rowbtn" aria-pressed={activeKey === `${kind}|${r.name}`} onClick={() => onSelect(kind, r)}>
                  {r.display_name}
                  <span className="sr-only"> (zoom to this area on the map)</span>
                </button>
                <button type="button" className="nw-plan" onClick={() => onPlan(kind, r)}>
                  Plan here
                </button>
              </th>
              <td>
                <ScoreChip w={r.mean_W} eligible={r.suitable_points > 0} label="Mean score W over the area" />
                <span className="nw-sub">
                  where suitable: {r.mean_W_where_suitable === MARKER ? <span className="unavailable">Data Unavailable</span> : fmt(r.mean_W_where_suitable)}
                </span>
              </td>
              <td>
                <strong>{pct(r.share_suitable)}</strong>
                <span className="nw-sub">
                  {r.suitable_points} of {r.legal_points} points
                </span>
                {r.not_plantable_points > 0 && <span className="nw-sub">✕ {r.not_plantable_points} not plantable (left out)</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

// Mode 1: barangays AND zones ranked for the selected species. Clicking a name zooms the map to it and highlights it.
export default function AreasPanel({ speciesNames, combine, onCombine, byBarangay, byZone, activeKey, onSelect, onPlan, seasonNote, allRemoved }) {
  const none = !allRemoved && byBarangay.status === 'ok' && byBarangay.data.areas.every((r) => r.suitable_points === 0)
  return (
    <div className="v2 v2-embedded nw-areas">
      <div className="panel-body">
        <h2>Where do they grow?</h2>
        <p className="muted">
          {speciesNames.length === 1 ? speciesNames[0] : `${speciesNames.length} species`} · {combine === 'all' ? 'must suit all selected' : 'suits at least one'}.
          Mean W is the average score over all planting-zone points of the area (0 where a point is not suitable). Click a name to zoom to it.
        </p>
        {seasonNote}
        {none && (
          <div className="notice" role="status">
            <strong>{combine === 'all' ? 'No suitable area for all selected species.' : 'None of the selected species is suitable anywhere for this purpose.'}</strong>
            {combine === 'all' && (
              <>
                <p>Try “Suits at least one”, or select fewer species.</p>
                <button type="button" className="btn btn-small" onClick={() => onCombine('any')}>
                  Switch to “Suits at least one”
                </button>
              </>
            )}
          </div>
        )}
        <AreaTable title="Barangays" kind="barangay" api={byBarangay} activeKey={activeKey} onSelect={onSelect} onPlan={onPlan} />
        <AreaTable title="Zones" kind="zone" api={byZone} activeKey={activeKey} onSelect={onSelect} onPlan={onPlan} />
      </div>
    </div>
  )
}
