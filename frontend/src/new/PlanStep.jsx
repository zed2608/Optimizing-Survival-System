import CountsForm from './CountsForm.jsx'
import HelpTip from './HelpTip.jsx'
import { plainWarning } from './plainWords.js'
import SeasonNotice from './SeasonNotice.jsx'
import Callout from './ui/Callout.jsx'

const PRESETS = [50, 100, 300, 500]

// Step 5 "Plan": campaign name, assigned unit, the trees (one number for the automatic mix, or one row per chosen species), a compact summary of what the plan will use,
// the capacity message, and the one primary button.
export default function PlanStep({
  name, onName, unit, onUnit, n, onN, nValid, areaLabel, areaSplit = null, modeLabel, windowText, preview, reason, onCreate, creating, createError, result, onAnother, seasonNoticeProps,
  countsMode = false, countRows = [], counts = {}, onCount, areaMode = false, ownSpecies = false, onOwnSpecies, onAutoMix, picker = null,
}) {
  const p = preview.status === 'ok' ? preview.data : null
  const est = p?.blocks_estimate ?? null
  const placed = result?.summary?.saplings_placed
  const requested = result?.summary?.n_saplings_requested
  const sm = result?.summary
  const short = sm?.species_counts?.per_species?.filter((r) => r.unplaced > 0) ?? []
  return (
    <div>
      <div className="nw-opt-head">
        <label className="nw-label nw-grow" htmlFor="nw-campaign-name">
          Campaign name
        </label>
        <HelpTip label="Campaign name">The name of the planting event, saved with the plan.</HelpTip>
      </div>
      <input id="nw-campaign-name" data-tour="p-name" className="nw-input" value={name} maxLength={80} onChange={(e) => onName(e.target.value)} placeholder="e.g. Brgy. Santa Ana Tree Day" aria-required="true" />
      <label className="nw-label" htmlFor="nw-campaign-unit">
        Assigned unit
      </label>
      <input id="nw-campaign-unit" data-tour="p-unit" className="nw-input" value={unit} maxLength={80} onChange={(e) => onUnit(e.target.value)} placeholder="e.g. MENRO field team" />

      {countsMode ? (
        <>
          <div className="nw-opt-head">
            <span className="nw-label nw-grow">Trees for each species</span>
            <HelpTip label="Trees for each species">
              How many trees of each chosen species, 1 to 2000 in total. Exactly these numbers are planted, in blocks: each block is one 100 m grid square planted at the species spacing. The usual share limits do not apply, so a mix of mostly one species gets a warning.
            </HelpTip>
          </div>
          {ownSpecies && picker}
          {countRows.length === 0 ? <p className="nw-hint">Choose species to give each its trees.</p> : <CountsForm rows={countRows} counts={counts} onChange={onCount} est={est} />}
          {ownSpecies && (
            <button type="button" className="nw-linkbtn" onClick={onAutoMix}>
              Use the automatic mix
            </button>
          )}
        </>
      ) : (
        <>
          <div className="nw-opt-head">
            <label className="nw-label nw-grow" htmlFor="nw-saplings">
              Number of trees
            </label>
            <HelpTip label="Number of trees">How many trees to plan in total, from 1 to 2000. They are planted in blocks: each block is one 100 m grid square planted at the species spacing.</HelpTip>
          </div>
          <input id="nw-saplings" data-tour="p-trees" type="number" min="1" max="2000" className="nw-input" value={n} onChange={(e) => onN(e.target.value)} aria-invalid={!nValid} />
          <div className="nw-presets" role="group" aria-label="Tree number presets">
            {PRESETS.map((v) => (
              <button key={v} type="button" className={`nw-btn nw-btn-small ${String(n) === String(v) ? 'nw-btn-go' : ''}`} onClick={() => onN(String(v))}>
                {v}
              </button>
            ))}
          </div>
          {!nValid && (
            <Callout tone="error" role="alert">
              Trees: 1 to 2000.
            </Callout>
          )}
          {areaMode && (
            <button type="button" className="nw-linkbtn" onClick={onOwnSpecies}>
              Choose my own species and counts
            </button>
          )}
          {est && (
            <Callout tone="success" className="nw-estimate">
              About {est.blocks_about} block{est.blocks_about === 1 ? '' : 's'} of {est.typical_trees_per_block} trees (about {est.hectares_about} ha)
            </Callout>
          )}
        </>
      )}
      <dl className="nw-plansum" aria-label="What the plan will use" data-tour="p-summary">
        <div>
          <dt>Area</dt>
          <dd>
            {areaLabel || 'Not chosen'}
            {p ? ` · ${p.area.suitable_squares} suitable squares available` : ''}
            {areaSplit && (
              <span className="nw-sub" data-role="plan-area-split">
                {areaSplit}
              </span>
            )}
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
        <Callout tone="warning" className="nw-capacity">
          {p.capacity.message}
        </Callout>
      )}
      {p && !p.can_create && p.reason !== 'no_suitable_squares' && seasonNoticeProps && (
        <SeasonNotice {...seasonNoticeProps} text={p.reason === 'chosen_species_outside_best_months' ? 'None of your chosen species can be planted in these dates.' : ''} />
      )}
      {p && !p.can_create && p.reason === 'no_suitable_squares' && <Callout tone="error">{plainWarning(p.message)}</Callout>}

      <button type="button" className="nw-btn nw-btn-go nw-btn-wide" disabled={!!reason || creating} onClick={onCreate} data-role="create-plan" data-tour="p-create" data-tour-unsafe>
        {creating ? 'Creating…' : 'Create plan'}
      </button>
      {reason && (
        <p className="nw-hint" role="status" id="nw-plan-reason">
          {reason}
        </p>
      )}
      {createError && (
        <Callout tone="error" role="alert">
          {plainWarning(createError)}
        </Callout>
      )}
      {result && (
        <Callout
          tone={placed < requested ? 'warning' : 'success'}
          className="nw-created"
          title={`Placed ${placed} of ${requested} trees${sm.layout ? ` in ${sm.layout.blocks} block${sm.layout.blocks === 1 ? '' : 's'}` : ''}`}
          actions={
            <button type="button" className="nw-btn nw-btn-small" onClick={onAnother}>
              Make another plan
            </button>
          }
        >
          {short.length > 0 && (
            <ul>
              {short.map((r) => (
                <li key={r.species_id}>
                  {r.species}: {r.placed} of {r.requested} trees placed. {r.reason}
                </li>
              ))}
            </ul>
          )}
          {placed < requested && short.length === 0 && (
            <ul>
              {sm.saplings_unallocated > 0 && <li>{sm.saplings_unallocated} could not be shared out: each species fits only so many squares and the caps are used up.</li>}
              {sm.saplings_unmatched > 0 && <li>{sm.saplings_unmatched} found no suitable square left for their species.</li>}
              {sm.saplings_unallocated === 0 && sm.saplings_unmatched === 0 && <li>The area has no more suitable squares.</li>}
            </ul>
          )}
        </Callout>
      )}
    </div>
  )
}
