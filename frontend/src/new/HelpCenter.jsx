import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { HOW_STEPS } from './help.js'
import Icon from './Icon.jsx'

export function HelpButton({ onClick }) {
  return (
    <button type="button" className="nw-btn nw-helpbtn" onClick={onClick} aria-haspopup="dialog">
      <Icon name="question" /> Help
    </button>
  )
}

// A dismissible banner at the top of the sidebar on the first visit.
export function HelpBanner({ onStart, onDismiss }) {
  return (
    <div className="nw-helpbanner" role="region" aria-label="First time">
      <span className="nw-helpbanner-text">First time? Take the 1-minute tour</span>
      <button type="button" className="nw-btn nw-btn-go nw-btn-small" onClick={onStart}>
        Start the tour
      </button>
      <button type="button" className="nw-btn nw-btn-small nw-btn-ghost" onClick={onDismiss} aria-label="Hide this message">
        <Icon name="close" size={14} />
      </button>
    </div>
  )
}

// The "How to use" dialog: the five steps in plain words.
export function HowToUse({ onClose, onTour }) {
  const closeRef = useRef(null)
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="nw-dialog-back" onClick={onClose}>
      <section className="nw-dialog nw-howto" role="dialog" aria-modal="true" aria-label="How to use" onClick={(e) => e.stopPropagation()}>
        <div className="nw-dialog-head">
          <h2>How to use</h2>
          <button type="button" className="nw-btn nw-btn-ghost" onClick={onClose} ref={closeRef}>
            <Icon name="close" /> Close
          </button>
        </div>
        <ol className="nw-howlist">
          {HOW_STEPS.map((s, i) => (
            <li key={s.id}>
              <span className="nw-hown">{i + 1}</span>
              <div>
                <strong>{s.title}</strong>
                <div>{s.text}</div>
              </div>
            </li>
          ))}
        </ol>
        <div className="nw-dialog-foot">
          <button type="button" className="nw-btn nw-btn-go" onClick={onTour}>
            <Icon name="target" /> Take the 1-minute tour
          </button>
        </div>
      </section>
    </div>
  )
}

// A simple step-by-step tour: the sidebar step is opened and highlighted, a small card says what it is for, with Back, Next and Skip. Escape ends it.
export function Tour({ step, onStep, onFinish, onOpenStep }) {
  const [rect, setRect] = useState(null)
  const s = HOW_STEPS[step]
  const measure = useCallback(() => {
    const el = document.querySelector(`.nw-step[data-step=${s.id}]`)
    if (!el) return setRect(null)
    const r = el.getBoundingClientRect()
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height, right: r.right })
  }, [s.id])
  useEffect(() => {
    onOpenStep(s.id)
  }, [s.id, onOpenStep])
  useLayoutEffect(() => {
    const t = setTimeout(measure, 280) // after the step has opened
    window.addEventListener('resize', measure)
    return () => {
      clearTimeout(t)
      window.removeEventListener('resize', measure)
    }
  }, [measure])
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onFinish()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onFinish])
  const last = step === HOW_STEPS.length - 1
  const left = rect ? Math.min(rect.right + 14, window.innerWidth - 330) : 380
  const top = rect ? Math.max(70, Math.min(rect.top, window.innerHeight - 220)) : 140
  return (
    <div className="nw-tour" role="dialog" aria-label={`Tour, step ${step + 1} of ${HOW_STEPS.length}`}>
      {rect && <div className="nw-tour-hole" style={{ top: rect.top - 4, left: rect.left - 4, width: rect.width + 8, height: rect.height + 8 }} aria-hidden="true" />}
      <div className="nw-tour-card" style={{ top, left }}>
        <div className="nw-tour-count">
          Step {step + 1} of {HOW_STEPS.length}
        </div>
        <h3>{s.title}</h3>
        <p>{s.text}</p>
        <div className="nw-tour-btns">
          <button type="button" className="nw-btn nw-btn-small" onClick={() => onStep(step - 1)} disabled={step === 0}>
            <Icon name="left" size={14} /> Back
          </button>
          {last ? (
            <button type="button" className="nw-btn nw-btn-go nw-btn-small" onClick={onFinish}>
              <Icon name="check" size={14} /> Done
            </button>
          ) : (
            <button type="button" className="nw-btn nw-btn-go nw-btn-small" onClick={() => onStep(step + 1)}>
              Next <Icon name="right" size={14} />
            </button>
          )}
          <button type="button" className="nw-btn nw-btn-small nw-btn-ghost" onClick={onFinish}>
            Skip
          </button>
        </div>
      </div>
    </div>
  )
}
