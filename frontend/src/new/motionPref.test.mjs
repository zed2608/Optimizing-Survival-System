import test from 'node:test'
import assert from 'node:assert/strict'

test('Animations: Auto follows the OS, On overrides it, and a blocked storage does not break it', async () => {
  globalThis.matchMedia = () => ({ matches: true })                        // the OS asks for reduced motion
  globalThis.localStorage = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') }, removeItem() { throw new Error('blocked') } }
  const attrs = {}
  globalThis.document = { documentElement: { setAttribute: (k, v) => (attrs[k] = v), removeAttribute: (k) => delete attrs[k] } }
  const m = await import('./motionPref.js')
  assert.equal(m.getMotionMode(), 'auto')
  assert.equal(m.motionAllowed(), false)                                    // Auto + OS reduced = no motion
  m.setMotionMode('on')
  assert.equal(m.motionAllowed(), true)
  assert.equal(attrs['data-motion'], 'on')
  m.setMotionMode('auto')
  assert.equal(attrs['data-motion'], undefined)
  globalThis.matchMedia = () => ({ matches: false })
  assert.equal(m.motionAllowed(), true)                                     // Auto + OS fine = motion
  const saved = []
  globalThis.localStorage = { getItem: () => null, setItem: (k, v) => saved.push([k, v]), removeItem: () => {} }
  m.setMotionMode('on')
  assert.deepEqual(saved, [[m.MOTION_KEY, 'on']])
})
