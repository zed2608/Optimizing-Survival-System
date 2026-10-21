// The tour engine's brain (R1 W3). One controller for every tour of the dashboard; the host (TourHost.jsx) only draws what the controller says.
//
// Rules the engine keeps (and tests/scripts/tour_walk.mjs checks):
//  - a step NEVER shows without its target: the target (data-tour="id") must be on screen, visible and inside the viewport (the engine waits up to WAIT_MS, scrolls it into view);
//    a step without a target is SKIPPED and written to window.__tourSkipped (the walker fails on it) - unless it is marked `optional` (a thing that exists only sometimes, e.g. the demo banner);
//  - a tour belongs to a page; the Weather tour never shows a Studio step: a page change that the engine did not make ends the tour;
//  - state safety: the selections are saved before the tour starts (bridge.snapshot) and restored when it ends or is skipped;
//  - the tour NEVER writes real data: setup() may only use the bridge (navigation) and ui.toggle(id) (a toggle that opens a menu or panel); engine-made clicks on anything that creates a plan, a link or
//    a field check are refused (see UNSAFE).
import { useSyncExternalStore } from 'react'

export const WAIT_MS = 2000
const UNSAFE = '[data-role="create-plan"], [data-role="field-save"], [data-tour-unsafe], .fc-bigbtn, .nw-btn-go[type="submit"]'

let bridge = null
let snapshot = null
let navigating = 0
let token = 0
let timer = null
let current = null // { tour, section, steps, idx }
let ready = null // { step, el, tourId, idx, total } while a step is on screen
let listeners = new Set()
let version = 0

