import { FIELD_TABLE as table } from './fieldStatusTable.js'

// The colours and icons of the field-check statuses: ONE module for the map, the legend, the panels, the progress tab (and, through fieldStatus.json, the field map PDF).
// planted = green with a check; plantable (verified) = green ring; needs recheck = amber with a question mark; not plantable = red with a cross,
// except water reasons = blue and paved / building / rock = gray. Colour is never the only signal: every class has an icon and words.
export const FIELD_ORDER = table.order
export const FIELD_CLASSES = table.classes

export function fieldClass(status, reason) {
  const base = table.status_class[status]
  return base === 'not_plantable' ? (table.reason_class[reason ?? ''] ?? 'not_plantable') : base
}
export const fieldColor = (cls) => (FIELD_CLASSES[cls] ?? FIELD_CLASSES.not_plantable).color
export const fieldIcon = (cls) => (FIELD_CLASSES[cls] ?? FIELD_CLASSES.not_plantable).icon
export const fieldLabel = (cls) => (FIELD_CLASSES[cls] ?? FIELD_CLASSES.not_plantable).label
