import { useState } from 'react'

const KEY_VIEW = 'nw_view_mode'
const KEY_LEGEND = 'nw_legend_open'
const KEY_UNZONED = 'nw_include_unzoned'
const KEY_DETAIL = 'nw_map_detail'

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

// "Simple" (default, stored as compact) or "Detailed" (stored as full) for all panels, remembered in this browser. Detailed keeps every number and technical line.
export function useViewMode() {
  const [view, setView] = useState(() => (read(KEY_VIEW) === 'full' ? 'full' : 'compact'))
  const update = (v) => {
    const next = v === 'full' ? 'full' : 'compact'
    setView(next)
    write(KEY_VIEW, next)
  }
  return [view, update]
}

// "Include land outside the zoning map" (default ON), remembered in this browser. On: those squares are scored and flagged zoning_unconfirmed; off: confirmed legal zones only.
export function useIncludeUnzoned() {
  const [on, setOn] = useState(() => read(KEY_UNZONED) !== 'false')
  const update = (v) => {
    setOn(!!v)
    write(KEY_UNZONED, v ? 'true' : 'false')
  }
  return [on, update]
}

// The map shows "Simple" (default: coloured squares, outlines, labels) or "Detailed" (adds every field-check symbol, planted-tree codes and the grey squares). Remembered.
export function useMapDetail() {
  const [detailed, setDetailed] = useState(() => read(KEY_DETAIL) === 'detailed')
  const update = (v) => {
    setDetailed(!!v)
    write(KEY_DETAIL, v ? 'detailed' : 'simple')
  }
  return [detailed, update]
}

// The map legend starts collapsed (a small "Legend" button) and remembers whether it was opened.
export function useLegendOpen() {
  const [open, setOpen] = useState(() => read(KEY_LEGEND) === 'true')
  const update = (v) => {
    setOpen(!!v)
    write(KEY_LEGEND, v ? 'true' : 'false')
  }
  return [open, update]
}
