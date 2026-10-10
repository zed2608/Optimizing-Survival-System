import Icon from './Icon.jsx'
import { isFallback } from './scoreSource.js'

// Shown at the top of the dashboard only when the service had to fall back from the Random Forest to the expert rules. In normal mode (S from the Random Forest) nothing is shown.
export default function ScoreSourceNotice({ health }) {
  if (!isFallback(health)) return null
  return (
    <div className="nw-notice" role="status" data-notice="score-source">
      <Icon name="warn" size={16} />
      <span>Random Forest scores are not loaded. The app is using the rule scores. Run scripts/rebuild_scores.py.</span>
    </div>
  )
}
