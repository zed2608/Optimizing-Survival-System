import Icon from './Icon.jsx'
import PhChip from './PhChip.jsx'
import { Tooltip } from './ui/ui.jsx'
import { SEASON_WORDS, monthsText } from './season.js'

// The two small icons of a species row (UX revamp v2): the planting months and the soil pH. Each has a tooltip (hover and keyboard focus) and a text for screen readers. Neither is red: an out-of-season
// species or an uncertain pH is information, not an error. Display only.
export function SeasonIcon({ season }) {
  if (!season) return null
  const w = SEASON_WORDS[season.status] ?? SEASON_WORDS.unknown
  const best = season.status === 'out_of_season' && season.species_months?.length ? ` · Best months: ${monthsText(season.species_months)}` : ''
  const text = `${w.word}${best}`
  return (
    <Tooltip text={text}>
      <span className={`cy-rowicon is-${season.status}`} role="img" aria-label={text} tabIndex={0} data-role="season-icon">
        <Icon name="calendar" size={16} />
      </span>
    </Tooltip>
  )
}

export default function RowIcons({ season, phVerdict, speciesId, site, ranges }) {
  return (
    <span className="cy-rowicons">
      <SeasonIcon season={season} />
      <PhChip icon verdict={phVerdict} speciesId={speciesId} site={site} ranges={ranges} />
    </span>
  )
}
