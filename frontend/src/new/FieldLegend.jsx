import { tr, useLang } from './i18n.js'
import Icon from './Icon.jsx'
import { FIELD_ORDER, fieldColor, fieldIcon, fieldLabel } from './fieldStatus.js'

// The legend of the field-check statuses (map symbols, progress tab, field map PDF use the same colours and icons).
export default function FieldLegend() {
  const lang = useLang()
  return (
    <div className="nw-fieldkey-box">
      <div className="nw-fieldkey-title">{tr('fk.title', {}, lang)}</div>
    <ul className="nw-fieldkey" aria-label="Field check symbols">
      {FIELD_ORDER.map((k) => (
        <li key={k}>
          <span className="nw-fieldmark" style={{ color: fieldColor(k) }}>
            <Icon name={fieldIcon(k)} />
          </span>{' '}
          <span className="nw-fieldkey-text">{fieldLabel(k, lang)}</span>
        </li>
      ))}
    </ul>
    </div>
  )
}
