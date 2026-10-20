// "Seen the welcome screen" flag, kept in the browser inside try/catch. When the storage is blocked the welcome shows once per page load and the page still works.
export const WELCOME_KEY = 'nw_welcome_seen'
export function welcomeSeen() {
  try {
    return localStorage.getItem(WELCOME_KEY) === '1'
  } catch {
    return false
  }
}
export function markWelcomeSeen() {
  try {
    localStorage.setItem(WELCOME_KEY, '1')
  } catch {
    /* not saved: it shows again on the next load */
  }
}
