import Callout from './ui/Callout.jsx'
import { isSandbox } from './publicMode.js'

// First-screen notice of the public sandbox (only when the service says so): the text comes from the service so that it is written in one place.
export default function PublicNotice({ health }) {
  if (!isSandbox(health)) return null
  const text = health.public_mode.notice || 'Demo / sandbox. Data is provisional and not yet signed off by the agriculturist. Entries reset regularly.'
  return (
    <Callout tone="warning" role="note" className="is-banner nw-notice nw-notice-sandbox" data-notice="sandbox" data-tour="h-banner">
      {text}
    </Callout>
  )
}
