import { LEGEND } from '../scale.js'

// Legend for the colours of the overall score W. Each colour also has a word and a number range.
export default function ColorLegend() {
  return (
    <ul className="legend" aria-label="Colour scale for the overall score W">
      {LEGEND.map((l) => (
        <li key={l.level} className="legend-item">
          <span className={`swatch level-${l.level}`} aria-hidden="true" />
          <span>
            <strong>{l.word}</strong> <span className="muted">({l.range})</span>
          </span>
        </li>
      ))}
    </ul>
  )
}
