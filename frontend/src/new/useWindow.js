import { useState } from 'react'
import { localToday, restoreWindow, validateWindow } from './season.js'

const KEY_WINDOW = 'nw_planting_window'
const KEY_ONLY = 'nw_season_only'

function readJson(key) {
  try {
    return JSON.parse(window.localStorage.getItem(key) ?? 'null')
  } catch {
    return null
  }
}
function write(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* the browser may refuse storage: the dates are then simply not remembered */
  }
}

// The planting window: start and end dates (default today to 30 days later), remembered in this browser.
// `raw` is what the date boxes hold (it may be wrong while someone is typing); `applied` is the last valid window, the one every request uses,
// so a half-typed or wrong date never changes the results. `error` is the plain-words problem with `raw`, or ''.
export function usePlantingWindow() {
  const [today] = useState(localToday)
  const [raw, setRaw] = useState(() => restoreWindow(readJson(KEY_WINDOW), today))
  const [applied, setApplied] = useState(raw)
  const check = validateWindow(raw.start, raw.end, today)
  const update = (patch) => {
    const next = { ...raw, ...patch }
    setRaw(next)
    if (validateWindow(next.start, next.end, today).ok) {
      setApplied(next)
      write(KEY_WINDOW, next)
    }
  }
  return { today, raw, applied, error: check.ok ? '' : check.error, setStart: (v) => update({ start: v }), setEnd: (v) => update({ end: v }), setRange: (start, end) => update({ start, end }) }
}

// "Only species that can be planted in my dates": ON by default, remembered in this browser.
export function useOnlySeason() {
  const [only, setOnly] = useState(() => readJson(KEY_ONLY) !== false)
  const update = (v) => {
    setOnly(v)
    write(KEY_ONLY, v)
  }
  return [only, update]
}
