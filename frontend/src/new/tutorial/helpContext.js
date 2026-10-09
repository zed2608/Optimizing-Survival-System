import { createContext } from 'react'

// Lets any control open the Help page at one answer: openHelp('check-code'). The default does nothing (so a component can be shown on its own).
export const HelpContext = createContext({ openHelp: () => {} })
