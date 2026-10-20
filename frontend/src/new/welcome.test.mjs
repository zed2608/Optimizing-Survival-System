import test from 'node:test'
import assert from 'node:assert/strict'
import { WELCOME_KEY, markWelcomeSeen, welcomeSeen } from './welcome.js'

test('the welcome flag works with a storage, and the page works without one', () => {
  const store = {}
  globalThis.localStorage = { getItem: (k) => store[k] ?? null, setItem: (k, v) => (store[k] = v) }
  assert.equal(welcomeSeen(), false)
  markWelcomeSeen()
  assert.equal(store[WELCOME_KEY], '1')
  assert.equal(welcomeSeen(), true)
  globalThis.localStorage = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') } }
  assert.equal(welcomeSeen(), false)
  assert.doesNotThrow(() => markWelcomeSeen())
  delete globalThis.localStorage
  assert.equal(welcomeSeen(), false)
})
