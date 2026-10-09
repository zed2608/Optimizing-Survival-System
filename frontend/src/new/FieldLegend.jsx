import Icon from './Icon.jsx'
import { FIELD_ORDER, fieldColor, fieldIcon, fieldLabel } from './fieldStatus.js'

// The legend of the field-check statuses (map symbols, progress tab, field map PDF use the same colours and icons).
export default function FieldLegend() {
  return (
    <ul className="nw-fieldkey" aria-label="Field check symbols">
      {FIELD_ORDER.map((k) => (
        <li key={k} style={{ color: fieldColor(k) }}>
          <Icon name={fieldIcon(k)} /> <span className="nw-fieldkey-text">{fieldLabel(k)}</span>
        </li>
      ))}
    </ul>
  )
}
