import { useState } from 'react'

const KEY_TOUR = 'nw_tour_done'
const KEY_BANNER = 'nw_help_banner_off'

function read(key) {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}
function write(key, value) {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    /* the browser may refuse storage: the choice is then simply not remembered */
  }
}

// The five steps of the sidebar in plain words (used by "How to use" and by the tour). `id` is the data-step of the sidebar step the tour highlights.
export const HOW_STEPS = [
  { id: 'goal', title: 'Goal', text: 'Choose what you have: species you want to plant, or an area you want to plant in.' },
  { id: 'purpose', title: 'Purpose', text: 'Say what the trees are for: shade in town, tree planting, or protecting soil and water.' },
  { id: 'window', title: 'Dates', text: 'Pick when you plan to plant. Each species has its own best months.' },
  { id: 'pick', title: 'Species or Area', text: 'Choose your species, or click the map to choose the area. The map and the panel on the right then show what suits.' },
  { id: 'plan', title: 'Plan', text: 'Name the campaign, say how many trees, and press Create plan. You get blocks to plant and a field kit to print.' },
]

// What the dashboard remembers about the help: the "First time?" banner is shown until the tour was taken or the banner was dismissed.
export function useHelpState() {
  const [bannerOff, setBannerOff] = useState(() => read(KEY_BANNER) === '1' || read(KEY_TOUR) === '1')
  const [howOpen, setHowOpen] = useState(false)
  const [tourStep, setTourStep] = useState(null) // null = no tour; 0..4 = the step shown
  const dismissBanner = () => {
    setBannerOff(true)
    write(KEY_BANNER, '1')
  }
  const finishTour = () => {
    setTourStep(null)
    setBannerOff(true)
    write(KEY_TOUR, '1')
  }
  return { bannerOff, dismissBanner, howOpen, setHowOpen, tourStep, setTourStep, finishTour }
}
