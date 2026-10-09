import { useContext } from 'react'
import Icon from '../Icon.jsx'
import { FAQ } from './tutorialContent.js'
import { HelpContext } from './helpContext.js'

// A small "?" next to a main control: it opens the Help page at the matching answer.
export default function AskHelp({ id }) {
  const { openHelp } = useContext(HelpContext)
  const faq = FAQ.find((f) => f.id === id)
  if (!faq) return null
  return (
    <button
      type="button"
      className="nw-askhelp"
      aria-label={`Help: ${faq.q}`}
      title={faq.q}
      data-help={id}
      onClick={(e) => {
        e.stopPropagation()
        openHelp(id)
      }}
    >
      <Icon name="question" size={14} />
    </button>
  )
}
