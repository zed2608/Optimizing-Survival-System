// node --test src/new/weatherText.test.mjs : the "no weather now" message (C3).
import test from 'node:test'
import assert from 'node:assert/strict'
import { weatherError as weatherErrorIn } from './weatherText.js'
import { setLang } from './i18n.js'
setLang('tl') // V2: the sentence is in messages.js; these tests pin the Taglish sentence, the English one is checked at the end
const WEATHER_UNREACHABLE = 'Hindi maabot ang weather ngayon. Subukan ulit mamaya.'
const weatherError = (e) => weatherErrorIn(e, 'tl')

test('the plain Filipino sentence is exactly the agreed one', () => {
  assert.equal(weatherErrorIn(null, 'tl').main, WEATHER_UNREACHABLE)
  assert.equal(weatherErrorIn(null, 'en').main, 'The weather cannot be reached now. Try again later.')
})

test('no network, and a 503 from the service (no forecast and no saved copy), both say it plainly and keep the reason under it', () => {
  const a = weatherError({ network: true, status: null, message: 'The planning service could not be reached at http://x.' })
  assert.equal(a.unreachable, true)
  assert.equal(a.main, WEATHER_UNREACHABLE)
  assert.match(a.detail, /could not be reached/)
  const b = weatherError({ network: false, status: 503, message: 'The weather forecast service (Open-Meteo) could not be reached and there is no cached forecast for this place yet. Try again later.' })
  assert.equal(b.main, WEATHER_UNREACHABLE)
  assert.match(b.detail, /Open-Meteo/)
})

test('another error (a place outside San Mateo, too many requests) keeps its own message and is not called unreachable', () => {
  const c = weatherError({ network: false, status: 422, message: 'The coordinate is outside the San Mateo area.' })
  assert.equal(c.unreachable, false)
  assert.equal(c.main, 'The coordinate is outside the San Mateo area.')
  assert.equal(c.detail, '')
  assert.equal(weatherError({ network: false, status: 429, message: 'Too many requests.' }).unreachable, false)
})

test('a missing error object never throws and never invents a reason', () => {
  assert.equal(weatherError(null).main, WEATHER_UNREACHABLE)
  assert.equal(weatherError(undefined).detail, '')
})
