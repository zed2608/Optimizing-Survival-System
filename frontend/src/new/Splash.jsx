import { useEffect, useState } from 'react'
import { tr, useLang } from './i18n.js'

// The short branded splash of every load (UX revamp, Phase 5): tree rings pulse and a sapling grows, drawn in SVG and CSS. It goes as soon as the app is ready (the service answered), after at least
// 400 ms so that it does not flash, and never stays longer than 1.5 s. With reduced motion it is shown without any animation.
export default function Splash({ ready }) {
  const lang = useLang()
  const [minDone, setMinDone] = useState(false)
  const [maxDone, setMaxDone] = useState(false)
  const [gone, setGone] = useState(false)
  useEffect(() => {
    const a = setTimeout(() => setMinDone(true), 400)
    const b = setTimeout(() => setMaxDone(true), 1500)
    return () => {
      clearTimeout(a)
      clearTimeout(b)
    }
  }, [])
  const out = maxDone || (ready && minDone)
  useEffect(() => {
    if (!out) return undefined
    const t = setTimeout(() => setGone(true), 260)
    return () => clearTimeout(t)
  }, [out])
  if (gone) return null
  return (
    <div className={`cy-splash ${out ? 'is-out' : ''}`} role="status" aria-label={tr('splash.label', {}, lang)} data-role="splash">
      <svg viewBox="0 0 120 120" width="120" height="120" aria-hidden="true">
        <circle className="cy-ring cy-ring-3" cx="60" cy="60" r="52" />
        <circle className="cy-ring cy-ring-2" cx="60" cy="60" r="40" />
        <circle className="cy-ring cy-ring-1" cx="60" cy="60" r="28" />
        <path className="cy-sapling" d="M60 84V52M60 66c-10 0-16-6-17-15 10 0 16 5 17 15zM60 60c9-1 15-6 17-14-10 0-16 5-17 14z" />
      </svg>
      <div className="cy-splash-title">{tr('splash.title', {}, lang)}</div>
    </div>
  )
}
