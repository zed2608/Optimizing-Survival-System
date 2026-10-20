import { useEffect, useRef } from 'react'
import Icon from './Icon.jsx'
import { tr, useLang } from './i18n.js'

// The welcome screen: first visit only (the flag is kept in the browser inside try/catch), skippable, and reopened from the header. An animated Sierra Madre ridgeline and a sapling drawn in code, and
// three short cards. It makes no promise about results: the third card says they are advisory.
export default function Welcome({ onClose }) {
  const lang = useLang()
  const t = (k) => tr(k, {}, lang)
  const ref = useRef(null)
  useEffect(() => {
    ref.current?.focus()
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  const cards = [
    ['map', 'welcome.c1.t', 'welcome.c1.p'],
    ['check', 'welcome.c2.t', 'welcome.c2.p'],
    ['info', 'welcome.c3.t', 'welcome.c3.p'],
  ]
  return (
    <div className="cy-welcome-scrim" data-role="welcome">
      <div className="cy-welcome" role="dialog" aria-modal="true" aria-labelledby="cy-welcome-title">
        <svg className="cy-ridge" viewBox="0 0 400 130" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
          <circle className="cy-sun" cx="318" cy="38" r="16" />
          <path className="cy-ridge-3" d="M0 92 L38 64 L70 82 L112 48 L150 76 L196 40 L240 74 L282 52 L330 80 L372 58 L400 74 V130 H0z" />
          <path className="cy-ridge-2" d="M0 104 L44 78 L86 98 L132 68 L178 96 L224 70 L270 98 L318 74 L362 96 L400 84 V130 H0z" />
          <path className="cy-ridge-1" d="M0 118 L60 100 L120 114 L190 96 L260 114 L330 98 L400 112 V130 H0z" />
          <path className="cy-sapling-w" d="M200 118V94M200 106c-7 0-11-4-12-10 7 0 11 4 12 10zM200 101c6-1 10-4 12-10-7 0-11 4-12 10z" />
        </svg>
        <div className="cy-welcome-body">
          <h2 id="cy-welcome-title">{t('welcome.title')}</h2>
          <p className="cy-welcome-sub">{t('welcome.sub')}</p>
          <div className="cy-welcome-cards">
            {cards.map(([icon, h, p]) => (
              <div key={h} className="cy-welcome-card">
                <span className="cy-empty-icon">
                  <Icon name={icon} size={20} />
                </span>
                <h3>{t(h)}</h3>
                <p>{t(p)}</p>
              </div>
            ))}
          </div>
          <div className="cy-welcome-actions">
            <button type="button" className="cy-btn cy-btn-quiet" onClick={onClose} data-role="welcome-skip">
              {t('welcome.skip')}
            </button>
            <button type="button" ref={ref} className="cy-btn cy-btn-primary" onClick={onClose} data-role="welcome-start">
              {t('welcome.start')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
