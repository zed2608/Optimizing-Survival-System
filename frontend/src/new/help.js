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

// What the dashboard remembers about the help: the "First time?" banner is shown until the tour was taken or the banner was dismissed.
// helpPage: null (closed) or { faq } (open, at that answer). tour: null (no tour) or 'full' | 'screen'.
export function useHelpState() {
  const [bannerOff, setBannerOff] = useState(() => read(KEY_BANNER) === '1' || read(KEY_TOUR) === '1')
  const [helpPage, setHelpPage] = useState(null)
  const [tour, setTour] = useState(null)
  const dismissBanner = () => {
    setBannerOff(true)
    write(KEY_BANNER, '1')
  }
  const openHelp = (faq = null) => setHelpPage({ faq })
  const closeHelp = () => setHelpPage(null)
  const startTour = (kind = 'full') => {
    setHelpPage(null)
    setTour(kind)
  }
  const endTour = () => {
    setTour(null)
    setBannerOff(true)
    write(KEY_TOUR, '1')
  }
  return { bannerOff, dismissBanner, helpPage, openHelp, closeHelp, tour, startTour, endTour }
}
