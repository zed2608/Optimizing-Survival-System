import Icon from './Icon.jsx'
import { isSandbox } from './publicMode.js'

// First-screen notice of the public sandbox (only when the service says so): the text comes from the service so that it is written in one place.
export default function PublicNotice({ health }) {
  if (!isSandbox(health)) return null
  const text = health.public_mode.notice || 'Demo / sandbox. Data is provisional and not yet signed off by the agriculturist. Entries reset regularly.'
  return (
    <div className="nw-notice nw-notice-sandbox" role="note" data-notice="sandbox">
      <Icon name="warn" size={16} />
      <span>{text}</span>
    </div>
  )
}
