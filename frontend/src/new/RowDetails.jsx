import { useState } from 'react'
import Explanation from '../v2/components/Explanation.jsx'
import FlagList from './FlagList.jsx'
import { pct } from '../v2/scale.js'
import SeasonBadge, { SeasonDetail } from './SeasonBadge.jsx'
import HelpTip from './HelpTip.jsx'
import Icon from './Icon.jsx'
import ProvisionalTag from './ProvisionalTag.jsx'
import { matchText, SCORE_WORDS } from './plainWords.js'
import { BEST_MONTHS_NOTE, MONTH_STRIP_NOTE } from './season.js'

// What a species row's "Details" holds: S, P, overall W, confidence, the season (12-month strip), flags and "Why this score?" (every term with its weight and source link).
// In the Full view the strip explanation is written out in place and the breakdown starts open; in Compact the same things are one tap or one "?" away.
export default function RowDetails({ item, point, full }) {
  const [why, setWhy] = useState(full)
  return (
    <>
      {!full && (
        <dl className="scores">
          <div>
            <dt>{SCORE_WORDS.W}</dt>
            <dd>{matchText(item.W)}</dd>
          </div>
          <div>
            <dt>{SCORE_WORDS.S}</dt>
            <dd>{matchText(item.S)}</dd>
          </div>
          <div>
            <dt>{SCORE_WORDS.P}</dt>
            <dd>{matchText(item.P)}</dd>
          </div>
          <div>
            <dt>Confidence</dt>
            <dd>{pct(item.confidence) ?? 'Data Unavailable'}</dd>
          </div>
        </dl>
      )}
      {full && (
      <dl className="scores" data-tour={item.rank === 1 ? 'r-scores' : undefined}>
        <div>
          <dt>Site suitability (S)</dt>
          <dd>{pct(item.S) ?? 'Data Unavailable'}</dd>
        </div>
        <div>
          <dt>Purpose fitness (P)</dt>
          <dd>{pct(item.P) ?? 'Data Unavailable'}</dd>
        </div>
        <div>
          <dt>Overall score (W)</dt>
          <dd>{pct(item.W) ?? 'Data Unavailable'}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{pct(item.confidence) ?? 'Data Unavailable'}</dd>
        </div>
      </dl>
      )}
      {full && (
        <div className="nw-opt-head">
          <span className="muted nw-grow">S, P and W are the numbers behind Site fit, Purpose fit and Overall match.</span>
          <HelpTip label="About S, P and W">S = site suitability: how well the place suits the species, shown as a percentage. P = purpose fitness: how well the species suits the goal. W = S × P, and 0 when S is below 50%. Good is 55% or more, Fair 35% or more, Poor below that.</HelpTip>
        </div>
      )}
      <SeasonBadge season={item.season} />
      {full && item.season && (
        <div className="muted">
          {MONTH_STRIP_NOTE} {BEST_MONTHS_NOTE}
        </div>
      )}
      <FlagList flags={item.flags} />
      {item.habagat && (
        <div className="nw-habagat" role="note">
          <Icon name="rain" size={14} /> Heavy rain and flooding (Habagat) can wash out seedlings here in Jul-Sep. The overall match is lowered by 20% (multiplier {item.habagat.multiplier}
          {full ? `: W ${pct(item.habagat.W_before)} becomes ${pct(item.habagat.W_after)}` : ''}). Site fit and who is suitable do not change. <ProvisionalTag />
        </div>
      )}
      {!item.eligible && <div className="muted">Not suitable here: site suitability is below 50%.</div>}
      <button type="button" className="btn btn-small" aria-expanded={why} onClick={() => setWhy((w) => !w)} data-tour={item.rank === 1 ? 'r-why-btn' : undefined}>
        {why ? 'Hide why this score' : 'Why this score?'}
        <span className="sr-only"> for {item.common_name}</span>
      </button>
      {why && (
        <div className="explain-wrap" role="region" aria-label={`Explanation for ${item.common_name}`}>
          <SeasonDetail season={item.season} />
          {item.rf && (
            <p className="nw-rfline" data-rf="yes" data-tour={item.rank === 1 ? 'r-rf' : undefined}>
              <Icon name="tree" size={14} /> {item.rf.text}
              <span className="muted"> {item.rf.note}</span>
            </p>
          )}
          <Explanation item={item} point={point} />
        </div>
      )}
    </>
  )
}