const emit = () => {
  version += 1
  listeners.forEach((f) => f())
}
const subscribe = (f) => {
  listeners.add(f)
  return () => listeners.delete(f)
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const visible = (el) => {
  if (!el || !el.isConnected) return false
  const r = el.getBoundingClientRect()
  const s = getComputedStyle(el)
  return r.width > 2 && r.height > 2 && s.visibility !== 'hidden' && s.display !== 'none'
}
export const findTarget = (id) => {
  for (const el of document.querySelectorAll(`[data-tour="${id}"]`)) if (visible(el)) return el
  return null
}
const inViewport = (el) => {
  const r = el.getBoundingClientRect()
  return r.top >= 0 && r.left >= 0 && r.bottom <= innerHeight && r.right <= innerWidth
}

export function registerBridge(b) {
  bridge = b
  return () => {
    if (bridge === b) bridge = null
  }
}
export const getBridge = () => bridge

// what setup() may use
const ui = {
  exists: (id) => !!findTarget(id),
  // press a toggle that opens or closes a menu / panel / step. Refuses anything that could write data.
  toggle: async (id) => {
    const el = findTarget(id)
    if (!el) return false
    if (el.matches(UNSAFE) || el.closest(UNSAFE)) throw new Error(`the tour may not press ${id}`)
    el.click()
    await sleep(250)
    return true
  },
  // open a <details> (its summary is pressed only when it is closed)
  openDetails: async (id) => {
    const el = findTarget(id)
    if (el && el.tagName === 'DETAILS' && !el.open) {
      el.querySelector('summary')?.click()
      await sleep(250)
    }
    return !!el
  },
  sleep,
  waitFor: async (fn, ms = WAIT_MS) => {
    const t0 = Date.now()
    while (Date.now() - t0 < ms) {
      try {
        const v = fn()
        if (v) return v
      } catch {
        /* not there yet */
      }
      await sleep(60)
    }
    return null
  },
}

async function goPage(page) {
  if (!bridge || !page || page === 'any') return
  if (bridge.page() === page) return
  navigating += 1
  try {
    await bridge.setPage(page)
    await ui.waitFor(() => bridge.page() === page, 1500)
    await sleep(200)
  } finally {
    navigating -= 1
  }
}

async function runStep(my, dir) {
  const { steps } = current
  while (my === token && current && current.idx >= 0 && current.idx < steps.length) {
    const step = steps[current.idx]
    ready = null
    emit()
    try {
      await goPage(step.page ?? current.tour.page)
      if (my !== token) return
      if (step.setup) await step.setup({ bridge, ui })
      if (my !== token) return
    } catch (e) {
      console.warn('tour setup failed', step.id, e)
    }
    let el = null
    if (step.target) {
      el = await ui.waitFor(() => findTarget(step.target), WAIT_MS)
      if (el) {
        // line the target up: a target taller than most of the screen (or a step that shows a region of it) by its top, anything else centred. Panels that are still opening move things, so look again.
        for (let k = 0; k < 5; k += 1) {
          const tall = el.getBoundingClientRect().height > innerHeight * 0.8
          el.scrollIntoView({ block: tall || step.region ? 'start' : 'center', inline: 'nearest' })
          await sleep(k === 0 ? 220 : 160)
          if (my !== token) return
          if (step.region || inViewport(el) || el.getBoundingClientRect().height > innerHeight * 0.8) break
        }
        // a panel that was still sliding (a step opening, another closing) can move the target after the passes above: look once more when it has settled
        await sleep(350)
        if (my !== token) return
        if (!step.region && !inViewport(el) && el.getBoundingClientRect().height <= innerHeight * 0.8) {
          el.scrollIntoView({ block: 'center', inline: 'nearest' })
          await sleep(200)
        }
      }
      if (my !== token) return
      if (!el) {
        if (!step.optional) {
          window.__tourSkipped = [...(window.__tourSkipped || []), `${current.tour.id}/${step.id} (${step.target})`]
          console.warn('tour step skipped: its target is not on screen', step.id, step.target)
        }
        if (step.teardown) await step.teardown({ bridge, ui }).catch(() => {})
        current.idx += dir
        continue
      }
    }
    ready = { step, el, tourId: current.tour.id, idx: current.idx, total: steps.length, section: current.section }
    emit()
    return
  }
  if (my === token && current) {
    if (current.idx >= steps.length) await finish(true)
    else if (current.idx < 0) {
      current.idx = 0
      await runStep(my, 1)
    }
  }
}

export async function startTour(tour, opts = {}) {
  if (!tour) return false
  await stopTour('restart', false)
  const steps = (opts.section ? tour.sections.find((s) => s.id === opts.section)?.steps : tour.sections.flatMap((s) => s.steps)) ?? []
  if (!steps.length) return false
  window.__tourSkipped = []
  window.__tourActive = true
  snapshot = bridge ? bridge.snapshot() : null
  current = { tour, section: opts.section ?? null, steps, idx: 0, auto: !!opts.auto }
  const my = ++token
  clearInterval(timer)
  timer = setInterval(() => {
    // a page change the engine did not make (the person clicked a tab): the tour ends, it never shows steps of another page
    if (!current || navigating || !bridge) return
    const want = current.tour.page
    if (want && want !== 'any' && bridge.page() !== want) stopTour('page-changed')
  }, 400)
  emit()
  await runStep(my, 1)
  return true
}

export async function goTo(delta) {
  if (!current) return
  const step = ready?.step
  if (step?.teardown) await step.teardown({ bridge, ui }).catch(() => {})
  current.idx += delta
  const my = ++token
  if (current.idx >= current.steps.length) return finish(true)
  if (current.idx < 0) current.idx = 0
  await runStep(my, delta < 0 ? -1 : 1)
}
export const nextStep = () => goTo(1)
export const prevStep = () => goTo(-1)

async function finish(done) {
  const c = current
  await stopTour(done ? 'done' : 'closed', true)
  return c
}

export async function stopTour(reason = 'closed', restore = true) {
  const step = ready?.step
  token += 1
  clearInterval(timer)
  const c = current
  current = null
  ready = null
  if (step?.teardown) await step.teardown({ bridge, ui }).catch(() => {})
  if (c && restore && bridge && snapshot) {
    navigating += 1
    try {
      await bridge.restore(snapshot)
    } catch (e) {
      console.warn('tour: the selections could not be restored', e)
    } finally {
      navigating -= 1
    }
  }
  snapshot = null
  window.__tourActive = false
  if (c) window.__tourLast = { tour: c.tour.id, reason, skipped: window.__tourSkipped || [] }
  emit()
  return c
}

export const getTourState = () => ({ active: !!current, ready, tourId: current?.tour.id ?? null, auto: !!current?.auto, version })
let cache = null
const snap = () => {
  if (!cache || cache.version !== version) cache = getTourState()
  return cache
}
export const useTour = () => useSyncExternalStore(subscribe, snap, snap)
