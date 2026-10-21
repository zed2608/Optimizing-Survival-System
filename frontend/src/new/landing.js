// When to show the landing story: on a user's first visit, or when the last visit was more than 7 days ago. The time of the last visit is kept in the browser inside try/catch; when the storage is blocked
// the story shows once per browser session (a flag in sessionStorage, also inside try/catch; with no storage at all it shows once per page load).
export const VISIT_KEY = 'nw_last_visit'
export const SESSION_KEY = 'nw_landing_session'
export const LANDING_DAYS = 7

export function shouldShowLanding(now = Date.now()) {
  try {
    const raw = localStorage.getItem(VISIT_KEY)
    if (raw === null) return true
    const t = Number(raw)
    return !Number.isFinite(t) || now - t > LANDING_DAYS * 86400000
  } catch {
    /* the local storage is blocked: use the session flag */
  }
  try {
    return sessionStorage.getItem(SESSION_KEY) !== '1'
  } catch {
    return true
  }
}

export function markVisit(now = Date.now()) {
  try {
    localStorage.setItem(VISIT_KEY, String(now))
    return
  } catch {
    /* fall through to the session flag */
  }
  try {
    sessionStorage.setItem(SESSION_KEY, '1')
  } catch {
    /* nothing can be kept: the story shows again on the next load */
  }
}
