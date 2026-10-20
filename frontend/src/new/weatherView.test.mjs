import test from 'node:test'
import assert from 'node:assert/strict'
import { dayAdvice, dayCondition, hourInPhilippines, rainBarPct, timeOfDay } from './weatherView.js'

test('the day condition and the advice come from the rain only, with the service heavy-rain threshold', () => {
  assert.equal(dayCondition(0), 'clear')
  assert.equal(dayCondition(0.9), 'clear')
  assert.equal(dayCondition(1), 'light')
  assert.equal(dayCondition(9.9), 'light')
  assert.equal(dayCondition(10), 'rainy')
  assert.equal(dayCondition(80), 'rainy')
  assert.equal(dayCondition(80.1), 'heavy')
  assert.equal(dayCondition(null), 'none')
  assert.equal(dayCondition(undefined), 'none')
  assert.deepEqual([0, 5, 30, 95, null].map((m) => dayAdvice(m)), ['good', 'good', 'wet', 'postpone', 'none'])
  assert.equal(dayAdvice(60, 50), 'postpone')                                    // a different service threshold is respected
})

test('the sky follows the hour in San Mateo', () => {
  assert.deepEqual([3, 5, 6, 7, 12, 16, 17, 18, 19, 23].map(timeOfDay), ['night', 'dawn', 'dawn', 'day', 'day', 'day', 'dusk', 'dusk', 'night', 'night'])
  const h = hourInPhilippines(new Date('2026-10-21T00:00:00Z'))                  // 08:00 in Manila
  assert.equal(h, 8)
  assert.equal(hourInPhilippines(new Date('2026-10-21T16:30:00Z')), 0)           // 00:30 the next day: hour 0, not 24
})

test('the rain bar is relative to the wettest day, never empty for rain and never above 100', () => {
  assert.equal(rainBarPct(null, 20), 0)
  assert.equal(rainBarPct(0, 20), 0)
  assert.equal(rainBarPct(10, 20), 50)
  assert.equal(rainBarPct(20, 20), 100)
  assert.equal(rainBarPct(5, 0), 50)               // a quiet week still uses 10 mm as the full bar
  assert.equal(rainBarPct(500, 100), 100)
})
