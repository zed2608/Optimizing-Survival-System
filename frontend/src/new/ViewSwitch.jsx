const OPTIONS = [
  ['compact', 'Compact'],
  ['full', 'Full details'],
]

// "Compact | Full details": a two-option switch (radio buttons; Tab to it, Left/Right arrows or Enter/Space change it).
export default function ViewSwitch({ value, onChange }) {
  const onKey = (e) => {
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
      e.preventDefault()
      const next = value === 'compact' ? 'full' : 'compact'
      onChange(next)
      setTimeout(() => document.getElementById(`nw-view-${next}`)?.focus(), 0)
    }
  }
  return (
    <div className="nw-viewswitch" role="radiogroup" aria-label="How much detail to show" onKeyDown={onKey}>
      {OPTIONS.map(([v, label]) => (
        <button key={v} id={`nw-view-${v}`} type="button" role="radio" aria-checked={value === v} className={`nw-viewbtn ${value === v ? 'is-active' : ''}`} onClick={() => onChange(v)}>
          {label}
        </button>
      ))}
    </div>
  )
}
