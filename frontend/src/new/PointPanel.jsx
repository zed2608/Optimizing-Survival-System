import { useState } from 'react'
import Icon from './Icon.jsx'
import { ErrorBox, Loading } from '../v2/components/Status.jsx'
import ColorLegend from '../v2/components/ColorLegend.jsx'
import ScoreChip from '../v2/components/ScoreChip.jsx'
import MatchChip from './MatchChip.jsx'
import { matchLevel, verdictSentence } from './plainWords.js'
import { wLevel } from '../v2/scale.js'
import { friendlyNotRankable, purposeLabel } from '../v2/labels.js'
import BlockLayout from './BlockLayout.jsx'
import ChosenHere from './ChosenHere.jsx'
import HelpTip from './HelpTip.jsx'
import LocationCard from './LocationCard.jsx'
import RowDetails from './RowDetails.jsx'
import SeasonBadge from './SeasonBadge.jsx'
import { BEST_MONTHS_NOTE } from './season.js'
import VerifyBar from './VerifyBar.jsx'
import ViableSuggestion from './ViableSuggestion.jsx'
import ViewSwitch from './ViewSwitch.jsx'
import WhyNone from './WhyNone.jsx'

// One species of the compact list: rank, name (opens the species card), score chip, short season badge, and ONE "Details" disclosure
// (open from the start in the Full view).
function ResultRow({ item, point, onInfo, full }) {
  return (
    <li className={`nw-prow level-${wLevel(item.W, item.eligible)}`}>
      <div className="nw-prow-main">
        <span className="rank-no" aria-label={`Rank ${item.rank}`}>
          {item.rank}
        </span>
        <button type="button" className="nw-namebtn nw-prow-name" onClick={() => onInfo(item.species_id)}>
          {item.common_name}
          <span className="sr-only"> (species information)</span>
        </button>
        {full ? <ScoreChip w={item.W} eligible={item.eligible} /> : <MatchChip w={item.W} eligible={item.eligible} />}
        <SeasonBadge season={item.season} strip={false} best={false} />
      </div>
      <details className="nw-pdetails" open={full || undefined}>
        <summary>
          Details<span className="sr-only"> for {item.common_name}</span>
        </summary>
        <RowDetails item={item} point={point} full={full} />
      </details>
    </li>
  )
}

// The verdict of the spot in one sentence: "Good place for Kamagong: overall match 77%. In its planting months. Check the ground first."
function VerdictCard({ ranking, leftOut, preferId = null }) {
  const top = (preferId !== null ? ranking.find((r) => r.species_id === preferId && r.eligible) : null) ?? ranking.find((r) => r.eligible) ?? null
  const text = leftOut ? 'This spot was marked not plantable in the field, so it is left out of plans.' : verdictSentence(top, top?.flags ?? [])
  const good = !leftOut && top && matchLevel(top.W) === 'Good'
  return (
    <section className={`nw-pcard nw-verdictcard ${good ? 'is-good' : top && !leftOut ? 'is-fair' : 'is-poor'}`} aria-label="Verdict for this spot">
      <p className="nw-verdict-text" role="status">
        <Icon name={good ? 'check' : top && !leftOut ? 'info' : 'warn'} /> {text}
      </p>
    </section>
  )
}

