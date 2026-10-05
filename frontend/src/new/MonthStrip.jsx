import { MONTH_LETTERS, monthsText } from './season.js'

// Twelve small cells J F M A M J J A S O N D. `filled` = the months a species can be planted (cell filled); `ring` = the months of the planting window (cell ringed).
// The meaning is also given in words for screen readers, so colour is never the only signal.
export default function MonthStrip({ filled = null, ring = null, size = 'small', label = '' }) {
  const f = new Set(filled ?? [])
  const r = new Set(ring ?? [])
  const parts = []
  if (filled !== null) parts.push(`Planting months: ${monthsText([...f].sort((a, b) => a - b))}.`)
  if (ring !== null) parts.push(`Your dates cover: ${monthsText([...r].sort((a, b) => a - b))}.`)
  return (
    <span className={`nw-months nw-months-${size}`} role="img" aria-label={label || parts.join(' ')}>
      {MONTH_LETTERS.map((l, i) => (
        <span key={i} className={`nw-mo ${f.has(i + 1) ? 'is-filled' : ''} ${r.has(i + 1) ? 'is-ring' : ''}`} aria-hidden="true">
          {l}
        </span>
      ))}
    </span>
  )
}
