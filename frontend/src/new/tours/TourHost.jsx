import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../Icon.jsx'
import { tr, useLang } from '../i18n.js'
import { motionAllowed } from '../motionPref.js'
import { getTourState, nextStep, prevStep, startTour, stopTour, useTour } from './tourController.js'
import { getTour, TOURS } from './tourDefs.js'
import { freeBand, placePopover } from './tourLayout.js'

// The tour overlay (R1 W3): a dimmed screen with a cut-out (spotlight) and a ring around the real element, and a popover beside it. It is mounted once, ABOVE the lazy-loaded pages and the error boundary
// (main.jsx), so opening Weather or Analytics cannot close it. Esc closes; Right / Left arrows move; Tab stays inside the popover; the focus goes back to where it was.
const KEY_TOUR = 'nw_tour_done'
// a handle for the automated walk (scripts/tour_walk.mjs): list, start, stop, state. It starts nothing by itself.
if (typeof window !== 'undefined') {
  window.__tours = {
    list: () => TOURS.map((t) => ({ id: t.id, page: t.page, sections: t.sections.map((x) => ({ id: x.id, steps: x.steps.map((y) => ({ id: y.id, target: y.target, optional: !!y.optional })) })) })),
    start: (id, section) => startTour(getTour(id), { section }),
    stop: () => stopTour('test'),
    state: () => ({ ...getTourState(), ready: !!getTourState().ready }),
  }
}
const pick = (v, lang) => (v && typeof v === 'object' ? v[lang] ?? v.en : v) ?? ''
const rectOf = (el) => {
  const r = el.getBoundingClientRect()
  return { left: r.left, top: r.top, width: r.width, height: r.height }
}
// a step may spotlight only a part of a big target (the map, a tall card): region = fractions {x, y, w, h} of the element's box
const effectiveRegion = (rect, region, vp) => region ?? (vp.width < 640 && rect.height > vp.height * 0.5 ? { x: 0, y: 0, w: 1, h: Math.min(1, (vp.height * 0.38) / rect.height) } : null) // a tall target on a phone: only its top part is the spotlight, so the docked popover never covers it
const regionOf = (rect, region) => (region ? { left: rect.left + rect.width * region.x, top: rect.top + rect.height * region.y, width: rect.width * region.w, height: rect.height * region.h } : rect)
const same = (a, b) => a && b && ['left', 'top', 'width', 'height'].every((k) => Math.abs(a[k] - b[k]) < 0.5)

