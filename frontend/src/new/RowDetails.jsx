import { useState } from 'react'
import Explanation from '../v2/components/Explanation.jsx'
import FlagList from './FlagList.jsx'
import { fmt, pct } from '../v2/scale.js'
import SeasonBadge, { SeasonDetail } from './SeasonBadge.jsx'
import { BEST_MONTHS_NOTE } from './season.js'

// What a species row's "Details" holds: S, P, overall W, confidence, the season (12-month strip), flags and "Why this score?" (every term with its weight and source link).
// In the Full view the strip explanation is written out in place and the breakdown starts open; in Compact the same things are one tap or one "?" away.
export default function RowDetails({ item, point, full }) {
  const [why, setWhy] = useState(full)
  return (
    <>
      <dl className="scores">
        <div>
          <dt>Site suitability (S)</dt>
          <dd>{fmt(item.S) ?? 'Data Unavailable'}</dd>
        </div>
        <div>
          <dt>Purpose fitness (P)</dt>
          <dd>{fmt(item.P) ?? 'Data Unavailable'}</dd>
        </div>
        <div>
          <dt>Overall score (W)</dt>
          <dd>{fmt(item.W) ?? 'Data Unavailable'}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{pct(item.confidence) ?? 'Data Unavailable'}</dd>
        </div>
      </dl>
      <SeasonBadge season={item.season} />
      {full && item.season && (
        <div className="muted">
          Month strip: filled = planting months, ringed = your dates. {BEST_MONTHS_NOTE}
        </div>
      )}
      <FlagList flags={item.flags} />
      {!item.eligible && <div className="muted">Not suitable here: site suitability is below 0.50.</div>}
      <button type="button" className="btn btn-small" aria-expanded={why} onClick={() => setWhy((w) => !w)}>
        {why ? 'Hide why this score' : 'Why this score?'}
        <span className="sr-only"> for {item.common_name}</span>
      </button>
      {why && (
        <div className="explain-wrap" role="region" aria-label={`Explanation for ${item.common_name}`}>
          <SeasonDetail season={item.season} />
          <Explanation item={item} point={point} />
        </div>
      )}
    </>
  )
}
