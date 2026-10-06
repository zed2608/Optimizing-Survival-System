import HelpTip from './HelpTip.jsx'
import SeasonNotice from './SeasonNotice.jsx'

const PRESETS = [50, 100, 300, 500]

// Step 5 "Plan": campaign name, assigned unit, number of saplings, a compact summary of what the plan will use, the capacity message, and the one primary button.
export default function PlanStep({
  name, onName, unit, onUnit, n, onN, nValid, areaLabel, modeLabel, windowText, preview, reason, onCreate, creating, createError, result, onAnother, seasonNoticeProps,
}) {
  const p = preview.status === 'ok' ? preview.data : null
  const placed = result?.summary?.saplings_placed
  const requested = result?.summary?.n_saplings_requested
  const sm = result?.summary
  return (
    <div>
      <div className="nw-opt-head">
        <label className="nw-label nw-grow" htmlFor="nw-campaign-name">
          Campaign name
        </label>
        <HelpTip label="Campaign name">The name of the planting event, saved with the plan.</HelpTip>
      </div>
      <input id="nw-campaign-name" className="nw-input" value={name} maxLength={80} onChange={(e) => onName(e.target.value)} placeholder="e.g. Brgy. Santa Ana Tree Day" aria-required="true" />
      <label className="nw-label" htmlFor="nw-campaign-unit">
        Assigned unit
      </label>
      <input id="nw-campaign-unit" className="nw-input" value={unit} maxLength={80} onChange={(e) => onUnit(e.target.value)} placeholder="e.g. MENRO field team" />
      <div className="nw-opt-head">
        <label className="nw-label nw-grow" htmlFor="nw-saplings">
          Number of saplings
        </label>
        <HelpTip label="Number of saplings">How many trees to plan, from 1 to 2000.</HelpTip>
      </div>
      <input id="nw-saplings" type="number" min="1" max="2000" className="nw-input" value={n} onChange={(e) => onN(e.target.value)} aria-invalid={!nValid} />
      <div className="nw-presets" role="group" aria-label="Sapling presets">
        {PRESETS.map((v) => (
          <button key={v} type="button" className={`nw-btn nw-btn-small ${String(n) === String(v) ? 'nw-btn-go' : ''}`} onClick={() => onN(String(v))}>
            {v}
          </button>
        ))}
      </div>
      {!nValid && (
        <p className="nw-error" role="alert">
          Saplings: 1 to 2000.
        </p>
      )}

      <dl className="nw-plansum" aria-label="What the plan will use">
        <div>
          <dt>Area</dt>
          <dd>
            {areaLabel || 'Not chosen'}
            {p ? ` · ${p.area.suitable_squares} suitable squares available` : ''}
          </dd>
        </div>
        <div>
          <dt>Dates</dt>
          <dd>{windowText}</dd>
        </div>
        <div>
          <dt>Species</dt>
          <dd>{modeLabel}</dd>
        </div>
      </dl>

      {p && p.capacity.message && (
        <p className="nw-capacity" role="status">
          {p.capacity.message}
        </p>
      )}
      {p && !p.can_create && p.reason !== 'no_suitable_squares' && seasonNoticeProps && (
        <SeasonNotice {...seasonNoticeProps} text={p.reason === 'chosen_species_outside_best_months' ? 'None of your chosen species can be planted in these dates.' : ''} />
      )}
      {p && !p.can_create && p.reason === 'no_suitable_squares' && <p className="nw-error">{p.message}</p>}

      <button type="button" className="nw-btn nw-btn-go nw-btn-wide" disabled={!!reason || creating} onClick={onCreate}>
        {creating ? 'Creating…' : 'Create plan'}
      </button>
      {reason && (
        <p className="nw-hint" role="status" id="nw-plan-reason">
          {reason}
        </p>
      )}
      {createError && (
        <p className="nw-error" role="alert">
          {createError}
        </p>
      )}
      {result && (
        <div className="nw-created" role="status">
          <strong>
            Placed {placed} of {requested}
          </strong>
          {placed < requested && (
            <ul>
              {sm.saplings_unallocated > 0 && <li>{sm.saplings_unallocated} could not be shared out: each species fits only so many squares and the caps are used up.</li>}
              {sm.saplings_unmatched > 0 && <li>{sm.saplings_unmatched} found no suitable square left for their species.</li>}
              {sm.saplings_unallocated === 0 && sm.saplings_unmatched === 0 && <li>The area has no more suitable squares.</li>}
            </ul>
          )}
          <button type="button" className="nw-btn nw-btn-small" onClick={onAnother}>
            Make another plan
          </button>
        </div>
      )}
    </div>
  )
}
