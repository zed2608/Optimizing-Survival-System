import { useSyncExternalStore } from 'react'

// One toast system: success, info, warning, error. They stack, dismiss by themselves (errors stay longer) and can be closed. The text must be a plain sentence.
let list = []
let seq = 0
const listeners = new Set()
const emit = () => listeners.forEach((f) => f())
const LIFE = { success: 4000, info: 5000, warning: 7000, error: 9000 }

export function dismissToast(id) {
  list = list.filter((t) => t.id !== id)
  emit()
}
export function toast(kind, text, ms) {
  const k = LIFE[kind] ? kind : 'info'
  const id = ++seq
  list = [...list.slice(-3), { id, kind: k, text }]
  emit()
  if (typeof setTimeout === 'function') setTimeout(() => dismissToast(id), ms ?? LIFE[k])
  return id
}
export const clearToasts = () => {
  list = []
  emit()
}
const subscribe = (f) => {
  listeners.add(f)
  return () => listeners.delete(f)
}
export const useToasts = () => useSyncExternalStore(subscribe, () => list, () => list)