export default function TourHost() {
  const { active, ready, auto } = useTour()
  const lang = useLang()
  const popRef = useRef(null)
  const lastFocus = useRef(null)
  const [rect, setRect] = useState(null)
  const [size, setSize] = useState({ width: 340, height: 220 })
  const [vp, setVp] = useState({ width: window.innerWidth, height: window.innerHeight })
  const [never, setNever] = useState(true)
  const step = ready?.step

  // remember the focus when a tour starts, give it back when it ends
  useEffect(() => {
    if (active && !lastFocus.current) lastFocus.current = document.activeElement
    if (!active && lastFocus.current) {
      try {
        lastFocus.current.focus?.({ preventScroll: true })
      } catch {
        /* the element is gone */
      }
      lastFocus.current = null
    }
  }, [active])

  // follow the real element (it may move: scrolling, a panel that finishes opening, a resize)
  useEffect(() => {
    if (!ready?.el) return undefined
    const el = ready.el
    const tick = () => {
      setVp({ width: window.innerWidth, height: window.innerHeight })
      if (el.isConnected) setRect((old) => (same(old, rectOf(el)) ? old : rectOf(el)))
    }
    const first = requestAnimationFrame(tick)
    const id = setInterval(tick, 120)
    window.addEventListener('resize', tick)
    return () => {
      cancelAnimationFrame(first)
      clearInterval(id)
      window.removeEventListener('resize', tick)
    }
  }, [ready])

  useLayoutEffect(() => {
    if (!popRef.current) return
    const r = popRef.current.getBoundingClientRect()
    setSize((s) => (Math.abs(s.width - r.width) < 1 && Math.abs(s.height - r.height) < 1 ? s : { width: r.width, height: r.height }))
  }, [ready, lang, rect])

  const finish = useCallback(
    (done) => {
      try {
        if (done || never) window.localStorage.setItem(KEY_TOUR, '1')
      } catch {
        /* storage refused: the choice is not remembered */
      }
      stopTour(done ? 'done' : 'closed')
    },
    [never],
  )
  const goNext = useCallback(() => (ready && ready.idx >= ready.total - 1 ? finish(true) : nextStep()), [ready, finish])

  useEffect(() => {
    if (!active) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        finish(false)
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        goNext()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        prevStep()
      } else if (e.key === 'Tab' && popRef.current) {
        const f = [...popRef.current.querySelectorAll('button, input, [href]')].filter((x) => !x.disabled)
        if (!f.length) return
        const first = f[0]
        const last = f[f.length - 1]
        if (!popRef.current.contains(document.activeElement)) {
          e.preventDefault()
          first.focus()
        } else if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [active, finish, goNext])

  // the focus goes to the popover when a step opens
  useEffect(() => {
    if (ready && popRef.current) popRef.current.querySelector('[data-tour-primary]')?.focus({ preventScroll: true })
  }, [ready])

  if (!active || !step) return null
  const eff = ready.el && rect ? effectiveRegion(rect, step.region, vp) : null
  const shownRect = ready.el && rect ? regionOf(rect, eff) : null
  const pop = placePopover(step.target ? shownRect : null, size, vp)
  const band = freeBand(pop, vp)
  const pad = 6
  const hole = shownRect && step.target ? { x: Math.max(0, shownRect.left - pad), y: Math.max(0, shownRect.top - pad), w: shownRect.width + pad * 2, h: shownRect.height + pad * 2 } : null
  const last = ready.idx >= ready.total - 1
  const anim = motionAllowed()
  const watch = pick(step.watch, lang)
  return createPortal(
    <div className="tr-root" data-role="tour" data-tour-ui="true" data-step={step.id} data-target={step.target ?? ''} data-region={eff ? JSON.stringify(eff) : ''} data-tour-id={ready.tourId} data-placement={pop.placement} data-band={`${Math.round(band.top)}-${Math.round(band.bottom)}`}>
      <svg className="tr-dim" width={vp.width} height={vp.height} aria-hidden="true">
        <defs>
          <mask id="tr-mask">
            <rect className="tr-mask-all" x="0" y="0" width={vp.width} height={vp.height} />
            {hole && <rect className="tr-mask-hole" x={hole.x} y={hole.y} width={hole.w} height={hole.h} rx="10" />}
          </mask>
        </defs>
        <rect className="tr-dimrect" x="0" y="0" width={vp.width} height={vp.height} mask="url(#tr-mask)" />
      </svg>
      {hole && <div className={`tr-ring ${anim ? 'is-anim' : ''}`} style={{ left: hole.x, top: hole.y, width: hole.w, height: hole.h }} aria-hidden="true" />}
      <section
        ref={popRef}
        className={`tr-pop ${pop.docked ? 'is-docked' : ''} ${anim ? 'is-anim' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tr-title"
        style={{ left: pop.left, top: pop.top, width: pop.docked ? pop.width : undefined, maxHeight: pop.docked ? pop.height : vp.height - 16, visibility: size.height > 0 ? 'visible' : 'hidden' }}
      >
        <div className="tr-count" role="status">
          {tr('tour.progress', { n: ready.idx + 1, total: ready.total }, lang)}
        </div>
        <h2 id="tr-title" className="tr-title">
          {pick(step.title, lang)}
        </h2>
        <p className="tr-text">{pick(step.text, lang)}</p>
        {watch && (
          <p className="tr-watch">
            <strong>{tr('tour.watch', {}, lang)}</strong> {watch}
          </p>
        )}
        {auto && (
          <label className="tr-never">
            <input type="checkbox" checked={never} onChange={(e) => setNever(e.target.checked)} /> {tr('tour.never', {}, lang)}
          </label>
        )}
        <div className="tr-btns">
          <button type="button" className="nw-btn nw-btn-small" onClick={() => prevStep()} disabled={ready.idx === 0}>
            <Icon name="left" size={14} /> {tr('tour.back', {}, lang)}
          </button>
          <button type="button" className="nw-btn nw-btn-go nw-btn-small" onClick={goNext} data-tour-primary>
            {last ? tr('tour.done', {}, lang) : tr('tour.next', {}, lang)} {!last && <Icon name="right" size={14} />}
          </button>
          <button type="button" className="nw-btn nw-btn-small nw-btn-ghost" onClick={() => finish(false)}>
            {tr('tour.skip', {}, lang)}
          </button>
        </div>
      </section>
    </div>,
    document.body,
  )
}
