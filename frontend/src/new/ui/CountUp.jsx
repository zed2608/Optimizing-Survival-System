import { useEffect, useRef, useState } from 'react'

// A figure that counts up to its value in about 600 ms (decorative). The final text is always the exact value; with reduced motion, or for a value that is not a plain number, it is shown at once.
export default function CountUp({ value, ms = 600 }) {
  const n = Number(value)
  const plain = Number.isFinite(n) && String(value).trim() !== ''
  const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
  const [shown, setShown] = useState(plain && !reduce ? 0 : n)
  const frame = useRef(0)
  useEffect(() => {
    if (!plain || reduce) return undefined
    const t0 = performance.now()
    const dec = String(value).includes('.') ? String(value).split('.')[1].length : 0
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / ms)
      const e = 1 - (1 - k) ** 3
      setShown(k >= 1 ? n : Number((n * e).toFixed(dec)))
      if (k < 1) frame.current = requestAnimationFrame(tick)
    }
    frame.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame.current)
  }, [n, plain, reduce, ms, value])
  const text = plain && !reduce ? shown : value
  return <span data-count-to={plain ? n : undefined}>{typeof text === 'number' && Number.isInteger(text) ? text.toLocaleString('en-US') : text}</span>
}
