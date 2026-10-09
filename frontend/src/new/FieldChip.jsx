import Icon from './Icon.jsx'
import { fieldColor, fieldIcon, fieldLabel } from './fieldStatus.js'

// A field-check status as a small chip: icon AND colour AND words (never colour alone). cls = planted | verified | recheck | not_plantable | water | hard.
export default function FieldChip({ cls, text }) {
  const c = fieldColor(cls)
  return (
    <span className="nw-chip nw-fchip" style={{ color: c, borderColor: c, borderWidth: 1, borderStyle: 'solid', background: '#fff' }}>
      <Icon name={fieldIcon(cls)} size={14} /> {text ?? fieldLabel(cls)}
    </span>
  )
}
