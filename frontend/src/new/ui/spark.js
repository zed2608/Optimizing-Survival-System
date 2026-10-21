/*
 * Adapted from the ClickSpark idea of React Bits (David Haz, https://github.com/DavidHDev/react-bits, MIT with Commons Clause). Rewritten for this project: a few small elements fly out of a point and fade
 * (CSS animation, no canvas, no dependency). The licence header is kept as the author asks. It is decoration only and is skipped when motion is not allowed.
 */
import { motionAllowed } from '../motionPref.js'

export function sparkBurst(el, n = 10) {
  if (!el || typeof document === 'undefined' || !motionAllowed()) return
  const r = el.getBoundingClientRect()
  const cx = r.left + r.width / 2
  const cy = r.top + r.height / 2
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n
    const s = document.createElement('span')
    s.className = 'cy-spark'
    s.style.left = `${cx}px`
    s.style.top = `${cy}px`
    s.style.setProperty('--dx', `${Math.cos(a) * (38 + (i % 3) * 8)}px`)
    s.style.setProperty('--dy', `${Math.sin(a) * (38 + (i % 3) * 8)}px`)
    s.setAttribute('aria-hidden', 'true')
    document.body.appendChild(s)
    setTimeout(() => s.remove(), 700)
  }
}
