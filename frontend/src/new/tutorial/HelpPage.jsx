import { useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../Icon.jsx'
import { matchFaq } from './faqSearch.js'
import { FAQ, GLOSSARY, SCREENS, SECTIONS, TOUR_STEPS, faqAnswer } from './tutorialContent.js'

// The whole guide as one clean page, shown only when printing (the "Print this guide" button).
function PrintGuide() {
  return (
    <section className="nw-printguide" aria-hidden="true">
      <h1>Tree Planting Decision Support: user guide</h1>
      <p>San Mateo, Rizal. Municipal Environment and Natural Resources Office (MENRO).</p>
      <h2>The tour, step by step</h2>
      {SECTIONS.map((sec) => {
        const steps = TOUR_STEPS.filter((s) => s.section === sec.id)
        if (!steps.length) return null
        return (
          <div key={sec.id}>
            <h3>{sec.title}</h3>
            {steps.map((s) => (
              <div key={s.id} className="nw-print-step">
                <h4>{s.title}</h4>
                <p>{s.text}</p>
                {s.watch && (
                  <p>
                    <strong>Watch for:</strong> {s.watch}
                  </p>
                )}
              </div>
            ))}
          </div>
        )
      })}
      <h2>Questions and answers</h2>
      {FAQ.map((f) => (
        <div key={f.id} className="nw-print-step">
          <h4>{f.q}</h4>
          <p>{f.a}</p>
        </div>
      ))}
      <h2>Glossary</h2>
      <dl>
        {GLOSSARY.map((g) => (
          <div key={g.term} className="nw-print-step">
            <dt>
              <strong>{g.term}</strong>
            </dt>
            <dd>{g.meaning}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

// The Help page (full screen): searchable questions and answers, a short glossary, the tour buttons and "Print this guide".
export default function HelpPage({ initialFaq, screen, onClose, onTour, onQuickTour, usingRules = false }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(initialFaq ?? null)
  const closeRef = useRef(null)
  const listRef = useRef(null)
  const shown = useMemo(() => FAQ.filter((f) => matchFaq(f, query)), [query])

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    if (initialFaq) {
      setTimeout(() => listRef.current?.querySelector(`[data-faq="${initialFaq}"]`)?.scrollIntoView({ block: 'start' }), 60)
    }
  }, [initialFaq])

  const topics = [...new Set(shown.map((f) => f.topic))]
  return (
    <div className="nw-helppage" role="dialog" aria-modal="true" aria-label="Help">
      <div className="nw-helppage-bar">
        <h2>Help</h2>
        <div className="nw-helppage-btns">
          <button type="button" className="nw-btn nw-btn-go" onClick={onTour}>
            <Icon name="target" /> Take the tour again
          </button>
          <button type="button" className="nw-btn" onClick={onQuickTour}>
            Quick tour of this screen
          </button>
          <button type="button" className="nw-btn" onClick={() => window.print()}>
            <Icon name="printer" /> Print this guide
          </button>
          <button type="button" className="nw-btn nw-btn-ghost" onClick={onClose} ref={closeRef}>
            <Icon name="close" /> Close
          </button>
        </div>
      </div>
      <div className="nw-helppage-body">
        <p className="nw-helppage-lead">Quick tour of this screen runs only the steps for {SCREENS[screen]?.name ?? 'the screen that is open'}.</p>
        <label className="nw-label" htmlFor="nw-help-search">
          Search the questions
        </label>
        <input id="nw-help-search" className="nw-input" type="search" placeholder="For example: check code, nursery, grey point" value={query} onChange={(e) => setQuery(e.target.value)} autoComplete="off" />
        <p className="muted nw-helppage-count" role="status">
          {shown.length === 0 ? 'No question matches. Try one other word.' : `${shown.length} of ${FAQ.length} questions`}
        </p>
        <div className="nw-faqlist" ref={listRef}>
          {topics.map((t) => (
            <section key={t} aria-label={t}>
              <h3>{t}</h3>
              {shown
                .filter((f) => f.topic === t)
                .map((f) => (
                  <div key={f.id} className={`nw-faq ${open === f.id ? 'is-open' : ''}`} data-faq={f.id}>
                    <button type="button" className="nw-faq-q" aria-expanded={open === f.id} aria-controls={`nw-faq-${f.id}`} onClick={() => setOpen(open === f.id ? null : f.id)}>
                      {f.q}
                    </button>
                    {open === f.id && (
                      <p className="nw-faq-a" id={`nw-faq-${f.id}`}>
                        {faqAnswer(f, usingRules)}
                      </p>
                    )}
                  </div>
                ))}
            </section>
          ))}
        </div>
        <section aria-label="Glossary" className="nw-glossary">
          <h3>Glossary</h3>
          <dl>
            {GLOSSARY.map((g) => (
              <div key={g.term}>
                <dt>{g.term}</dt>
                <dd>{g.meaning}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>
      <PrintGuide />
    </div>
  )
}
