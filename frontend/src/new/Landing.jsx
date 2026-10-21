import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import Icon from './Icon.jsx'
import { Badge, Eyebrow } from './ui/ui.jsx'
import { PROJECT_CREDITS } from './projectCredits.js'
import { useMotionAllowed } from './motionPref.js'
import { tr, useLang } from './i18n.js'

const N_SLIDES = 3
const pad = (n) => String(n).padStart(2, '0')

// Slowly drifting contour lines, drawn from a few sine waves (no image, no library). Decoration only.
function Contours() {
  const paths = useMemo(() => {
    const out = []
    for (let k = 0; k < 16; k++) {
      let d = ''
      for (let x = 0; x <= 1200; x += 30) {
        const y = 40 + k * 38 + Math.sin(x / 150 + k * 0.55) * 26 + Math.sin(x / 61 + k) * 7
        d += `${x === 0 ? 'M' : 'L'}${x} ${y.toFixed(1)}`
      }
      out.push(d)
    }
    return out
  }, [])
  return (
    <svg className="ln-contours" viewBox="0 0 1200 700" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      <g className="ln-contours-drift">
        {paths.map((d, i) => (
          <path key={i} d={d} />
        ))}
      </g>
    </svg>
  )
}

function Headline({ text, accent, ok }) {
  const words = text.split(' ')
  const accentWords = accent.split(' ')
  const all = [...words.map((w) => [w, false]), ...accentWords.map((w) => [w, true])]
  return (
    <h1 className="ln-h1" aria-label={`${text} ${accent}`}>
      {all.map(([w, acc], i) => (
        <motion.span
          key={`${w}-${i}`}
          aria-hidden="true"
          className={acc ? 'ln-word cy-serif' : 'ln-word'}
          initial={ok ? { opacity: 0, y: 18, filter: 'blur(8px)' } : false}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ duration: ok ? 0.6 : 0, delay: ok ? 0.12 + i * 0.09 : 0, ease: [0.2, 0.7, 0.2, 1] }}
        >
          {w}
        </motion.span>
      ))}
    </h1>
  )
}