// The point panel: 1 where this is (header card), 2 the field check card, 3 (goal "I have species") your chosen species here, 4 the best species as a compact list.
export default function PointPanel({
  rank, purpose, win, today, barangay, searched, pointId, fieldApi, observer, onObserver, onSaved, viable, onFindViable, onGo, seasonNote, onInfo,
  view, onView, chosen, selIds, combine, onlySeason, planBlock = null,
}) {
  const [show, setShow] = useState(5)
  const full = view === 'full'

  if (rank.status === 'idle') {
    return (
      <div className="nw-ppanel">
        <section className="nw-pcard">
          <h3>Start here</h3>
          <p className="nw-plain">Click a place on the map, or search for it.</p>
        </section>
      </div>
    )
  }
  if (rank.status === 'loading') return <div className="nw-ppanel"><section className="nw-pcard"><Loading what="Ranking species for this spot" /></section></div>
  if (rank.status === 'error') {
    if (rank.error.status === 404) {
      const f = friendlyNotRankable(rank.error.message)
      return (
        <div className="nw-ppanel">
          <section className="nw-pcard">
            {searched && <div className="nw-loc-searched">Searched: {searched}</div>}
            <h3>{f.title}</h3>
            <p className="nw-plain">{f.text}</p>
            <button type="button" className="btn" onClick={onFindViable} disabled={viable.status === 'loading'}>
              Find the nearest suitable spot
            </button>
            <ViableSuggestion status={viable} onGo={onGo} />
          </section>
        </div>
      )
    }
    return <div className="nw-ppanel"><section className="nw-pcard"><ErrorBox error={rank.error} onRetry={rank.retry} title="Could not rank the species" brief /></section></div>
  }

  const { point, ranking } = rank.data
  const leftOut = rank.data.left_out_by_field_check
  const shown = ranking.slice(0, show)
  return (
    <div className="nw-ppanel">
      <ViewSwitch value={view} onChange={onView} />
      <VerdictCard ranking={ranking} leftOut={leftOut} preferId={planBlock ? planBlock.item.species_id : null} />
      <LocationCard full={full} soil={point.soil ?? null} ground={point.ground_cover} zoning={point.zoning_status ?? (point.zone ? 'confirmed' : null)} barangay={barangay} zone={point.zone} pointId={point.point_id} lat={point.lat} lon={point.lon} elev={point.elev_m} slope={point.slope_pct} win={win} today={today} distance={point.distance_m} searched={searched} />
      {planBlock && (
        <section className="nw-pcard nw-blockcard" aria-label="Planting block">
          <div className="nw-pcard-head">
            <h3>Planting block {planBlock.item.block_ref}</h3>
            <HelpTip label="About blocks">A block is one 100 m grid square planted at the species spacing. Walk to the centre, start at the south-west corner of the planted part and plant the rows east to west.</HelpTip>
          </div>
          <div className="nw-loc-line">
            {planBlock.item.species} · {planBlock.item.trees_planned} trees · plan {planBlock.planId}
          </div>
          <BlockLayout item={planBlock.item} kind={planBlock.kind} />
        </section>
      )}
      {pointId ? (
        <VerifyBar
          key={`${pointId}|${planBlock?.planId ?? ''}`}
          pointId={pointId}
          api={fieldApi}
          observer={observer}
          onObserver={onObserver}
          onSaved={onSaved}
          block={planBlock ? { planId: planBlock.planId, trees: planBlock.item.trees_planned, ref: planBlock.item.block_ref } : null}
        />
      ) : null}
      {chosen && selIds.length > 0 && <ChosenHere api={chosen} selIds={selIds} combine={combine} onlySeason={onlySeason} full={full} point={point} onInfo={onInfo} />}

      {rank.data.limiting_factors && <WhyNone lf={rank.data.limiting_factors} ground={point.ground_cover} />}

      <section className="nw-pcard" aria-label="Best species for this spot">
        <div className="nw-pcard-head">
          <h3>Best species for this spot</h3>
          <HelpTip label="About this list">
            <div>Each point stands for a 100 m × 100 m square. Colours: green good, orange moderate, red poor, grey not suitable.</div>
            <ColorLegend />
            <div>Month strip: filled = planting months, ringed = your dates. {BEST_MONTHS_NOTE}</div>
          </HelpTip>
        </div>
        <div className="nw-count-line">
          {rank.data.species_eligible} of {rank.data.species_total} suitable · {purposeLabel(purpose)}
        </div>
        {full && (
          <div className="nw-fullnote">
            <div className="muted">Each point stands for a 100 m × 100 m square. Colours: green good, orange moderate, red poor, grey not suitable.</div>
            <ColorLegend />
          </div>
        )}
        {ranking.length === 0 && seasonNote}
        {leftOut && (
          <p className="notice" role="status">
            <Icon name="close" /> Left out of plans because of a field check.
          </p>
        )}
        <ol className={`nw-plist ${leftOut ? 'is-greyed' : ''}`} aria-label={`Best species for ${purposeLabel(purpose)}`}>
          {shown.map((item) => (
            <ResultRow key={`${item.species_id}|${full}`} item={item} point={point} onInfo={onInfo} full={full} />
          ))}
        </ol>
        {ranking.length > 5 && (
          <div className="nw-more-row" role="group" aria-label="How many species to show">
            <button type="button" className="btn btn-small" aria-pressed={show === 10} onClick={() => setShow((s) => (s === 10 ? 5 : 10))}>
              {show === 10 ? 'Show 5' : 'Show 10'}
            </button>
            {ranking.length > 10 && (
              <button type="button" className="btn btn-small" aria-pressed={show > 10} onClick={() => setShow((s) => (s > 10 ? 5 : 100))}>
                {show > 10 ? 'Show 5' : 'Show all'}
              </button>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
