import { MONTH_LETTERS, MONTH_SHORT, monthsText } from './season.js'

// Twelve small cells. `filled` = the months a species can be planted (cell filled); `ring` = the months of the planting window (cell ringed).
// The meaning is also given in words for screen readers, so colour is never the only signal.
//
// Round 28c (Karren item 9, Mationg item 63 - both raised "don't make the date indicator just letters" independently):
// single letters (J F M A M J J A S O N D) repeat - J, M and A each stand for three or two different months - so the
// glyphs themselves are ambiguous without reading a caption first. The size="small" strip (used densely in long rows
// and lists, where the caller already supplies a "?" tooltip or nearby spelled-out text) keeps the single letters to
// stay compact. The size="large" strip - the one standalone, full-width use (the Planting Window step, the full
// SeasonBadge tooltip, the species card detail drawer) has room, so it now shows unambiguous 3-letter month
// abbreviations (Jan, Feb, Mar, ...) instead, removing the ambiguity at the glyph itself rather than only in a caption.
export default function MonthStrip({ filled = null, ring = null, size = 'small', label = '', tourId }) {
  const f = new Set(filled ?? [])
  const r = new Set(ring ?? [])
  const parts = []
  if (filled !== null) parts.push(`Planting months: ${monthsText([...f].sort((a, b) => a - b))}.`)
  if (ring !== null) parts.push(`Your dates cover: ${monthsText([...r].sort((a, b) => a - b))}.`)
  const glyphs = size === 'large' ? MONTH_SHORT : MONTH_LETTERS
  return (
    <span className={`nw-months nw-months-${size}`} role="img" aria-label={label || parts.join(' ')} data-tour={tourId}>
      {glyphs.map((l, i) => (
        <span key={i} className={`nw-mo ${f.has(i + 1) ? 'is-filled' : ''} ${r.has(i + 1) ? 'is-ring' : ''}`} aria-hidden="true">
          {l}
        </span>
      ))}
    </span>
  )
}
