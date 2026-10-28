import { useEffect, useRef, useState } from 'react'
import Icon from '../Icon.jsx'
import { tr, useLang } from '../i18n.js'
import { TOURS } from './tourDefs.js'

// The list of every tour (R1 W3), grouped by page: the tour of a whole page, and a short "explain this" tour for every section. A tour that needs a saved plan says so and is greyed out when there is none.
const PAGE_NAME = {
  any: { en: 'Every page', tl: 'Lahat ng pahina' },
  studio: { en: 'Plan & Map', tl: 'Plan & Map' },
  weather: { en: 'Weather', tl: 'Panahon' },
  history: { en: 'Campaign Logs', tl: 'Campaign Logs' },
  analytics: { en: 'System Analytics', tl: 'System Analytics' },
  help: { en: 'Help', tl: 'Tulong' },
}
const ORDER = ['any', 'studio', 'weather', 'history', 'analytics', 'help']
const pick = (v, lang) => (v && typeof v === 'object' ? v[lang] ?? v.en : v) ?? ''

export default function ToursMenu({ page, onStart, onClose, hasPlan }) {
  const lang = useLang()
  const ref = useRef(null)
  const [open, setOpen] = useState(null)
  useEffect(() => {
    ref.current?.querySelector('button')?.focus()
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  const groups = ORDER.map((p) => [p, TOURS.filter((t) => t.page === p && !t.hidden)]).filter(([, l]) => l.length)
  return (
    <div className="tm-scrim" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="tm-box" role="dialog" aria-modal="true" aria-labelledby="tm-title" ref={ref} data-role="tours-menu">
        <div className="tm-head">
          <h2 id="tm-title">{tr('tours.title', {}, lang)}</h2>
          <button type="button" className="nw-btn nw-btn-small" onClick={onClose}>
            <Icon name="close" size={14} /> {tr('tours.close', {}, lang)}
          </button>
        </div>
        <p className="tm-lead">{tr('tours.lead', {}, lang)}</p>
        {groups.map(([p, list]) => (
          <section key={p} className="tm-group" aria-label={pick(PAGE_NAME[p], lang)}>
            <h3>
              {pick(PAGE_NAME[p], lang)}
              {p === page && <span className="tm-here"> · {tr('tours.this', {}, lang)}</span>}
            </h3>
            {list.map((t) => {
              const blocked = t.requires === 'plan' && !hasPlan
              return (
                <div key={t.id} className="tm-tour" data-tour-entry={t.id}>
                  <div className="tm-row">
                    <button type="button" className="nw-btn nw-btn-go nw-btn-small" disabled={blocked} onClick={() => onStart(t.id)}>
                      <Icon name="target" size={14} /> {pick(t.title, lang)}
                    </button>
                    <button type="button" className="nw-linkbtn" aria-expanded={open === t.id} onClick={() => setOpen(open === t.id ? null : t.id)}>
                      {tr('tours.sections', {}, lang)}
                    </button>
                  </div>
                  <p className="tm-blurb">{blocked ? tr('tours.needsPlan', {}, lang) : pick(t.blurb, lang)}</p>
                  {open === t.id && (
                    <ul className="tm-sections">
                      {t.sections.map((s) => (
                        <li key={s.id}>
                          <button type="button" className="nw-btn nw-btn-small" disabled={blocked} onClick={() => onStart(t.id, s.id)}>
                            {pick(s.title, lang)} <span className="tm-n">({s.steps.length})</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )
            })}
          </section>
        ))}
      </div>
    </div>
  )
}
