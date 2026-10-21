import { useEffect, useId, useRef, useState } from 'react'
import Icon from './Icon.jsx'
import { LANGS, setLang, tr, useLang } from './i18n.js'
import { setTheme, useTheme } from './theme.js'
import { setMotionMode, useMotionMode } from './motionPref.js'

// ONE settings menu in the header (UX revamp v2): theme, language, animations, and the links About this project, Help and Take the tour. It replaces the separate info, theme, language and Help buttons.
function Seg({ label, value, options, onChange, tourId }) {
  return (
    <div className="set-row" data-tour={tourId}>
      <span className="set-label">{label}</span>
      <div className="set-seg" role="radiogroup" aria-label={label}>
        {options.map(([v, text, lang]) => (
          <button key={v} type="button" role="radio" aria-checked={value === v} lang={lang} className={`set-segbtn ${value === v ? 'is-on' : ''}`} onClick={() => onChange(v)} data-value={v}>
            {text}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function SettingsMenu({ onAbout, onHelp, onTour }) {
  const lang = useLang()
  const theme = useTheme()
  const motion = useMotionMode()
  const t = (k) => tr(k, {}, lang)
  const [open, setOpen] = useState(false)
  const root = useRef(null)
  const id = useId()
  useEffect(() => {
    if (!open) return undefined
    const onDoc = (e) => !root.current?.contains(e.target) && setOpen(false)
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])
  const run = (f) => () => {
    setOpen(false)
    f()
  }
  return (
    <div className="set-wrap" ref={root}>
      <button type="button" className="cy-iconbtn set-btn" data-tour="h-settings" aria-haspopup="dialog" aria-expanded={open} aria-controls={id} aria-label={t('set.open')} title={t('set.open')} onClick={() => setOpen((v) => !v)} data-role="settings-open">
        <Icon name="sliders" size={20} />
      </button>
      {open && (
        <div className="set-menu" id={id} role="dialog" aria-label={t('set.title')} data-role="settings-menu">
          <div className="set-title">{t('set.title')}</div>
          <Seg tourId="set-theme" label={t('set.theme')} value={theme} options={[['light', t('set.light')], ['dark', t('set.dark')]]} onChange={setTheme} />
          <Seg tourId="set-lang" label={t('set.lang')} value={lang} options={LANGS.map((l) => [l, tr(`lang.${l}`, {}, l), l === 'tl' ? 'fil' : 'en'])} onChange={setLang} />
          <Seg tourId="set-anim" label={t('set.anim')} value={motion} options={[['auto', t('set.auto')], ['on', t('set.on')], ['off', t('set.off')]]} onChange={setMotionMode} />
          <p className="set-hint">{t('set.animHelp')}</p>
          <div className="set-links">
            <button type="button" className="set-link" onClick={run(onAbout)} data-role="welcome-open" data-tour="set-welcome">
              <Icon name="info" size={16} /> {t('set.about')}
            </button>
            <button type="button" className="set-link" onClick={run(onHelp)} data-role="help-open" data-tour="set-help">
              <Icon name="question" size={16} /> {t('set.help')}
            </button>
            <button type="button" className="set-link" onClick={run(onTour)} data-role="tour-open" data-tour="set-tours">
              <Icon name="target" size={16} /> {t('set.tour')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
