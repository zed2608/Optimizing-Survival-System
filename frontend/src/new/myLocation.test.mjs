import test from 'node:test'
import assert from 'node:assert/strict'
import { FAST, PRECISE, findPosition, geoMessageKey } from './myLocation.js'
import { tr } from './i18n.js'

const POS = { coords: { latitude: 14.69, longitude: 121.12, accuracy: 18 } }
const nav = (script) => {
  const calls = []
  return { calls, geolocation: { getCurrentPosition: (ok, bad, opt) => { calls.push(opt); script[calls.length - 1](ok, bad) } } }
}

test('an insecure page is refused before the device is asked', async () => {
  const n = nav([() => assert.fail('the device must not be asked')])
  await assert.rejects(() => findPosition(n, false), (e) => geoMessageKey(e) === 'geo.insecure')
  assert.equal(n.calls.length, 0)
  await assert.rejects(() => findPosition({}, true), (e) => geoMessageKey(e) === 'geo.nogeo')
  await assert.rejects(() => findPosition(null, true), (e) => geoMessageKey(e) === 'geo.nogeo')
})

test('the first request is quick and low accuracy; a timeout is retried once with high accuracy', async () => {
  const ok = nav([(good) => good(POS)])
  assert.deepEqual(await findPosition(ok, true), { lat: 14.69, lon: 121.12, accuracy: 18 })
  assert.deepEqual(ok.calls, [FAST])
  assert.deepEqual(FAST, { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 })
  assert.deepEqual(PRECISE, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 })
  const retry = nav([(_, bad) => bad({ code: 3 }), (good) => good(POS)])
  assert.equal((await findPosition(retry, true)).lat, 14.69)
  assert.deepEqual(retry.calls, [FAST, PRECISE])
  const twice = nav([(_, bad) => bad({ code: 3 }), (_, bad) => bad({ code: 3 })])
  await assert.rejects(() => findPosition(twice, true), (e) => geoMessageKey(e) === 'geo.timeout')
  assert.equal(twice.calls.length, 2)                                                    // one retry only, never a loop
})

test('denied and unavailable are not retried and have their own message', async () => {
  for (const [code, key] of [[1, 'geo.denied'], [2, 'geo.unavailable']]) {
    const n = nav([(_, bad) => bad({ code })])
    await assert.rejects(() => findPosition(n, true), (e) => geoMessageKey(e) === key)
    assert.equal(n.calls.length, 1)
  }
  assert.equal(geoMessageKey({ code: 99 }), 'geo.unknown')
  assert.equal(geoMessageKey(undefined), 'geo.unknown')
})

test('the plain messages say what to do, in English and in Taglish', () => {
  assert.equal(tr('geo.insecure', {}, 'en'), 'Location needs a secure (HTTPS) page. It works on the live site; this test link is not secure. You can still tap the map to choose where you are.')
  assert.equal(tr('geo.denied', {}, 'en'), 'Location is blocked for this site. Allow it in the browser’s site settings (lock icon), then try again.')
  assert.equal(tr('geo.unavailable', {}, 'en'), 'Your device could not find its position. Turn on Location in system settings, then try again.')
  assert.equal(tr('geo.timeout', {}, 'en'), 'Finding your position took too long. Try again, or tap the map.')
  assert.equal(tr('geo.outside', {}, 'en'), 'You are outside San Mateo.')
  for (const k of ['geo.insecure', 'geo.denied', 'geo.unavailable', 'geo.timeout', 'geo.nogeo', 'geo.unknown', 'geo.outside', 'geo.finding', 'geo.setOnMap', 'geo.setHint', 'geo.set']) {
    assert.ok(tr(k, {}, 'tl') !== k && tr(k, {}, 'tl') !== tr(k, {}, 'en') || k === 'geo.nogeo', k)
  }
})
