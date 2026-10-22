import Callout from './ui/Callout.jsx'

// Shown when no species is in its best months for the dates: the species are still listed (W1). Two ways on: show all species, or change the dates.
// `light` is kept for the callers that still pass it: the colours now come from the theme tokens, so there is no light / dark variant of the box.
export const NONE_IN_SEASON = 'None of the suitable species are in their best months for your dates. They are still listed; expect more watering and more losses outside the best months.'

export default function SeasonNotice({ onShowAll, onChangeDates, text = '' }) {
  return (
    <Callout
      tone="warning"
      className="is-banner"
      data-role="season-notice"
      actions={
        <>
          <button type="button" className="nw-btn nw-btn-small nw-btn-go" onClick={onShowAll}>
            Show all species
          </button>
          <button type="button" className="nw-btn nw-btn-small" onClick={onChangeDates}>
            Change dates
          </button>
        </>
      }
    >
      {text || NONE_IN_SEASON}
    </Callout>
  )
}
