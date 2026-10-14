// Everything the "link for the planter" box decides, as small pure functions (tested in planterLink.test.mjs): the address to show, the time the link stops, the state of the box and its words.
// The words are in English with the same sentence in Filipino under it (the dashboard has no language switch). Short sentences, everyday words.

export const TEXT = {
  make: { en: 'Make a link for the planter', fil: 'Gumawa ng link para sa planter' },
  making: { en: 'Making the link… a few seconds', fil: 'Ginagawa ang link… ilang segundo' },
  again: { en: 'Make a new link', fil: 'Gumawa ng bagong link' },
  copy: { en: 'Copy', fil: 'Kopyahin' },
  copied: { en: 'Copied', fil: 'Nakopya na' },
  off: { en: 'Switch off this link', fil: 'Patayin ang link' },
  offAsk: { en: 'Switch off this link? Anyone who has it will see "Not found".', fil: 'Patayin ang link? Makikita ng sinumang may hawak nito ang "Not found".' },
  offYes: { en: 'Yes, switch it off', fil: 'Oo, patayin' },
  offNo: { en: 'No, keep it', fil: 'Hindi, panatilihin' },
  retry: { en: 'Try again', fil: 'Subukan ulit' },
  warn: {
    en: 'The link also stops when the server restarts. Tell the planter to save the results file before leaving.',
    fil: 'Mawawala rin ang link kapag nag-restart ang server. Sabihan ang planter na i-save ang results file bago umalis.',
  },
  qrLabel: { en: 'QR code of the planter link', fil: 'QR code ng link para sa planter' },
  localOnly: {
    en: 'This address works only on this computer. A phone needs the public address of the system.',
    fil: 'Sa computer na ito lang gumagana ang address na ito. Kailangan ng phone ang public address ng system.',
  },
  hint: { en: 'Scan the QR code with the phone, or send the link.', fil: 'I-scan ang QR code gamit ang phone, o ipadala ang link.' },
}

// The address a phone must open: the service's own address (API_BASE) when the dashboard is served from another one (development), else the page's own address.
export function fullUrl(apiBase, origin, path) {
  const base = (apiBase || origin || '').replace(/\/+$/, '')
  return `${base}${path}`
}

export function isLocalAddress(url) {
  try {
    const h = new URL(url).hostname
    return h === 'localhost' || h === '::1' || h === '[::1]' || /^127\./.test(h) || h === '0.0.0.0'
  } catch {
    return false
  }
}

// "14:20" (the local time of the viewer) and how long from now, in plain words.
export function expiryInfo(expiresAt, now = new Date()) {
  const t = new Date(expiresAt)
  if (Number.isNaN(t.getTime())) return null
  const minutes = Math.round((t.getTime() - new Date(now).getTime()) / 60000)
  const clock = `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`
  const sameDay = t.toDateString() === new Date(now).toDateString()
  const when = sameDay ? clock : `${clock} (${t.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })})`
  let left
  if (minutes <= 0) left = 'now'
  else if (minutes < 60) left = `${minutes} min`
  else left = `${Math.round(minutes / 6) / 10} h`.replace('.0 h', ' h')
  return { when, left, minutes, expired: minutes <= 0 }
}

export function expiryLines(expiresAt, now = new Date()) {
  const e = expiryInfo(expiresAt, now)
  if (!e) return null
  return {
    en: `This link will stop working at ${e.when} (in ${e.left}).`,
    fil: `Mawawala ang link na ito sa ${e.when} (sa loob ng ${e.left}).`,
  }
}

// The state of the box from what the page knows: { making, error, info } -> 'making' | 'error' | 'live' | 'none'.
export function boxState({ making = false, error = '', info = null }) {
  if (making) return 'making'
  if (error) return 'error'
  if (info && info.live && info.url) return 'live'
  return 'none'
}
