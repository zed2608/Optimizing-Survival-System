// Pure helpers of the Weather view (UX revamp, Phase 7). Everything is derived from the fields /weather/week returns: rain_mm, tmax_c, tmin_c per day and the service's own heavy-rain threshold.
// Nothing here invents humidity, wind, UV or a chance of rain: the forecast does not carry them. The day words and the advice rules are fixed and shown on the page; they are advisory.
export const RAIN_LIGHT_MM = 1 // display choices (the service has no threshold below the heavy-rain one): dry under 1 mm, light rain 1 to 10 mm, rainy 10 mm or more
export const RAIN_RAINY_MM = 10

// 'clear' | 'light' | 'rainy' | 'heavy' | 'none' (no value: never a guess)
export function dayCondition(mm, heavy = 80) {
  if (mm === null || mm === undefined || Number.isNaN(Number(mm))) return 'none'
  if (mm > heavy) return 'heavy'
  if (mm >= RAIN_RAINY_MM) return 'rainy'
  if (mm >= RAIN_LIGHT_MM) return 'light'
  return 'clear'
}

// The advice key of one day, from its rain only. Keys are messages in messages.js (wx.adv.*).
export function dayAdvice(mm, heavy = 80) {
  return { clear: 'good', light: 'good', rainy: 'wet', heavy: 'postpone', none: 'none' }[dayCondition(mm, heavy)]
}

// 'dawn' | 'day' | 'dusk' | 'night' from an hour of the day (0-23).
export function timeOfDay(hour) {
  if (hour >= 5 && hour < 7) return 'dawn'
  if (hour >= 7 && hour < 17) return 'day'
  if (hour >= 17 && hour < 19) return 'dusk'
  return 'night'
}

// The hour in San Mateo (Philippine time), whatever the clock of the device says.
export function hourInPhilippines(date = new Date()) {
  try {
    const h = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Manila', hour: 'numeric', hour12: false }).format(date)
    return Number(h) % 24
  } catch {
    return date.getHours()
  }
}

// The width of a rain bar in percent: the day's rain against the wettest day of the week (at least 10 mm so that a drizzle never looks like a flood).
export function rainBarPct(mm, weekMax) {
  if (mm === null || mm === undefined) return 0
  const top = Math.max(RAIN_RAINY_MM, weekMax ?? 0)
  return Math.max(0, Math.min(100, (mm / top) * 100))
}
