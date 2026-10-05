import Explanation from './Explanation.jsx'
import FlagBadges from './FlagBadges.jsx'
import ScoreChip from './ScoreChip.jsx'
import { fmt, pct, wLevel } from '../scale.js'

// One species in the ranking: name, scores, flags and an accordion button for the explanation.
export default function SpeciesRow({ item, point, open, onToggle }) {
  const panelId = `explain-${item.species_id}`
  return (
    <li className={`species level-${wLevel(item.W, item.eligible)}`}>
      <div className="species-head">
        <span className="rank-no" aria-label={`Rank ${item.rank}`}>
          {item.rank}
        </span>
        <div className="species-main">
          <h3 className="species-name">{item.common_name}</h3>
          <ScoreChip w={item.W} eligible={item.eligible} />
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
              <dt>Confidence</dt>
              <dd>{pct(item.confidence) ?? 'Data Unavailable'}</dd>
            </div>
          </dl>
          <FlagBadges flags={item.flags} />
          {!item.eligible && <p className="muted">Not suitable here: site suitability is below 0.50, so the overall score is 0.</p>}
        </div>
        <button type="button" className="btn btn-small" aria-expanded={open} aria-controls={panelId} onClick={onToggle}>
          {open ? 'Hide explanation' : 'Why this score?'}
          <span className="sr-only"> for {item.common_name}</span>
        </button>
      </div>
      {open && (
        <div id={panelId} className="explain-wrap" role="region" aria-label={`Explanation for ${item.common_name}`}>
          <Explanation item={item} point={point} />
        </div>
      )}
    </li>
  )
}
