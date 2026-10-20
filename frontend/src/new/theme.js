import { useSyncExternalStore } from 'react'

// Light / dark theme of the dashboard (UX revamp). The default follows the OS preference; the header button chooses one and remembers it in the browser (localStorage inside try/catch:
// when the storage is blocked the page still works and keeps following the OS). The choice is written on <html data-theme="light|dark">; without it the CSS follows prefers-color-scheme.
export const THEME_KEY = 'nw_theme'

const osDark = () => {
  try {
    return typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}
let chosen = null // 'light' | 'dark' | null (= follow the OS)
try {
  const v = localStorage.getItem(THEME_KEY)
  if (v === 'light' || v === 'dark') chosen = v
} catch {
  /* storage blocked: follow the OS */
}
const listeners = new Set()
const apply = () => {
  try {
    if (chosen) document.documentElement.setAttribute('data-theme', chosen)
    else document.documentElement.removeAttribute('data-theme')
  } catch {
    /* no document (tests) */
  }
}
apply()
try {
  if (typeof matchMedia === 'function') matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => listeners.forEach((f) => f()))
} catch {
  /* old browser */
}

export const effectiveTheme = () => chosen ?? (osDark() ? 'dark' : 'light')
export function setTheme(t) {
  chosen = t === 'light' || t === 'dark' ? t : null
  try {
    if (chosen) localStorage.setItem(THEME_KEY, chosen)
    else localStorage.removeItem(THEME_KEY)
  } catch {
    /* not saved: the choice still holds for this page */
  }
  apply()
  listeners.forEach((f) => f())
}
export const toggleTheme = () => setTheme(effectiveTheme() === 'dark' ? 'light' : 'dark')
const subscribe = (f) => {
  listeners.add(f)
  return () => listeners.delete(f)
}
export const useTheme = () => useSyncExternalStore(subscribe, effectiveTheme, () => 'light')
