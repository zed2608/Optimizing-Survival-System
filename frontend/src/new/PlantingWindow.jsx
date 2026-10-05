import { useState } from 'react'
import HelpTip from './HelpTip.jsx'
import MonthStrip from './MonthStrip.jsx'
import { addDays, bestSeasonWindow, formatSpan, MAX_DAYS, monthsText, parseMonths, windowMonths } from './season.js'

// Step 3: the planting window (start and end date), the 12-month strip of the months it covers, the "only species for my dates" switch and the
// button that jumps to the next planting season (the best window of NEXT_SEASON_DAYS days that starts today or later).
export default function PlantingWindow({ win, onlySeason, onOnlySeason, species }) {
  const [jumped, setJumped] = useState('')
  const months = windowMonths(win.applied.start, win.applied.end)
  const list = species.status === 'ok' ? species.data.species : null

  const jump = () => {
    if (!list) return
    const best = bestSeasonWindow(list.map((s) => parseMonths(s.planting_months)), win.today)
    win.setRange(best.start, best.end)
    setJumped(`Set to ${formatSpan(best.start, best.end)}: ${best.count} of ${best.total} species in season`)
  }

  return (
    <div>
      <div className="nw-dates">
        <div>
          <label className="nw-label" htmlFor="nw-start">
            Start
          </label>
          <input id="nw-start" type="date" className="nw-input" min={win.today} value={win.raw.start} aria-invalid={!!win.error} aria-describedby={win.error ? 'nw-window-error' : undefined} onChange={(e) => { setJumped(''); win.setStart(e.target.value) }} />
        </div>
        <div>
          <label className="nw-label" htmlFor="nw-end">
            End
          </label>
          <input
            id="nw-end"
            type="date"
            className="nw-input"
            min={win.raw.start || win.today}
            max={win.raw.start ? addDays(win.raw.start, MAX_DAYS - 1) : undefined}
            value={win.raw.end}
            aria-invalid={!!win.error}
            aria-describedby={win.error ? 'nw-window-error' : undefined}
            onChange={(e) => { setJumped(''); win.setEnd(e.target.value) }}
          />
        </div>
      </div>
      {win.error && (
        <p id="nw-window-error" className="nw-error" role="alert">
          {win.error}
        </p>
      )}
      <div className="nw-strip-row">
        <MonthStrip ring={months} size="large" label={`Months your dates cover: ${monthsText(months)}.`} />
      </div>
      <p className="nw-hint">Ringed months are covered.</p>
      <button type="button" className="nw-btn nw-btn-wide" onClick={jump} disabled={!list}>
        Jump to the next planting season
      </button>
      <p className="nw-hint nw-jumped" role="status">
        {jumped}
      </p>
      <div className="nw-opt-head nw-opt-gap">
        <label className="nw-togglerow" htmlFor="nw-only-season">
          <input id="nw-only-season" type="checkbox" checked={onlySeason} onChange={(e) => onOnlySeason(e.target.checked)} />
          <span>Only species for my dates</span>
        </label>
        <HelpTip label="Only species for my dates">
          Species that cannot be planted in your planting window are left out of rankings, the map colours, area tables and plans. Turn it off to see every species with its season label. Scores never change.
        </HelpTip>
      </div>
    </div>
  )
}
