import { useState } from 'react'

const KEY = 'nw_observer_name'

// The name of the person doing field checks, remembered in this browser (localStorage). Browsers can refuse storage (private windows),
// so every read and write is guarded and the page works without it.
export function useObserver() {
  const [name, setName] = useState(() => {
    try {
      return window.localStorage.getItem(KEY) ?? ''
    } catch {
      return ''
    }
  })
  const update = (value) => {
    setName(value)
    try {
      window.localStorage.setItem(KEY, value)
    } catch {
      /* not remembered */
    }
  }
  return [name, update]
}
