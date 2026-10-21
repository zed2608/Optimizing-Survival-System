// "My location" (UX fix round). Pure helpers, tested in myLocation.test.mjs. The position is only used on this page, in memory: it is never logged and never sent anywhere.
//   findPosition(nav, secure): checks the secure context, asks the device once with a quick low-accuracy request (10 s, a saved position up to 60 s old is fine) and, if that times out, once more with high accuracy (15 s).
//   geoMessageKey(err): the message key for a failure: insecure page, no geolocation in the browser, permission denied (code 1), position unavailable (code 2), timeout (code 3), anything else.
export const FAST = { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
export const PRECISE = { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }

const once = (nav, options) =>
  new Promise((resolve, reject) => {
    nav.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy ?? null }),
      (e) => reject(e),
      options,
    )
  })

export async function findPosition(nav = typeof navigator === 'undefined' ? null : navigator, secure = typeof isSecureContext === 'undefined' ? false : isSecureContext) {
  if (!secure) throw Object.assign(new Error('insecure'), { kind: 'insecure' })
  if (!nav || !nav.geolocation) throw Object.assign(new Error('nogeo'), { kind: 'nogeo' })
  try {
    return await once(nav, FAST)
  } catch (e) {
    if (e && e.code === 3) return once(nav, PRECISE) // the quick request timed out: one more try with high accuracy
    throw e
  }
}

export function geoMessageKey(err) {
  if (err && err.kind === 'insecure') return 'geo.insecure'
  if (err && err.kind === 'nogeo') return 'geo.nogeo'
  if (err && err.code === 1) return 'geo.denied'
  if (err && err.code === 2) return 'geo.unavailable'
  if (err && err.code === 3) return 'geo.timeout'
  return 'geo.unknown'
}
