import MonthStrip from './MonthStrip.jsx'
import { monthsText, SEASON_WORDS } from './season.js'

// The season of one species for the chosen dates: a badge with WORDS and a symbol (never colour alone) and the 12-month strip
// (planting months filled, window months ringed). `season` is the season object of the API ({status, window_months, species_months, months_in_window}).
export default function SeasonBadge({ season, strip = true, className = '' }) {
  if (!season) return null
  const w = SEASON_WORDS[season.status] ?? SEASON_WORDS.unknown
  return (
    <span className={`nw-season-wrap ${className}`}>
      <span className={`nw-season nw-season-${season.status}`}>
        <span aria-hidden="true">{w.glyph}</span> {w.word}
      </span>
      {strip && <MonthStrip filled={season.species_months} ring={season.window_months} />}
    </span>
  )
}

// The same in full sentences, for the species detail ("Why this score?").
export function SeasonDetail({ season }) {
  if (!season) return null
  const w = SEASON_WORDS[season.status] ?? SEASON_WORDS.unknown
  return (
    <div className="nw-seasondetail">
      <h4>Planting window</h4>
      <p>
        <span className={`nw-season nw-season-${season.status}`}>
          <span aria-hidden="true">{w.glyph}</span> {w.word}
        </span>
      </p>
      <p>
        {season.species_months.length ? `Planting months: ${monthsText(season.species_months)}.` : 'No planting months are recorded for this species, so its season is not guessed.'} Your dates cover{' '}
        {monthsText(season.window_months)}
        {season.months_in_window.length ? `; ${monthsText(season.months_in_window)} can be planted.` : '.'}
      </p>
      <MonthStrip filled={season.species_months} ring={season.window_months} size="large" />
    </div>
  )
}
