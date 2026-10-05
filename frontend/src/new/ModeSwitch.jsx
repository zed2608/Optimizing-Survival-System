const GOALS = [
  { id: 'species', label: 'I have species', sub: 'Find where they grow' },
  { id: 'area', label: 'I have an area', sub: 'Find what to plant' },
]

// Step 1: the goal, as two big buttons (a radio group, so the arrow keys also work).
export default function ModeSwitch({ value, onChange }) {
  return (
    <div className="nw-modes" role="radiogroup" aria-label="Your goal">
      {GOALS.map((m) => (
        <button
          key={m.id}
          type="button"
          role="radio"
          aria-checked={value === m.id}
          className={`nw-mode nw-mode-${m.id} ${value === m.id ? 'is-active' : ''}`}
          onClick={() => onChange(m.id)}
        >
          <span className="nw-mode-main">{m.label}</span>
          <span className="nw-mode-sub">{m.sub}</span>
        </button>
      ))}
    </div>
  )
}
