import test from 'node:test'
import assert from 'node:assert/strict'

test('the theme follows the OS by default, can be chosen, and still works when the browser storage fails', async () => {
  globalThis.matchMedia = () => ({ matches: true, addEventListener() {} })
  globalThis.localStorage = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') }, removeItem() { throw new Error('blocked') } }
  const attrs = {}
  globalThis.document = { documentElement: { setAttribute: (k, v) => (attrs[k] = v), removeAttribute: (k) => delete attrs[k] } }
  const t = await import('./theme.js')
  assert.equal(t.effectiveTheme(), 'dark')            // no stored choice: the OS says dark
  assert.equal(attrs['data-theme'], undefined)
  t.toggleTheme()
  assert.equal(t.effectiveTheme(), 'light')           // chosen although the storage is blocked
  assert.equal(attrs['data-theme'], 'light')
  t.setTheme('dark')
  assert.equal(attrs['data-theme'], 'dark')
  t.setTheme(null)
  assert.equal(attrs['data-theme'], undefined)
  const saved = []
  globalThis.localStorage = { getItem: () => null, setItem: (k, v) => saved.push([k, v]), removeItem: () => {} }
  t.setTheme('light')
  assert.deepEqual(saved, [[t.THEME_KEY, 'light']])
})