export default function Landing({ onClose }) {
  const lang = useLang()
  const t = (k, p) => tr(k, p, lang)
  const ok = useMotionAllowed()
  const [i, setI] = useState(0)
  const [dir, setDir] = useState(1)
  const primary = useRef(null)
  const go = (n) => {
    if (n < 0 || n >= N_SLIDES) return
    setDir(n > i ? 1 : -1)
    setI(n)
  }
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'ArrowRight') go(i + 1)
      else if (e.key === 'ArrowLeft') go(i - 1)
      else if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  })
  useEffect(() => {
    primary.current?.focus()
  }, [i])
  const dist = ok ? 36 : 0
  const problems = [
    ['tree', 1],
    ['mappin', 2],
    ['calendar', 3],
  ]
  const steps = [
    ['layers', 1],
    ['sprout', 2],
    ['clipboard', 3],
  ]
  const C = PROJECT_CREDITS
  return (
    <div className="ln-root" role="dialog" aria-modal="true" aria-label={t('ln.label')} data-role="landing" data-slide={i}>
      <Contours />
      <header className="ln-top">
        <span className="ln-brand">
          <Icon name="tree" size={18} /> LGU San Mateo
        </span>
        <span className="ln-counter" aria-live="polite" data-role="ln-counter">
          {pad(i + 1)}/{pad(N_SLIDES)}
        </span>
        {i > 0 ? (
          <button type="button" className="cy-btn cy-btn-quiet" onClick={onClose} data-role="ln-skip">
            {t('ln.skip')}
          </button>
        ) : (
          <span />
        )}
      </header>
      <main className="ln-stage">
        <AnimatePresence mode="wait" initial={false}>
          <motion.section
            key={i}
            className="ln-slide"
            initial={{ opacity: 0, x: dir * dist }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -dir * dist }}
            transition={{ duration: ok ? 0.28 : 0, ease: [0.2, 0.7, 0.2, 1] }}
            aria-roledescription="slide"
            aria-label={`${i + 1} / ${N_SLIDES}`}
          >
            {i === 0 && (
              <div className="ln-hero">
                <Eyebrow items={[t('ln.e1'), t('ln.e2'), t('ln.e3'), t('ln.e4')]} />
                <Badge>{t('ln.badge')}</Badge>
                <Headline text={t('ln.h1')} accent={t('ln.h1a')} ok={ok} />
                <p className="ln-sub">{t('ln.sub')}</p>
                <div className="ln-actions">
                  <button type="button" ref={primary} className="cy-btn cy-btn-primary ln-big" onClick={onClose} data-role="ln-enter">
                    {t('ln.enter')} <Icon name="right" size={16} />
                  </button>
                  <button type="button" className="cy-btn cy-btn-quiet" onClick={onClose} data-role="ln-skip">
                    {t('ln.skip')}
                  </button>
                </div>
              </div>
            )}
            {i === 1 && (
              <div className="ln-text ln-about" data-role="ln-about">
                <h2 className="ln-slogan">{t('ln.a.slogan')}</h2>
                <Eyebrow items={[t('ln.a.pe')]} />
                <ul className="ln-tiles">
                  {problems.map(([icon, k], n) => (
                    <motion.li key={k} initial={ok ? { opacity: 0, y: 12 } : false} animate={{ opacity: 1, y: 0 }} transition={{ duration: ok ? 0.35 : 0, delay: ok ? 0.1 + n * 0.12 : 0 }}>
                      <span className="ln-stepicon">
                        <Icon name={icon} size={22} />
                      </span>
                      <h3>{t(`ln.a.t${k}`)}</h3>
                      <p>{t(`ln.a.l${k}`)}</p>
                    </motion.li>
                  ))}
                </ul>
                <Eyebrow items={[t('ln.a.ae')]} />
                <ol className="ln-steps">
                  {steps.map(([icon, k], n) => (
                    <motion.li key={k} initial={ok ? { opacity: 0, y: 12 } : false} animate={{ opacity: 1, y: 0 }} transition={{ duration: ok ? 0.35 : 0, delay: ok ? 0.45 + n * 0.12 : 0 }}>
                      <span className="ln-stepno">{pad(n + 1)}</span>
                      <span className="ln-stepicon">
                        <Icon name={icon} size={22} />
                      </span>
                      <div>
                        <h3>{t(`ln.a.s${k}`)}</h3>
                        <p>{t(`ln.a.d${k}`)}</p>
                      </div>
                    </motion.li>
                  ))}
                </ol>
                <p className="ln-closing">{t('ln.a.close')}</p>
                <p className="ln-note" data-role="ln-advisory">
                  {t('ln.a.foot')}
                </p>
              </div>
            )}
            {i === 2 && (
              <div className="ln-text ln-credits">
                <Eyebrow items={[t('ln.cr.e')]} />
                <h2>{t('ln.cr.h')}</h2>
                <div className="ln-credgrid">
                  <section>
                    <h3>{t('ln.cr.dev')}</h3>
                    <p>{C.developers.join(' · ')}</p>
                    <p className="muted">
                      {t('ln.cr.adv')}: {C.adviser}
                    </p>
                    <p className="muted">
                      {C.school} · {C.course}
                    </p>
                  </section>
                  <section>
                    <h3>{t('ln.cr.lgu')}</h3>
                    <p>
                      {C.lgu.place}: {C.lgu.offices.join(', ')}
                    </p>
                  </section>
                  <section>
                    <h3>{t('ln.cr.data')}</h3>
                    <ul>
                      {[...C.data, ...C.tools].map(([name, what, lic]) => (
                        <li key={name}>
                          <strong>{name}</strong> — {what}. <span className="muted">{lic}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                </div>
                <p className="ln-note">{t('ln.cr.close')}</p>
                <div className="ln-actions">
                  <button type="button" ref={primary} className="cy-btn cy-btn-primary ln-big" onClick={onClose} data-role="ln-enter">
                    {t('ln.enter')} <Icon name="right" size={16} />
                  </button>
                </div>
              </div>
            )}
          </motion.section>
        </AnimatePresence>
      </main>
      <footer className="ln-foot">
        <button type="button" className="cy-btn" onClick={() => go(i - 1)} disabled={i === 0} data-role="ln-back">
          <Icon name="left" size={16} /> {t('ln.back')}
        </button>
        <div className="ln-dots" role="tablist" aria-label={t('ln.label')}>
          {Array.from({ length: N_SLIDES }, (_, n) => (
            <button key={n} type="button" role="tab" aria-selected={n === i} aria-label={`${n + 1}`} className={`ln-dot ${n === i ? 'is-on' : ''}`} onClick={() => go(n)} />
          ))}
        </div>
        <button type="button" className="cy-btn cy-btn-primary" onClick={() => (i === N_SLIDES - 1 ? onClose() : go(i + 1))} data-role="ln-next">
          {i === N_SLIDES - 1 ? t('ln.enter') : t('ln.next')} <Icon name="right" size={16} />
        </button>
      </footer>
    </div>
  )
}
