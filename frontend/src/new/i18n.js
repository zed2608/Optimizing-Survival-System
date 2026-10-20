import { useSyncExternalStore } from 'react'
import { MESSAGES } from './messages.js'

// English / Taglish switch of the Studio strings introduced in the UX rounds (UX round 4, Phase 2). Default English. The choice is kept in the browser (localStorage inside try/catch:
// when the storage is blocked the page still works and starts in English). Species names, scientific names, source quotes and evidence text, the Field Pack, the tutorial and Help are NOT translated here.
export const LANGS = ['en', 'tl']
export const LANG_KEY = 'nw_lang'

let current = 'en'
try {
  const v = localStorage.getItem(LANG_KEY)
  if (v === 'en' || v === 'tl') current = v
} catch {
  /* storage blocked: stay in English */
}
const listeners = new Set()

export const getLang = () => current
export function setLang(l) {
  if (!LANGS.includes(l) || l === current) return
  current = l
  try {
    localStorage.setItem(LANG_KEY, l)
  } catch {
    /* not saved: the choice still holds for this page */
  }
  listeners.forEach((f) => f())
}
const subscribe = (f) => {
  listeners.add(f)
  return () => listeners.delete(f)
}
export const useLang = () => useSyncExternalStore(subscribe, getLang, getLang)

// tr(key, {name: value}, lang): the message in the language (English when the key is missing in it), with {name} placeholders filled.
export function tr(key, params = {}, lang = current) {
  const text = MESSAGES[lang]?.[key] ?? MESSAGES.en[key]
  if (text === undefined) return key
  return text.replace(/\{(\w+)\}/g, (m, k) => (params[k] === undefined ? m : String(params[k])))
}
