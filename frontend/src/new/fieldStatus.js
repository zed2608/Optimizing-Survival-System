import { FIELD_TABLE as table } from './fieldStatusTable.js'
import { getLang, tr } from './i18n.js'

// The colours and icons of the field-check statuses: ONE module for the map, the legend, the panels, the progress tab (and, through fieldStatus.json, the field map PDF).
// One violet for every mark (UX round 5, C). The shape tells the status apart: planted = a check; plantable (verified) = a ring; needs recheck = a question mark;
// not plantable (also water, paved, building, rock) = a cross. The words and the reason are always written next to the mark.
export const FIELD_ORDER = table.order
export const FIELD_CLASSES = table.classes

export function fieldClass(status, reason) {
  const base = table.status_class[status]
  return base === 'not_plantable' ? (table.reason_class[reason ?? ''] ?? 'not_plantable') : base
}
export const fieldColor = (cls) => (FIELD_CLASSES[cls] ?? FIELD_CLASSES.not_plantable).color
export const fieldIcon = (cls) => (FIELD_CLASSES[cls] ?? FIELD_CLASSES.not_plantable).icon
// the words follow the language toggle (messages.js fk.l.*); the English label of fieldStatus.json is the fallback (and what the field map PDF prints)
export const fieldLabel = (cls, lang = getLang()) => {
  const c = FIELD_CLASSES[cls] ? cls : 'not_plantable'
  const t = tr(`fk.l.${c}`, {}, lang)
  return t === `fk.l.${c}` ? FIELD_CLASSES[c].label : t
}
