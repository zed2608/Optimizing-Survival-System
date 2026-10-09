import { useCallback, useEffect, useRef, useState } from 'react'
import Icon from '../Icon.jsx'
import { SECTIONS } from './tutorialContent.js'
import { ensureScreen, findTarget, runActions, sleep } from './tourActions.js'

// The guided tour (round 16): a spotlight on the real element, a card with what it is, what to do and one thing to watch for, and Back / Next / Skip.
// A step whose element is not on screen is skipped (or shown as a centred card when it only exists after the user did something).
// Keys: Right arrow = Next, Left arrow = Back, Escape = close. On a narrow screen the card sits at the bottom.
export default function GuidedTour({ steps, onClose }) {
  const [idx, setIdx] = useState(0)
  const [view, setView] = useState({ rect: null, center: true, later: '', forIdx: -1 })
  const dirRef = useRef(1)
  const tokenRef = useRef(0)
  const lastRef = useRef(null) // the step that is open now (its "after" actions run when it is left)
  const cardRef = useRef(null)
  const total = steps.length
  const step = steps[idx]

  const measure = useCallback(() => {
    const el = lastRef.current?.el
    if (!el || !document.contains(el)) return
    const r = el.getBoundingClientRect()
    setView((v) => (v.rect && Math.abs(v.rect.top - r.top) < 1 && Math.abs(v.rect.left - r.left) < 1 && Math.abs(v.rect.width - r.width) < 1 && Math.abs(v.rect.height - r.height) < 1 ? v : { ...v, rect: { top: r.top, left: r.left, width: r.width, height: r.height } }))
  }, [])

  const finish = useCallback(
    async (done) => {
      tokenRef.current += 1
      if (lastRef.current) await runActions(lastRef.current.step.after)
      lastRef.current = null
      await ensureScreen('studio')
      onClose(done)
    },
    [onClose],
  )

  // open a step: put the screen right, do the "before" actions, look for the element
  useEffect(() => {
    const token = ++tokenRef.current
    let dead = false
    ;(async () => {
      if (lastRef.current && lastRef.current.step !== step) await runActions(lastRef.current.step.after)
      if (dead || token !== tokenRef.current) return
      await ensureScreen(step.screen)
      await runActions(step.before)
      if (dead || token !== tokenRef.current) return
      let el = null
      if (step.target) {
        const tries = step.missing === 'center' && !step.before ? 5 : 14 // an element that only exists after the user did something is looked for briefly
        for (let i = 0; i < tries && !el; i += 1) {
          el = findTarget(step.target)
          if (!el) await sleep(100)
        }
      }
      if (dead || token !== tokenRef.current) return
      if (step.target && !el && step.missing !== 'center') {
        // not on screen: skip the step
        const next = idx + dirRef.current
        if (next >= total) finish(true)
        else if (next < 0) setIdx(0 === idx ? idx : 0)
        else setIdx(next)
        return
      }
      lastRef.current = { step, el }
      if (el) {
        el.scrollIntoView({ block: 'nearest', inline: 'nearest' })
        await sleep(120)
        const r = el.getBoundingClientRect()
        setView({ rect: { top: r.top, left: r.left, width: r.width, height: r.height }, center: false, later: '', forIdx: idx })
      } else setView({ rect: null, center: true, later: step.target ? step.later ?? '' : '', forIdx: idx })
      cardRef.current?.focus()
    })()
    return () => {
      dead = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idx, step])

  useEffect(() => {
    const t = setInterval(measure, 400)
    window.addEventListener('resize', measure)
    return () => {
      clearInterval(t)
      window.removeEventListener('resize', measure)
    }
  }, [measure])

  const next = useCallback(() => {
    dirRef.current = 1
    if (idx >= total - 1) finish(true)
    else setIdx(idx + 1)
  }, [idx, total, finish])
  const back = useCallback(() => {
    dirRef.current = -1
    if (idx > 0) setIdx(idx - 1)
  }, [idx])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        finish(false)
      } else if (e.key === 'ArrowRight') next()
      else if (e.key === 'ArrowLeft') back()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [finish, next, back])

  const narrow = typeof window !== 'undefined' && window.innerWidth < 700
  const ready = view.forIdx === idx // while a step is still being opened the spotlight of the step before is not shown
  const r = view.rect
  const vw = typeof window !== 'undefined' ? window.innerWidth : 1366
  const vh = typeof window !== 'undefined' ? window.innerHeight : 768
  const big = r && r.width * r.height > vw * vh * 0.5 // a huge target (the whole map or the whole sidebar): outline only, no dimming
  let cardStyle
  if (!narrow) {
    const W = 340
    const H = 400 // the tallest card: when the card would run past the bottom it is anchored to the bottom edge instead
    const place = (left, top) => (top > vh - H ? { left, bottom: 16 } : { left, top: Math.max(70, top) })
    if (!r || big) cardStyle = r ? { left: Math.round((vw - W) / 2), bottom: 16 } : place(Math.round((vw - W) / 2), Math.round(vh / 2 - 150))
    else if (r.left + r.width + 16 + W < vw) cardStyle = place(r.left + r.width + 16, r.top)
    else if (r.left - 16 - W > 0) cardStyle = place(r.left - 16 - W, r.top)
    else cardStyle = place(Math.max(12, Math.min(r.left, vw - W - 12)), r.top + r.height + 12 < vh - H ? r.top + r.height + 12 : Math.max(70, r.top - H))
  }
  const sec = SECTIONS.find((s) => s.id === step.section)
  return (
    <div className="nw-tour" role="dialog" aria-label={`Guided tour, step ${idx + 1} of ${total}: ${step.title}`}>
      {ready && r && <div className={`nw-tour-hole ${big ? 'is-big' : ''}`} style={{ top: r.top - 4, left: r.left - 4, width: r.width + 8, height: r.height + 8 }} aria-hidden="true" />}
      <div className={`nw-tour-card nw-tour-card-v2 ${narrow ? 'is-sheet' : ''}`} style={cardStyle} ref={cardRef} tabIndex={-1} aria-live="polite" data-step-id={step.id} data-centered={ready ? (view.center ? 'yes' : 'no') : 'loading'}>
        <div className="nw-tour-count">
          Step {idx + 1} of {total}
          {sec ? ` · ${sec.title}` : ''}
        </div>
        <h3>{step.title}</h3>
        <p>{step.text}</p>
        {step.watch && (
          <p className="nw-tour-watch">
            <Icon name="warn" size={14} /> <span>{step.watch}</span>
          </p>
        )}
        {ready && view.later && <p className="nw-tour-later">{view.later}</p>}
        <div className="nw-tour-btns">
          <button type="button" className="nw-btn nw-btn-small" onClick={back} disabled={idx === 0}>
            <Icon name="left" size={14} /> Back
          </button>
          {idx === total - 1 ? (
            <button type="button" className="nw-btn nw-btn-go nw-btn-small" onClick={() => finish(true)}>
              <Icon name="check" size={14} /> Done
            </button>
          ) : (
            <button type="button" className="nw-btn nw-btn-go nw-btn-small" onClick={next}>
              Next <Icon name="right" size={14} />
            </button>
          )}
          <button type="button" className="nw-btn nw-btn-small nw-btn-ghost" onClick={() => finish(false)}>
            Skip
          </button>
        </div>
      </div>
    </div>
  )
}
