import { useId } from 'react'
import { setHints, useHints } from './hints.js'
import { tr, useLang } from './i18n.js'

// One switch that shows or hides every small "?" hint button of the panel (off by default).
export default function HintsSwitch() {
  const on = useHints()
  const lang = useLang()
  const id = useId()
  return (
    <label className="hint-switch" htmlFor={id} data-role="hints-switch">
      <span>{tr('hints.label', {}, lang)}</span>
      <input id={id} type="checkbox" role="switch" checked={on} onChange={(e) => setHints(e.target.checked)} />
      <span className="hint-track" aria-hidden="true">
        <span className="hint-knob" />
      </span>
    </label>
  )
}
