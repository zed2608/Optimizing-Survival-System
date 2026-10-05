const MODES = [
  { id: 'species', label: 'I have species - find areas' },
  { id: 'area', label: 'I have an area - find species' },
]

// The two-way switch at the top of the sidebar (look copied from the mode switcher of the earlier dashboard).
export default function ModeSwitch({ value, onChange }) {
  return (
    <div className="nw-modes" role="radiogroup" aria-label="What do you want to find?">
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          role="radio"
          aria-checked={value === m.id}
          className={`nw-mode nw-mode-${m.id} ${value === m.id ? 'is-active' : ''}`}
          onClick={() => onChange(m.id)}
        >
          {m.label}
        </button>
      ))}
    </div>
  )
}
