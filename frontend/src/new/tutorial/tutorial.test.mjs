import test from 'node:test'
import assert from 'node:assert/strict'
import { ASK_TIPS, FAQ, GLOSSARY, allVisibleText, faqAnswer } from './tutorialContent.js'
import { guideTours } from '../tours/guideText.js'
import { matchFaq } from './faqSearch.js'

test('the guide is built from the tour registry: every tour has sections and every step a title and a text', () => {
  const tours = guideTours()
  assert.ok(tours.length >= 9)
  for (const t of tours) {
    assert.ok(t.sections.length >= 1 && t.title && t.blurb, t.id)
    for (const sec of t.sections) for (const s of sec.steps) {
      assert.ok(s.title.length > 2 && s.text.length > 20, `${t.id}/${s.id} has a title and a text`)
      assert.ok(s.text.split(/[.!?]/).filter(Boolean).length <= 6, `${t.id}/${s.id} is not long-winded`)
    }
  }
})

test('at least 25 help answers, each with a question and an answer', () => {
  assert.ok(FAQ.length >= 25)
  const ids = new Set()
  for (const f of FAQ) {
    assert.ok(f.id && !ids.has(f.id), `unique id ${f.id}`)
    ids.add(f.id)
    assert.ok(f.q.endsWith('?') && f.q.length > 8, `${f.id} question`)
    assert.ok(f.a.length > 30, `${f.id} answer`)
    assert.ok(f.topic, `${f.id} topic`)
  }
  for (const needed of ['grey-point', 'habagat', 'needs-permission', 'record-planted', 'check-code']) assert.ok(ids.has(needed), needed)
  for (const g of GLOSSARY) assert.ok(g.term && g.meaning)
  for (const t of ['Site match', 'Purpose fit', 'Overall match', 'Block', 'Check code', 'Provisional']) assert.ok(GLOSSARY.some((g) => g.term === t), t)
})

test('the question mark tips point to real answers', () => {
  for (const id of Object.values(ASK_TIPS)) assert.ok(FAQ.some((f) => f.id === id), id)
})

test('no visible text has an underscore or an equals sign, or talks about things that are not built', () => {
  for (const t of allVisibleText()) {
    assert.ok(!/[_=]/.test(t), `underscore or equals sign in: ${t.slice(0, 60)}`)
    assert.ok(!/offline|phone app|log in|login|password|mobile app/i.test(t.replace(/If it says offline/g, '')), `not built: ${t.slice(0, 60)}`) // "If it says offline" is the planning-service light of the header
  }
})

test('the help search finds check code and nursery', () => {
  const find = (q) => FAQ.filter((f) => matchFaq(f, q)).map((f) => f.id)
  assert.ok(find('check code').includes('check-code'))
  assert.ok(find('nursery').includes('nursery'))
  assert.ok(find('GREY').includes('grey-point'))
  assert.deepEqual(find('zzzzqqq'), [])
  assert.equal(find('').length, FAQ.length)
})

test('round 21: the scores answer has a rules version for the fallback, and nothing else changes in normal mode', () => {
  const f = FAQ.find((x) => x.id === 'scores')
  assert.ok(/predicted by a Random Forest trained on the expert rules/.test(faqAnswer(f)), 'normal mode keeps the forest sentence')
  assert.equal(faqAnswer(f, false), f.a)
  assert.ok(/Random Forest scores are not loaded, so site suitability comes from the expert rules/.test(faqAnswer(f, true)))
  assert.ok(!/is predicted by a Random Forest/.test(faqAnswer(f, true)), 'the rules version no longer says the forest predicts')
  for (const g of FAQ.filter((x) => x.id !== 'scores')) assert.equal(faqAnswer(g, true), g.a, `${g.id} is the same in both modes`)
})

test('round 21: the wetness wording says the creek and river distance is used and the waterways map is not validated', () => {
  const all = allVisibleText().join(' ')
  assert.ok(!/are not used/.test(all.replace(/not used for the/g, '')), 'no "are not used" sentence about creeks')
  assert.ok((all.match(/soft wetness factor \(50 metres\)/g) ?? []).length >= 2, 'the tour and the signed-off answer')
  assert.ok(/distance to creeks and rivers \(a soft wetness factor, 50 metres/.test(all), 'the glossary')
  assert.ok((all.match(/not (yet )?(been )?validated by MENRO|MENRO has not answered the waterways question/g) ?? []).length >= 3)
  assert.ok(!/zone and rain/.test(all), 'rain is not scored')
})
