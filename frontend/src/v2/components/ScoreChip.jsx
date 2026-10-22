import { LEVEL_WORD, pct, wLevel } from '../scale.js'

// The overall score W as a percentage AND a word, on a colour (the colour is never the only signal).
export default function ScoreChip({ w, eligible = true, label = 'Overall score' }) {
  const level = wLevel(w, eligible)
  const text = pct(w)
  const word = !eligible ? 'Not suitable' : LEVEL_WORD[level]
  return (
    <span className={`chip level-${level}`} title={`${label}: ${text ?? 'Data Unavailable'} (${word})`}>
      <strong>{text ?? 'n/a'}</strong>
      <span className="chip-word">{word}</span>
    </span>
  )
}
