import { useSyncExternalStore } from 'react'

// "Animations: Auto / On / Off". Off removes every animation, transition and blur (the light path for a weak phone). Auto follows the operating system (prefers-reduced-motion); On lets a person whose system setting asks for less motion still see the motion. The choice is kept in the browser
// inside try/catch and written on <html data-motion="on"> so that the stylesheet can switch its reduced-motion rule off.
export const MOTION_KEY = 'nw_anim'
let mode = 'auto'
try {
  const v = localStorage.getItem(MOTION_KEY)
  if (v === 'on' || v === 'off' || v === 'auto') mode = v
} catch {
  /* storage blocked: Auto */
}
const listeners = new Set()
const apply = () => {
  try {
    if (mode === 'on' || mode === 'off') document.documentElement.setAttribute('data-motion', mode)
    else document.documentElement.removeAttribute('data-motion')
  } catch {
    /* no document (tests) */
  }
}
apply()

export const getMotionMode = () => mode
export function setMotionMode(m) {
  mode = m === 'on' || m === 'off' ? m : 'auto'
  try {
    if (mode !== 'auto') localStorage.setItem(MOTION_KEY, mode)
    else localStorage.removeItem(MOTION_KEY)
  } catch {
    /* not saved: the choice still holds for this page */
  }
  apply()
  listeners.forEach((f) => f())
}
const osReduces = () => {
  try {
    return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}
export const motionAllowed = () => mode === 'on' || (mode === 'auto' && !osReduces())
const subscribe = (f) => {
  listeners.add(f)
  return () => listeners.delete(f)
}
export const useMotionMode = () => useSyncExternalStore(subscribe, getMotionMode, () => 'auto')
export const useMotionAllowed = () => useSyncExternalStore(subscribe, motionAllowed, () => true)
