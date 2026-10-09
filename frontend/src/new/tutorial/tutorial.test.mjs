import test from 'node:test'
import assert from 'node:assert/strict'
import { ASK_TIPS, FAQ, GLOSSARY, SCREENS, SECTIONS, TOUR_STEPS, allVisibleText } from './tutorialContent.js'
import { matchFaq } from './faqSearch.js'

test('every tour step has the fields the tour needs', () => {
  const ids = new Set()
  for (const s of TOUR_STEPS) {
    assert.ok(s.id && !ids.has(s.id), `unique id ${s.id}`)
    ids.add(s.id)
    assert.ok(s.title.length > 2 && s.text.length > 20, `${s.id} has a title and a text`)
    assert.ok(SECTIONS.some((x) => x.id === s.section), `${s.id} has a known section`)
    assert.ok(SCREENS[s.screen], `${s.id} has a known screen`)
    assert.ok(s.target === null || typeof s.target === 'string', `${s.id} target`)
    if (s.missing === 'center') assert.ok(s.later && s.later.length > 10, `${s.id} says when the element appears`)
    assert.ok(s.text.split(/[.!?]/).filter(Boolean).length <= 6, `${s.id} is not long-winded`)
  }
})

test('every part of the tour (a to m) has at least one step, in order', () => {
  assert.equal(SECTIONS.length, 13)
  let last = -1
  for (const s of TOUR_STEPS) {
    const k = SECTIONS.findIndex((x) => x.id === s.section)
    assert.ok(k >= last, `${s.id} is in order`)
    last = k
  }
  for (const sec of SECTIONS) assert.ok(TOUR_STEPS.some((s) => s.section === sec.id), `${sec.id} has a step`)
})

test('every screen has a quick-tour step', () => {
  for (const k of Object.keys(SCREENS)) assert.ok(TOUR_STEPS.some((s) => s.screen === k), k)
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
    assert.ok(!/offline|phone app|log in|login|password|mobile app/i.test(t), `not built: ${t.slice(0, 60)}`)
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
