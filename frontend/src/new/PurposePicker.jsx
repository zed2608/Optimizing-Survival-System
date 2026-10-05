import { PURPOSE_SHORT } from './labelsNew.js'

// Step 2: the planting purpose. Three compact options (radio buttons, keyboard friendly) with simple inline icons.
const ICONS = {
  urban: (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">
      <path d="M4 21V9l5-3v15M9 21V4l7 3v14M16 21v-8h4v8M3 21h18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  planting: (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">
      <path d="M12 21v-8M12 13c-4 0-6-2-6-6 4 0 6 2 6 6zM12 15c3 0 5-2 5-5-3 0-5 2-5 5zM8 21h8" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  watershed: (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">
      <path d="M12 3c3 4 5 6.5 5 9.5a5 5 0 0 1-10 0C7 9.5 9 7 12 3zM4 20c2-1.5 4 1.5 8 0s6 1.5 8 0" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
}

export default function PurposePicker({ value, onChange }) {
  return (
    <fieldset className="nw-fieldset">
      <legend className="sr-only">Planting purpose</legend>
      <div className="nw-purposes">
        {Object.keys(PURPOSE_SHORT).map((id) => (
          <label key={id} className={`nw-purpose ${value === id ? 'is-selected' : ''}`}>
            <input type="radio" name="nw-purpose" value={id} checked={value === id} onChange={() => onChange(id)} />
            {ICONS[id]}
            <span>{PURPOSE_SHORT[id]}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
