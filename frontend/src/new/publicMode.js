// Public sandbox (GET /health -> public_mode {on, notice, reset_hours}). Nothing is shown when the service is not in sandbox mode.
export function isSandbox(health) {
  return !!health && !!health.public_mode && health.public_mode.on === true
}
export const SANDBOX_NOTICE_HEIGHT = 52
export const FALLBACK_NOTICE_HEIGHT = 28
