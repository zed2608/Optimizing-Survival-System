import test from 'node:test'
import assert from 'node:assert/strict'
import { LANDING_DAYS, SESSION_KEY, VISIT_KEY, markVisit, shouldShowLanding } from './landing.js'

const DAY = 86400000

test('the landing shows on a first visit and after more than 7 days, and not in between', () => {
  const store = {}
  globalThis.localStorage = { getItem: (k) => store[k] ?? null, setItem: (k, v) => (store[k] = v) }
  const now = 1_800_000_000_000
  assert.equal(shouldShowLanding(now), true)                       // first visit
  markVisit(now)
  assert.equal(store[VISIT_KEY], String(now))
  assert.equal(shouldShowLanding(now + 2 * DAY), false)
  assert.equal(shouldShowLanding(now + LANDING_DAYS * DAY), false) // exactly 7 days: not yet
  assert.equal(shouldShowLanding(now + LANDING_DAYS * DAY + 1), true)
  store[VISIT_KEY] = 'junk'
  assert.equal(shouldShowLanding(now), true)                       // an unreadable value counts as a first visit
})

test('with the browser storage blocked it shows once per session, and with no storage once per load', () => {
  const blocked = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') } }
  globalThis.localStorage = blocked
  const sess = {}
  globalThis.sessionStorage = { getItem: (k) => sess[k] ?? null, setItem: (k, v) => (sess[k] = v) }
  assert.equal(shouldShowLanding(), true)
  markVisit()
  assert.equal(sess[SESSION_KEY], '1')
  assert.equal(shouldShowLanding(), false)
  globalThis.sessionStorage = blocked
  assert.equal(shouldShowLanding(), true)
  assert.doesNotThrow(() => markVisit())
  delete globalThis.localStorage
  delete globalThis.sessionStorage
})
