// Builds docs/USER_GUIDE.md from the same text the guided tour and the Help page use (frontend/src/new/tutorial/tutorialContent.js),
// so the printed guide and the in-app help cannot drift apart.
//   node scripts/build_user_guide.mjs           writes docs/USER_GUIDE.md
//   node scripts/build_user_guide.mjs --check   exits 1 if docs/USER_GUIDE.md is out of date (used by tests/test_round16.py)
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { FAQ, GLOSSARY, SCREENS, SECTIONS, TOUR_STEPS } from '../frontend/src/new/tutorial/tutorialContent.js'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const out = join(root, 'docs', 'USER_GUIDE.md')

export function buildGuide() {
  const L = []
  L.push('# Tree Planting Decision Support: user guide')
  L.push('')
  L.push('San Mateo, Rizal. Municipal Environment and Natural Resources Office (MENRO).')
  L.push('')
  L.push('This guide is built from the same text as the in-app tour and the Help page (`frontend/src/new/tutorial/tutorialContent.js`). Do not edit it by hand: change that file and run `node scripts/build_user_guide.mjs`.')
  L.push('')
  L.push('## Contents')
  L.push('')
  L.push('1. [The tour, step by step](#the-tour-step-by-step)')
  L.push('2. [Questions and answers](#questions-and-answers)')
  L.push('3. [Glossary](#glossary)')
  L.push('')
  L.push('## The tour, step by step')
  L.push('')
  let n = 0
  for (const sec of SECTIONS) {
    const steps = TOUR_STEPS.filter((s) => s.section === sec.id)
    if (!steps.length) continue
    L.push(`### ${sec.title}`)
    L.push('')
    for (const s of steps) {
      n += 1
      L.push(`**${n}. ${s.title}** (${SCREENS[s.screen].name})`)
      L.push('')
      L.push(s.text)
      L.push('')
      if (s.watch) {
        L.push(`*Watch for:* ${s.watch}`)
        L.push('')
      }
      if (s.later) {
        L.push(`*${s.later}*`)
        L.push('')
      }
    }
  }
  L.push('## Questions and answers')
  L.push('')
  for (const t of [...new Set(FAQ.map((f) => f.topic))]) {
    L.push(`### ${t}`)
    L.push('')
    for (const f of FAQ.filter((x) => x.topic === t)) {
      L.push(`**${f.q}**`)
      L.push('')
      L.push(f.a)
      L.push('')
    }
  }
  L.push('## Glossary')
  L.push('')
  for (const g of GLOSSARY) L.push(`- **${g.term}**: ${g.meaning}`)
  L.push('')
  return L.join('\n')
}

if (process.argv[1]?.endsWith('build_user_guide.mjs')) {
  const text = buildGuide()
  if (process.argv.includes('--check')) {
    let cur = ''
    try {
      cur = readFileSync(out, 'utf8')
    } catch {
      /* missing file: out of date */
    }
    if (cur !== text) {
      console.error('docs/USER_GUIDE.md is out of date: run node scripts/build_user_guide.mjs')
      process.exit(1)
    }
    console.log('docs/USER_GUIDE.md is up to date')
  } else {
    writeFileSync(out, text, 'utf8')
    console.log(`wrote ${out} (${text.length} characters, ${TOUR_STEPS.length} tour steps, ${FAQ.length} answers)`)
  }
}
