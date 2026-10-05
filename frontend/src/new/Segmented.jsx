import HelpTip from './HelpTip.jsx'

// A small labelled choice between two or three options (radio buttons shown as a button strip), with an optional "?" help tip.
export default function Segmented({ name, label, help, value, options, onChange }) {
  return (
    <div className="nw-opt">
      <div className="nw-opt-head">
        <span className="nw-label" id={`nw-opt-${name}`}>
          {label}
        </span>
        {help && <HelpTip label={label}>{help}</HelpTip>}
      </div>
      <div className="nw-seg" role="radiogroup" aria-labelledby={`nw-opt-${name}`}>
        {options.map((o) => (
          <button key={o.value} type="button" role="radio" aria-checked={value === o.value} className={`nw-segbtn ${value === o.value ? 'is-active' : ''}`} onClick={() => onChange(o.value)}>
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}
