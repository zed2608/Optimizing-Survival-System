export const NONE_IN_SEASON = 'None of the suitable species are in their best months for your dates. They are still listed; expect more watering and more losses outside the best months.'

// Shown when no species is in its best months for the dates: the species are still listed (W1). Two ways on: show all species, or change the dates.
// light = true inside the light result cards of the right-hand panel; dark (default) on the map and in the sidebar.
export default function SeasonNotice({ onShowAll, onChangeDates, light = false, text = '' }) {
  const btn = light ? 'btn btn-small' : 'nw-btn nw-btn-small'
  return (
    <div className={`nw-seasonnote ${light ? 'is-light' : ''}`} role="status">
      <strong>{text || NONE_IN_SEASON}</strong>
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
