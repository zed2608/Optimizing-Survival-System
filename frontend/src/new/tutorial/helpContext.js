import { createContext } from 'react'

// Lets any control open the Help page at one answer: openHelp('check-code'). The default does nothing (so a component can be shown on its own).
// startPageTour() starts the guided tour of the page that is open (the "?" buttons use it); without it a "?" falls back to the Help answer.
export const HelpContext = createContext({ openHelp: () => {}, startPageTour: null })
