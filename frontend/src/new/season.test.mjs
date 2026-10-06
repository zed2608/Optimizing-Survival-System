import test from 'node:test'
import assert from 'node:assert/strict'
import { addDays, defaultWindow, formatRange, localToday, restoreWindow, seasonQuery, validateWindow, windowDays, windowMonths } from './season.js'

test('dates: add days across month and year ends, leap day, and the default window', () => {
  assert.equal(addDays('2026-10-05', 30), '2026-11-04')
  assert.equal(addDays('2026-12-31', 1), '2027-01-01')
  assert.equal(addDays('2028-02-28', 1), '2028-02-29')
  assert.equal(addDays('2026-02-30', 1), null)
  assert.deepEqual(defaultWindow('2026-10-05'), { start: '2026-10-05', end: '2026-11-04' })
  assert.equal(localToday(new Date(2026, 9, 5, 23, 59)), '2026-10-05')
  assert.equal(windowDays('2026-10-05', '2026-10-05'), 1)
  assert.equal(windowDays('2026-01-15', '2027-01-15'), 366)
})

test('validation: past start, end before start, too long, missing, and the good cases', () => {
  const today = '2026-10-05'
  assert.equal(validateWindow('2026-10-05', '2026-11-04', today).ok, true)
  assert.equal(validateWindow('2026-10-05', '2026-10-05', today).ok, true)
  assert.match(validateWindow('2026-10-04', '2026-11-04', today).error, /cannot be in the past/)
  assert.match(validateWindow('2026-11-04', '2026-11-03', today).error, /on or after the start/)
  assert.equal(validateWindow('2026-10-05', '2027-10-05', today).ok, true) // 366 days
  assert.match(validateWindow('2026-10-05', '2027-10-06', today).error, /367 days/)
  assert.match(validateWindow('', '2026-11-04', today).error, /Pick a start date/)
  assert.match(validateWindow('2026-10-05', '2026-13-01', today).error, /Pick a start date/)
})

test('months of a window, including windows that cross the year end', () => {
  assert.deepEqual(windowMonths('2026-10-06', '2026-11-05'), [10, 11])
  assert.deepEqual(windowMonths('2026-11-10', '2027-02-20'), [11, 12, 1, 2])
  assert.deepEqual(windowMonths('2026-12-31', '2027-01-01'), [12, 1])
  assert.deepEqual(windowMonths('2026-03-05', '2026-03-05'), [3])
  assert.equal(windowMonths('2026-01-15', '2027-01-15').length, 12)
  assert.deepEqual(windowMonths('2026-11-05', '2026-11-01'), [])
})

test('wording and the query string', () => {
  assert.equal(formatRange('2026-10-06', '2026-11-05'), '6 Oct to 5 Nov')
  assert.equal(formatRange('2026-11-20', '2027-02-20'), '20 Nov 2026 to 20 Feb 2027')
  assert.equal(seasonQuery({ start: '2026-10-05', end: '2026-11-04' }, true), 'start=2026-10-05&end=2026-11-04&season_filter=only')
  assert.equal(seasonQuery({ start: '2026-10-05', end: '2026-11-04' }, false), 'start=2026-10-05&end=2026-11-04&season_filter=mark')
})

test('a remembered window is used only while it is still valid', () => {
  const today = '2026-10-05'
  assert.deepEqual(restoreWindow({ start: '2026-10-20', end: '2026-12-01' }, today), { start: '2026-10-20', end: '2026-12-01' })
  assert.deepEqual(restoreWindow({ start: '2026-09-01', end: '2026-12-01' }, today), defaultWindow(today))
  assert.deepEqual(restoreWindow({ start: 'x', end: 'y' }, today), defaultWindow(today))
  assert.deepEqual(restoreWindow(null, today), defaultWindow(today))
})

test('the next planting season: the window with the most species fully in season, earliest on ties, never starting in the past', async () => {
  const { bestSeasonWindow, formatSpan, parseMonths, NEXT_SEASON_DAYS } = await import('./season.js')
  assert.equal(NEXT_SEASON_DAYS, 60)
  assert.deepEqual(parseMonths('5;6;7'), [5, 6, 7])
  assert.equal(parseMonths(''), null)
  assert.equal(parseMonths(null), null)
  const species = [[5, 6, 7], [5, 6, 7, 8], [5, 6], [7, 8], null]
  const r = bestSeasonWindow(species, '2026-10-05')
  assert.deepEqual([r.start, r.end, r.count, r.total], ['2027-05-01', '2027-06-29', 3, 5]) // months 5 and 6: three species; 1 May is the earliest such start
  assert.equal(formatSpan(r.start, r.end), '1 May - 29 Jun')
  const inside = bestSeasonWindow(species, '2027-05-01') // today is already the best start
  assert.equal(inside.start, '2027-05-01')
  assert.equal(inside.count, 3)
  assert.equal(bestSeasonWindow(species, '2027-05-10').start, '2028-05-01') // 10 May + 60 days runs into July: the next best start is a year on
  const tie = bestSeasonWindow([[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]], '2026-10-05') // every window is equally good: today
  assert.equal(tie.start, '2026-10-05')
  assert.equal(bestSeasonWindow([null, null], '2026-10-05').count, 0)
  assert.ok(r.start >= '2026-10-05')
})

test('planting dates against the forecast, and campaign status', async () => {
  const { windowForecastMessage, campaignStatus, formatSpanYear, formatBytes } = await import('./season.js')
  assert.equal(formatSpanYear('2027-05-01', '2027-06-29'), '1 May - 29 Jun 2027')
  assert.equal(formatSpanYear('2026-11-20', '2027-02-20'), '20 Nov 2026 - 20 Feb 2027')
  const beyond = windowForecastMessage('2027-05-01', '2027-06-29', '2026-10-05', '2026-10-20')
  assert.equal(beyond.covered, false)
  assert.equal(beyond.message, 'Your planting dates (1 May - 29 Jun 2027) are beyond the 16-day forecast. The advice below is for the next 16 days only.')
  assert.match(windowForecastMessage('2026-09-01', '2026-09-30', '2026-10-05', '2026-10-20').message, /have already passed/)
  const part = windowForecastMessage('2026-10-15', '2026-11-15', '2026-10-05', '2026-10-20')
  assert.deepEqual(part.overlap, { start: '2026-10-15', end: '2026-10-20' })
  assert.match(part.message, /covers 15 Oct - 20 Oct 2026 of your planting dates/)
  assert.match(windowForecastMessage('2026-10-06', '2026-10-10', '2026-10-05', '2026-10-20').message, /covers all of your planting dates/)
  assert.equal(campaignStatus('2026-10-05', '2026-10-05', '2026-10-05'), 'active') // both ends are inclusive
  assert.equal(campaignStatus('2026-10-05', '2026-11-04', '2026-11-04'), 'active')
  assert.equal(campaignStatus('2026-10-06', '2026-11-04', '2026-10-05'), 'upcoming')
  assert.equal(campaignStatus('2026-09-01', '2026-10-04', '2026-10-05'), 'concluded')
  assert.equal(campaignStatus(null, null, '2026-10-05'), 'none')
  assert.equal(formatBytes(2048), '2 KB')
  assert.equal(formatBytes(3 * 1024 * 1024), '3.0 MB')
})
