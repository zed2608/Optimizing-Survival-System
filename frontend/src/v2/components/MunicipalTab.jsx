import { ErrorBox, Loading } from './Status.jsx'
import ColorLegend from './ColorLegend.jsx'
import FlagBadges from './FlagBadges.jsx'
import ScoreChip from './ScoreChip.jsx'
import SourceLink from './SourceLink.jsx'
import { MUNICIPAL_LIMIT } from '../config.js'
import { purposeLabel } from '../labels.js'
import { fmt, pct } from '../scale.js'
import { useApi } from '../useApi.js'

function SourceList({ title, ids, map }) {
  // Several fields often cite the same page: show each web page (and rank) once.
  const found = (ids ?? []).map((id) => map?.[String(id)]).filter(Boolean)
  const unique = [...new Map(found.map((src) => [`${src.url}|${src.rank}`, src])).values()]
  const missing = (ids ?? []).length > 0 && found.length === 0
  return (
    <div>
      <h4>{title}</h4>
      {unique.length === 0 || missing ? (
        <span className="unavailable">Data Unavailable</span>
      ) : (
        <ul className="plain-list">
          {unique.map((src) => (
            <li key={`${src.url}|${src.rank}`}>
              <SourceLink source={src} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// Species ranked over ALL planting-zone grid points for the chosen purpose.
export default function MunicipalTab({ purpose }) {
  const api = useApi(`/rank/municipal?purpose=${purpose}&limit=${MUNICIPAL_LIMIT}`)
  return (
    <div className="municipal">
      <h2>Whole municipality: {purposeLabel(purpose)}</h2>
      <p>
        These species are ranked over every planting-zone grid point of San Mateo. The <strong>municipal score</strong> is the average overall score
        (W) where the species is suitable × the share of planting-zone land where it is suitable, so a species that suits only a few places ranks lower.
      </p>
      <ColorLegend />
      {api.status === 'loading' && <Loading what="Ranking species for the whole municipality" />}
      {api.status === 'error' && <ErrorBox error={api.error} onRetry={api.retry} title="Could not load the municipal ranking" brief />}
      {api.status === 'ok' && (
        <div className="table-scroll">
          <table className="muni">
            <caption className="sr-only">
              Top {api.data.returned} of {api.data.species_total} species for {purposeLabel(purpose)}, over {api.data.legal_points} planting-zone grid points
            </caption>
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">Species</th>
                <th scope="col">Municipal score</th>
                <th scope="col">Average W where suitable</th>
                <th scope="col">Suitable on</th>
                <th scope="col">Purpose fitness (P)</th>
                <th scope="col">Confidence</th>
                <th scope="col">Sources</th>
              </tr>
            </thead>
            <tbody>
              {api.data.ranking.map((r) => (
                <tr key={r.species_id}>
                  <td>{r.rank}</td>
                  <th scope="row">
                    {r.common_name}
                    <FlagBadges flags={r.flags} />
                  </th>
                  <td>{fmt(r.species_score) ?? <span className="unavailable">Data Unavailable</span>}</td>
                  <td>
                    <ScoreChip w={r.mean_W_where_eligible} label="Average overall score where suitable" />
                  </td>
                  <td>
                    {pct(r.share_of_points_eligible) ?? <span className="unavailable">Data Unavailable</span>}
                    <span className="muted block">{r.eligible_points} of {api.data.legal_points} points</span>
                  </td>
                  <td>{fmt(r.P) ?? <span className="unavailable">Data Unavailable</span>}</td>
                  <td>
                    Purpose: {pct(r.p_confidence) ?? <span className="unavailable">Data Unavailable</span>}
                    <span className="block">Site: {pct(r.mean_site_confidence) ?? <span className="unavailable">Data Unavailable</span>}</span>
                  </td>
                  <td>
                    <details>
                      <summary>
                        Show sources<span className="sr-only"> for {r.common_name}</span>
                      </summary>
                      <SourceList title="Site suitability inputs" ids={r.source_ids?.site_score} map={api.data.sources} />
                      <SourceList title="Purpose fitness inputs" ids={r.source_ids?.purpose_score} map={api.data.sources} />
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
