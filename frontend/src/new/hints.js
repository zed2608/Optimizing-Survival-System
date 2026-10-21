import { useSyncExternalStore } from 'react'

// "Show hints": the small "?" buttons next to controls are hidden by default and shown when this switch is on. Kept in the browser inside try/catch (works without storage).
export const HINTS_KEY = 'nw_hints'
let on = false
try {
  on = localStorage.getItem(HINTS_KEY) === '1'
} catch {
  /* storage blocked: hints off */
}
const listeners = new Set()
export const hintsOn = () => on
export function setHints(v) {
  on = !!v
  try {
    if (on) localStorage.setItem(HINTS_KEY, '1')
    else localStorage.removeItem(HINTS_KEY)
  } catch {
    /* not saved: the choice still holds for this page */
  }
  listeners.forEach((f) => f())
}
const subscribe = (f) => {
  listeners.add(f)
  return () => listeners.delete(f)
}
export const useHints = () => useSyncExternalStore(subscribe, hintsOn, () => false)
