import Icon from './Icon.jsx'
import { FIELD_ORDER, fieldColor, fieldIcon, fieldLabel } from './fieldStatus.js'

// The legend of the field-check statuses (map symbols, progress tab, field map PDF use the same colours and icons).
export default function FieldLegend() {
  return (
    <div className="nw-fieldkey-box">
      <div className="nw-fieldkey-title">Mga marka ng field check: ang HUGIS ang nagsasabi ng uri (check, singsing, tandang pananong, krus). Hindi ito ang kulay ng score ng parisukat.</div>
    <ul className="nw-fieldkey" aria-label="Field check symbols">
      {FIELD_ORDER.map((k) => (
        <li key={k} style={{ color: fieldColor(k) }}>
          <Icon name={fieldIcon(k)} /> <span className="nw-fieldkey-text">{fieldLabel(k)}</span>
        </li>
      ))}
    </ul>
    </div>
  )
}
