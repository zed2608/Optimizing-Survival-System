import { matchLevel, matchText } from './plainWords.js'

// The overall score in plain words for the Simple view: "Good · 77%" (the colour is never the only signal). The cut-offs are the ones of the map colours.
export default function MatchChip({ w, eligible = true, label = 'Overall match' }) {
  if (eligible === false) return <span className="nw-chip nw-match is-none" title={`${label}: not suitable here`}>Not suitable here</span>
  const l = matchLevel(w)
  return (
    <span className={`nw-chip nw-match is-${l ? l.toLowerCase() : 'none'}`} title={`${label}: ${matchText(w)}`}>
      {matchText(w)}
    </span>
  )
}
