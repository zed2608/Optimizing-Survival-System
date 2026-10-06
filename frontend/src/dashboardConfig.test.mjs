// Tests of dashboardConfig.js. Run: node frontend/src/dashboardConfig.test.mjs (tests/test_dashboard_default.py runs it)
import assert from 'node:assert/strict'
import { chooseDashboard, DEFAULT_DASHBOARD } from './dashboardConfig.js'

assert.equal(DEFAULT_DASHBOARD, 'new')
assert.equal(chooseDashboard(''), 'new')            // no hash: the revamp is the default
assert.equal(chooseDashboard('#'), 'new')
assert.equal(chooseDashboard('#/'), 'new')
assert.equal(chooseDashboard('#/anything-else'), 'new')
assert.equal(chooseDashboard('#/new'), 'new')
assert.equal(chooseDashboard('#/new?x=1'), 'new')
assert.equal(chooseDashboard('#/legacy'), 'legacy') // the old dashboard stays reachable
assert.equal(chooseDashboard('#/v2'), 'v2')
assert.equal(chooseDashboard('', 'legacy'), 'legacy') // the fallback can still be changed by the caller
console.log('dashboardConfig: all tests passed')
