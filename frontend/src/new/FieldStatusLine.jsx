import { tr, useLang } from './i18n.js'
import Icon from './Icon.jsx'
import FieldChip from './FieldChip.jsx'
import { REASON_LABEL, STATUS_LABEL, when } from './fieldLabels.js'
import { fieldClass } from './fieldStatus.js'

// The point panel only DESCRIBES the field check of the point now (UX 13): the latest mark and who made it. Making a mark is done from the map menu (right-click, or long press on a phone)
// or with the button here, which opens the same menu.
const describe = (e) => (e.status === 'not_plantable' ? `Not plantable: ${REASON_LABEL[e.reason] ?? e.reason}` : e.status === 'planted' ? `Planted: ${e.trees_planted} trees` : STATUS_LABEL[e.status])

export default function FieldStatusLine({ api, onOpen }) {
  const lang = useLang()
  const current = api.status === 'ok' ? api.data.current : null
  return (
    <section className="nw-pcard fc fc-top" aria-label="Field check of this spot" data-role="field-status-line" data-tour="r-field">
      <div className="nw-pcard-head">
        <h3>Field check</h3>
        {current ? <FieldChip cls={fieldClass(current.status, current.reason)} text={describe(current)} /> : api.status === 'ok' ? <span className="nw-chip">{tr('fc.none', {}, lang)}</span> : null}
      </div>
      {current && (
        <p className="muted">
          {tr('fc.by', { name: current.observer }, lang)} · {when(current.observed_at)}
          {current.note ? ` · “${current.note}”` : ''}
        </p>
      )}
      <p className="nw-hint">{tr('fc.how', {}, lang)}</p>
      <button type="button" className="nw-btn nw-btn-small" onClick={onOpen}>
        <Icon name="check" size={14} /> {tr('fc.open', {}, lang)}
      </button>
    </section>
  )
}
