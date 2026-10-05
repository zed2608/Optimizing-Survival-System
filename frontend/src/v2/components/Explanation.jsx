import { CRITERION_LABEL, PART_LABEL, TERM_LABEL, flagInfo, humanize } from '../labels.js'
import { fmt, pct } from '../scale.js'
import SourceLink from './SourceLink.jsx'

// A value, or the words Data Unavailable. A missing value is never hidden.
function Val({ v, digits = 2, suffix = '' }) {
  const t = fmt(v, digits)
  return t === null ? <span className="unavailable">Data Unavailable</span> : <>{t}{suffix}</>
}

function Sources({ list }) {
  if (!list || list.length === 0) return <span className="unavailable">Data Unavailable</span>
  return (
    <ul className="plain-list">
      {list.map((s) => (
        <li key={s.source_id}>
          <SourceLink source={s} />
        </li>
      ))}
    </ul>
  )
}

function siteInput(term, point) {
  if (!point) return null
  if (term === 'elevation') return point.elev_m == null ? null : `${point.elev_m} m above sea level`
  if (term === 'slope') return point.slope_pct == null ? null : `${Number(point.slope_pct).toFixed(1)} % (from 100 m cells${point.slope_method === 'partial' ? ', one direction only, may be under-estimated' : ''})`
  if (term === 'soil') return point.soil_texture_legacy ? `${point.soil_texture_legacy} (soil map not yet verified)` : null
  return null
}

function PartValue({ value }) {
  return value === null || value === undefined ? <span className="unavailable">Data Unavailable</span> : <>{fmt(value)}</>
}

// The full explanation of one species at one place: every term and criterion with its value, weight and sources.
export default function Explanation({ item, point }) {
  const site = item.site_breakdown
  const purpose = item.purpose_breakdown
  const terms = Object.entries(site?.terms ?? {})
  const criteria = Object.entries(purpose?.criteria ?? {})
  return (
    <div className="explain">
      <p>
        <strong>Overall score W = site suitability S × purpose fitness P</strong> ({fmt(item.S)} × {fmt(item.P)} = {fmt(item.W)}). W is 0 when S is
        below 0.50. Values run from 0 (poor) to 1 (best).
      </p>

      {site?.gate_failed?.length > 0 && (
        <p className="notice">
          Hard limit exceeded for: {site.gate_failed.map((g) => (TERM_LABEL[g] ?? humanize(g)).toLowerCase()).join(', ')}. The score is 0.
        </p>
      )}

      <h4>Site suitability S (how well this place suits the species)</h4>
      <table className="breakdown">
        <caption className="sr-only">Site suitability terms for {item.common_name}</caption>
        <thead>
          <tr>
            <th scope="col">Term</th>
            <th scope="col">Value (0–1)</th>
            <th scope="col">Weight</th>
            <th scope="col">Source of the species limit</th>
          </tr>
        </thead>
        <tbody>
          {terms.map(([term, t]) => {
            const input = siteInput(term, point)
            return (
              <tr key={term}>
                <th scope="row">
                  {TERM_LABEL[term] ?? humanize(term)}
                  {input && <span className="muted block">This place: {input}</span>}
                </th>
                <td>
                  <Val v={t.value} />
                  {t.value === null && <span className="muted block">not scored: input missing</span>}
                </td>
                <td>{pct(t.weight) ?? <span className="unavailable">Data Unavailable</span>}</td>
                <td>
                  <Sources list={t.sources} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <h4>Purpose fitness P (how well the species fits the chosen purpose)</h4>
      <p className="muted">
        P = {fmt(purpose?.p_score)}. {purpose?.weights_status === 'provisional' ? 'The weights are provisional until the agriculturist signs off. ' : ''}
        {purpose?.n_missing > 0 ? `${purpose.n_missing} input(s) were missing and count as a neutral 0.5.` : ''}
      </p>
      <table className="breakdown">
        <caption className="sr-only">Purpose fitness criteria for {item.common_name}</caption>
        <thead>
          <tr>
            <th scope="col">Criterion</th>
            <th scope="col">Score (0–1)</th>
            <th scope="col">Weight</th>
            <th scope="col">Inputs and sources</th>
          </tr>
        </thead>
        <tbody>
          {criteria.map(([name, c]) => (
            <tr key={name}>
              <th scope="row">{CRITERION_LABEL[name] ?? humanize(name)}</th>
              <td>
                <Val v={c.score} />
              </td>
              <td>{pct(c.weight) ?? <span className="unavailable">Data Unavailable</span>}</td>
              <td>
                <ul className="plain-list">
                  {Object.entries(c.parts ?? {}).map(([k, v]) => (
                    <li key={k}>
                      {PART_LABEL[k] ?? humanize(k)}: <PartValue value={v} />
                    </li>
                  ))}
                </ul>
                <Sources list={c.sources} />
                {c.other_inputs?.length > 0 && (
                  <ul className="plain-list muted">
                    {c.other_inputs.map((o) => (
                      <li key={o}>Not a cited source: {o}</li>
                    ))}
                  </ul>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {item.flags?.length > 0 && (
        <>
          <h4>Notes</h4>
          <ul className="plain-list">
            {item.flags.map((f) => {
              const info = flagInfo(f)
              return (
                <li key={f}>
                  <strong>{info.label}.</strong> {info.help}
                </li>
              )
            })}
          </ul>
        </>
      )}
      <p className="muted">
        Confidence {pct(item.confidence) ?? <span className="unavailable">Data Unavailable</span>}: the share of the inputs for this place and species that could
        be checked. Source badges: Rank 1 = government agency, 2 = local academic or botanical, 3 = international reference, 4 = unranked.
      </p>
    </div>
  )
}
