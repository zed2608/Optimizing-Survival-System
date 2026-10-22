import { useContext } from 'react'
import Icon from '../Icon.jsx'
import { FAQ } from './tutorialContent.js'
import { HelpContext } from './helpContext.js'

// A small "?" next to a main control: it starts the guided tour of the current page (the same tour as Help > Tour of this page). Without a tour runner it opens the matching Help answer.
export default function AskHelp({ id }) {
  const { openHelp, startPageTour } = useContext(HelpContext)
  const faq = FAQ.find((f) => f.id === id)
  if (!faq) return null
  return (
    <button
      type="button"
      className="nw-askhelp"
      aria-label={startPageTour ? `Tour of this page: ${faq.q}` : `Help: ${faq.q}`}
      title={faq.q}
      data-help={id}
      onClick={(e) => {
        e.stopPropagation()
        if (startPageTour) startPageTour()
        else openHelp(id)
      }}
    >
      <Icon name="question" size={14} />
    </button>
  )
}
