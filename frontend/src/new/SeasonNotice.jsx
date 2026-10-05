import { formatDay } from './season.js'

// "Only 7 of 45 species can be planted between 6 Oct and 5 Nov" with the two ways out: show all species, or change the dates.
// light = true inside the light result cards of the right-hand panel; dark (default) on the map and in the sidebar.
export default function SeasonNotice({ kept, total, start, end, onShowAll, onChangeDates, light = false, text = '' }) {
  const btn = light ? 'btn btn-small' : 'nw-btn nw-btn-small'
  return (
    <div className={`nw-seasonnote ${light ? 'is-light' : ''}`} role="status">
      <strong>{text || `Only ${kept} of ${total} species can be planted between ${formatDay(start)} and ${formatDay(end)}.`}</strong>
      <div className="nw-row">
        <button type="button" className={`${btn} ${light ? 'btn-primary' : 'nw-btn-go'}`} onClick={onShowAll}>
          Show all species
        </button>
        <button type="button" className={btn} onClick={onChangeDates}>
          Change dates
        </button>
      </div>
    </div>
  )
}
