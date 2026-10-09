import { EXAMPLE_POINTS, SCREENS } from './tutorialContent.js'

// The small DOM helpers of the guided tour. The tour drives the real dashboard the way a person would (it presses the same buttons), so no screen needs special code for it.

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const $ = (sel) => document.querySelector(sel)

export async function waitFor(fn, ms = 1500, every = 80) {
  const t0 = Date.now()
  for (;;) {
    try {
      const v = fn()
      if (v) return v
    } catch {
      /* the element is not there yet: try again */
    }
    if (Date.now() - t0 > ms) return null
    await sleep(every)
  }
}

function setNative(input, value) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

function visible(el) {
  if (!el) return false
  const r = el.getBoundingClientRect()
  return r.width > 2 && r.height > 2
}

// The first element of a selector list that is really on screen (a hidden one does not count).
export function findTarget(selector) {
  if (!selector) return null
  for (const el of document.querySelectorAll(selector)) if (visible(el)) return el
  return null
}

// Open the tab (screen) a step lives on.
export async function ensureScreen(screen) {
  const label = SCREENS[screen]?.tab
  if (!label) return
  const btn = [...document.querySelectorAll('.nw-tab')].find((b) => b.textContent.includes(label))
  if (btn && btn.getAttribute('aria-selected') !== 'true') {
    btn.click()
    await sleep(350)
  }
}

export async function runAction(a) {
  if (a.sidebar) {
    const t = $('.nw-toggle')
    if (t && t.getAttribute('aria-expanded') === 'false') {
      t.click()
      await sleep(350)
    }
  } else if (a.openStep) {
    const sec = $(`.nw-step[data-step=${a.openStep}]`)
    if (sec && !sec.classList.contains('is-open')) {
      sec.querySelector('.nw-step-toggle')?.click()
      await sleep(350)
    }
  } else if (a.click) {
    if (a.ifClosed && $(a.ifClosed)) return
    if (a.ifOpen && !$(a.ifOpen)) return
    const el = [...document.querySelectorAll(a.click)].find((e) => !a.text || e.textContent.includes(a.text))
    if (el) {
      el.click()
      await sleep(300)
    }
  } else if (a.planTab) {
    $(`#nw-ptab-${a.planTab}`)?.click()
    await sleep(300)
  } else if (a.demo === 'point') {
    if ($('.nw-right[aria-label="Species for this point"]')) return
    const input = $('.nw-search-input')
    if (!input) return
    let opened = false
    for (const id of EXAMPLE_POINTS) {                                    // the first example point of Santa Ana; the next one if it is not there any more
      setNative(input, String(id))
      const opt = await waitFor(() => $('.nw-search-opt'), 2500)
      if (!opt) continue
      opt.click()
      opened = !!(await waitFor(() => $('.nw-right[aria-label="Species for this point"]'), 5000))
      if (opened) break
    }
    if (opened) await sleep(500)
  } else if (a.demo === 'species') {
    if ($('.nw-card')) return
    await runAction({ sidebar: true })
    let info = $('.nw-step[data-step=pick] .nw-infobtn')
    if (!info) {
      await runAction({ openStep: 'pick' })
      info = await waitFor(() => $('.nw-step[data-step=pick] .nw-infobtn'), 800)
    }
    if (!info) return // no small i on screen (for example no species is listed for the dates): no card is opened and the step is shown as a centred card
    info.click()
    await waitFor(() => $('.nw-card'), 4000)
    await sleep(600)
  } else if (a.demo === 'closeCard') {
    const b = [...document.querySelectorAll('.nw-card button')].find((e) => e.textContent.trim().startsWith('Close'))
    b?.click()
    await sleep(300)
  }
}

export async function runActions(list = []) {
  for (const a of list) await runAction(a)
}
