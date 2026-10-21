// Coverage registry for the guided tours (R1 W3): every page has a tour, every section the plan asked for has a step, every step has text in both languages and a target that exists in the source.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { TOURS, PAGE_TOUR, tourSteps } from './tourDefs.js'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
const walk = (d) => readdirSync(d).flatMap((f) => (statSync(join(d, f)).isDirectory() ? walk(join(d, f)) : /\.(jsx?|mjs)$/.test(f) && !/\.test\.|tourDefs/.test(f) ? [join(d, f)] : []))
const SOURCE = walk(SRC).map((f) => readFileSync(f, 'utf8')).join('\n')

// what each page tour must explain (the ids of REQUIRED targets, by page)
const REQUIRED = {
  any: ['h-brand', 'h-tabs', 'h-settings'],
  studio: ['s-panel', 's-modes', 's-purposes', 's-dates', 's-species-list', 'a-draw', 'p-create', 's-more', 'm-map', 'm-legend', 'm-search', 'm-mapview', 'r-panel', 'r-verdict', 'r-field', 'r-row', 'c-card', 'r-plan-numbers', 'r-kit', 'r-progress'],
  weather: ['w-where', 'w-purpose', 'w-view', 'w-hero', 'w-strip', 'w-verdict', 'w-best', 'w-source'],
  history: ['l-list'],
  analytics: ['an-filters', 'an-kpis', 'an-c-suit', 'an-c-ph', 'an-c-pvb'],
  help: ['help-search', 'help-faq', 'help-glossary', 'help-print'],
}

test('every page has a tour and every page tour exists', () => {
  for (const [page, id] of Object.entries(PAGE_TOUR)) assert.ok(TOURS.find((t) => t.id === id), `${page} -> ${id}`)
})

test('every step has both languages and a target present in the source', () => {
  for (const t of TOURS) {
    for (const s of tourSteps(t)) {
      assert.ok(s.title?.en && s.title?.tl, `${t.id}/${s.id} title`)
      assert.ok(s.text?.en && s.text?.tl, `${t.id}/${s.id} text`)
      if (s.target) {
        const stem = s.target.replace(/-[^-]*$/, '-')
        assert.ok(SOURCE.includes(`'${s.target}'`) || SOURCE.includes(`"${s.target}"`) || SOURCE.includes('`' + stem) || SOURCE.includes(stem + '$') || SOURCE.includes(s.target) || /-(table|csv)$/.test(s.target), `${t.id}/${s.id}: no element carries data-tour ${s.target}`)
      }
    }
  }
})

test('the required targets of each page are explained by a tour of that page', () => {
  for (const [page, ids] of Object.entries(REQUIRED)) {
    const targets = new Set(TOURS.filter((t) => t.page === page).flatMap((t) => tourSteps(t).map((s) => s.target)))
    for (const id of ids) assert.ok(targets.has(id), `page ${page}: no step explains ${id}`)
  }
})

test('step ids are unique inside a tour', () => {
  for (const t of TOURS) {
    const ids = tourSteps(t).map((s) => s.id)
    assert.equal(new Set(ids).size, ids.length, t.id)
  }
})
