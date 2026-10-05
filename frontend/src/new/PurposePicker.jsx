import { PURPOSES } from '../v2/labels.js'

// The planting purpose: three plain choices (radio buttons, keyboard friendly) in the sidebar style of the earlier dashboard.
export default function PurposePicker({ value, onChange }) {
  return (
    <fieldset className="nw-fieldset">
      <legend className="nw-label">What is the planting for?</legend>
      {PURPOSES.map((p) => (
        <label key={p.value} className={`nw-choice ${value === p.value ? 'is-selected' : ''}`}>
          <input type="radio" name="nw-purpose" value={p.value} checked={value === p.value} onChange={() => onChange(p.value)} />
          <span>
            <strong>{p.label}</strong>
            <span className="nw-choice-help">{p.help}</span>
          </span>
        </label>
      ))}
    </fieldset>
  )
}
