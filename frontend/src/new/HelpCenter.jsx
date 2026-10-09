import Icon from './Icon.jsx'

export function HelpButton({ onClick }) {
  return (
    <button type="button" className="nw-btn nw-helpbtn" onClick={onClick} aria-haspopup="dialog">
      <Icon name="question" /> Help
    </button>
  )
}

// A dismissible banner at the top of the sidebar on the first visit.
export function HelpBanner({ onStart, onDismiss }) {
  return (
    <div className="nw-helpbanner" role="region" aria-label="First time">
      <span className="nw-helpbanner-text">First time? Take the guided tour</span>
      <button type="button" className="nw-btn nw-btn-go nw-btn-small" onClick={onStart}>
        Start the tour
      </button>
      <button type="button" className="nw-btn nw-btn-small nw-btn-ghost" onClick={onDismiss} aria-label="Hide this message">
        <Icon name="close" size={14} />
      </button>
    </div>
  )
}
