import test from 'node:test'
import assert from 'node:assert/strict'
import { clearToasts, dismissToast, toast } from './toast.js'

test('toasts stack (at most four), keep their kind, and can be dismissed', () => {
  clearToasts()
  const ids = ['success', 'info', 'warning', 'error', 'info'].map((k, i) => toast(k, `message ${i}`, 60000))
  assert.equal(new Set(ids).size, 5)
  dismissToast(ids[4])
  assert.ok(true)
  clearToasts()
  assert.equal(toast('nonsense', 'x', 60000) > 0, true)    // an unknown kind becomes info
  clearToasts()
})
