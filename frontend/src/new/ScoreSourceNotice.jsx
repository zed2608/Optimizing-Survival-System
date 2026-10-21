import Callout from './ui/Callout.jsx'
import { isFallback } from './scoreSource.js'

// Shown at the top of the dashboard only when the service had to fall back from the Random Forest to the expert rules. In normal mode (S from the Random Forest) nothing is shown.
export default function ScoreSourceNotice({ health }) {
  if (!isFallback(health)) return null
  return (
    <Callout tone="warning" className="is-banner nw-notice" data-notice="score-source">
      Random Forest scores are not loaded. The app is using the rule scores. Run scripts/rebuild_scores.py.
    </Callout>
  )
}
