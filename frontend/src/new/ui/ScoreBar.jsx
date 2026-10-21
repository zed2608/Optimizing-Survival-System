import { motion } from 'motion/react'
import { motionAllowed } from '../motionPref.js'

// A score bar that fills when it appears (a spring). value is 0 to 1. The colour is a calm sequential green (the darker the bar, the higher the match); a score of 0 shows an empty track and the words say "not suitable".
// The number is always written next to the bar by the caller: the bar never carries the meaning alone.
export default function ScoreBar({ value, label }) {
  const v = Math.max(0, Math.min(1, Number(value) || 0))
  const step = v >= 0.55 ? 3 : v >= 0.35 ? 2 : v > 0 ? 1 : 0
  const ok = motionAllowed()
  return (
    <span className="cy-scorebar" role="img" aria-label={label} data-step={step}>
      <motion.span
        className="cy-scorebar-fill"
        initial={ok ? { width: '0%' } : false}
        animate={{ width: `${v * 100}%` }}
        transition={ok ? { type: 'spring', stiffness: 110, damping: 20, delay: 0.05 } : { duration: 0 }}
      />
    </span>
  )
}
