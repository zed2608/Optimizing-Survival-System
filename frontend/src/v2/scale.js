import { W_GOOD, W_MODERATE } from './config.js'

// Colour level of an overall score W. Grey = no data, or the species is not suitable here (S below 0.50 gives W = 0).
export function wLevel(w, eligible = true) {
  if (w === null || w === undefined || Number.isNaN(Number(w)) || eligible === false) return 'none'
  if (w >= W_GOOD) return 'good'
  if (w >= W_MODERATE) return 'moderate'
  return 'poor'
}

export const LEVEL_WORD = { good: 'Good', moderate: 'Moderate', poor: 'Poor', none: 'No data' }

export const LEGEND = [
  { level: 'good', word: 'Good', range: `W ${W_GOOD} or more` },
  { level: 'moderate', word: 'Moderate', range: `W ${W_MODERATE} to below ${W_GOOD}` },
  { level: 'poor', word: 'Poor', range: `W below ${W_MODERATE}` },
  { level: 'none', word: 'No data', range: 'not suitable here, or no value' },
]

export function fmt(v, digits = 2) {
  return v === null || v === undefined || Number.isNaN(Number(v)) ? null : Number(v).toFixed(digits)
}

export function pct(v) {
  return v === null || v === undefined || Number.isNaN(Number(v)) ? null : `${Math.round(Number(v) * 100)}%`
}
