// The guided flow of the field pack in headless Edge, in BOTH languages (Filipino is the default, English the other) at 360 x 640 and 390 x 844, with a FAKE GPS (tiles intercepted: no map server is contacted).
// Not run by pytest by default (see tests/test_field_pack_browser.py).   node tests/browser/fieldpack_check.mjs <page: a file path or an http address> <folder for pictures>
// Intro cards on the first visit, the landing page (how to use, before you go, Start, Help, language switch kept after a reload), Help on every screen, the four steps with the REAL numbers of the block
// (spacing, paces, trees per row, the offset of tree 1, the next tree, row and place), far / close / here in words, planted / skipped / undo, the results file, and no visible null / undefined / missing text.
import { pathToFileURL } from 'node:url'
import { resolve } from 'node:path'
import { launch } from './cdp_lib.mjs'

const target = process.argv[2]
const url = /^https?:/.test(target) ? target : pathToFileURL(resolve(target)).href
const b = await launch({ out: process.argv[3] })
const { ev, text, tap, check, sleep, waitFor, waitExpr, gps, noBadText } = b
b.tileMode = 'ok'

const WORDS = {
  fil: { how: 'Paano gamitin', before: 'Bago kayo umalis', start: 'Simulan', help: 'Tulong', skip: 'Laktawan', planted: 'Naitanim na', skipBtn: 'Laktawan', gpsStart: 'Simulan ang GPS', close: 'Isara', back: 'Balik', goStart: 'Nasa START na ako',
         stake: 'Naitusok ko na ang istaka', nextStep: 'Susunod na hakbang', undo: 'Ibalik', rock: 'Bato o gilid ng bangin', here: 'Nasa START na kayo', far: 'Malayo pa sa START', closeTo: 'Malapit na sa START', save: 'I-save ang file ng resulta', step: (n) => `Hakbang ${n} sa 4`, fix: 'Sigurado ang telepono hanggang mga', intro1: 'Ano ang ginagawa ng page na ito', honest: 'Madalas na lampas o kulang ng 3 hanggang 10 m', swEn: 'English', next: 'Susunod', done: 'Sige, naintindihan ko', card2a: '3 hanggang 10 m', card2b: '3 hanggang 20 m', card3: 'Naka-save ang inyong gawa', title: 'Gabay sa pagtatanim' },
  en: { how: 'How to use', before: 'Before you go', start: 'Start', help: 'Help', skip: 'Skip', planted: 'Planted', skipBtn: 'Skip', gpsStart: 'Start GPS', close: 'Close', back: 'Back', goStart: 'I am at START',
        stake: 'I put the stake', nextStep: 'Next step', undo: 'Undo', rock: 'Rock or ledge', here: 'You are at START', far: 'Far from START', closeTo: 'Close to START', save: 'Save results file', step: (n) => `Step ${n} of 4`, fix: 'The phone is sure to about', intro1: 'What this page does', honest: 'usually 3 to 10 m off', swEn: 'English', next: 'Next', done: 'Got it', card2a: '3 to 10 m', card2b: '3 to 20 m', card3: 'Your work is saved', title: 'Planting guide' },
}
const numbers = (s) => (s.match(/\d+(?:\.\d+)?/g) || []).map(Number)
const sameList = (a, c) => a.length === c.length && a.every((x, i) => Math.abs(x - c[i]) < 1e-9)
const paces = (m) => Math.max(1, Math.round(m / 0.75))

for (const lang of ['fil', 'en']) {
  for (const [W, H] of [[360, 640], [390, 844]]) {
    const w = WORDS[lang]
    const tag = `${lang} ${W}x${H}: `
    await b.viewport(W, H)
    await b.open(url)
    await ev('sessionStorage.clear(); localStorage.clear()')
    if (lang === 'en') await ev(`localStorage.setItem('fieldpack:prefs', JSON.stringify({ v: 1, observer: '', trees: {}, prefs: { lang: 'en' } }))`)
    await b.open(url)

    // ---- first visit: Filipino by default (English when it was chosen), and the 3-card intro that can be skipped
    check(tag + 'first visit: the page is in ' + (lang === 'fil' ? 'Filipino (the default)' : 'English (chosen)'), (await ev(`document.documentElement.lang`)) === lang && (await text()).includes(w.title))
    check(tag + 'first visit: a 3-card intro opens, with a Next and a Skip button', await ev(`document.querySelector('.overlay[data-kind="intro"]') !== null && document.querySelectorAll('.overlay .card').length === 1 && document.querySelectorAll('.overlay .btn').length === 2`))
    check(tag + 'intro card 1 says what the page does', (await text()).includes(w.intro1))
    await noBadText(tag + 'intro card 1')
    await b.shot(`flow_${lang}_${W}_0_intro`)
    await tap(w.next); await sleep(200)
    check(tag + 'intro card 2 is the honest one (GPS is 3 to 10 m off, trees 3 to 20 m apart)', (await text()).includes(w.card2a) && (await text()).includes(w.card2b))
    await tap(w.next); await sleep(200)
    check(tag + 'intro card 3 says the work is saved on the phone, and the last button closes the intro', (await text()).includes(w.card3))
    await tap(w.done); await sleep(300)
    check(tag + 'the intro closes and is not shown again after a reload', !(await ev(`!!document.querySelector('.overlay')`)))
    await b.send('Page.reload'); await sleep(1300)
    check(tag + 'after a reload: no intro, and the same language', !(await ev(`!!document.querySelector('.overlay')`)) && (await ev(`document.documentElement.lang`)) === lang)
    if (W === 360) { // the intro can also be skipped
      await ev(`localStorage.clear()`)
      if (lang === 'en') await ev(`localStorage.setItem('fieldpack:prefs', JSON.stringify({ v: 1, observer: '', trees: {}, prefs: { lang: 'en' } }))`)
      await b.send('Page.reload'); await sleep(1300)
      await tap(lang === 'fil' ? 'Laktawan' : 'Skip'); await sleep(300)
      check(tag + 'the intro can be skipped from the first card', !(await ev(`!!document.querySelector('.overlay')`)))
    }

    // ---- landing page
    await sleep(200)
    const landing = await ev(`JSON.stringify({ steps: document.querySelectorAll('ol.steps li').length, checks: document.querySelectorAll('.checklist li').length, startBtn: [...document.querySelectorAll('button')].some((x) => x.textContent.trim() === ${JSON.stringify(w.start)}), helpBtn: [...document.querySelectorAll('button')].some((x) => x.textContent.trim() === ${JSON.stringify(w.help)}), sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, honest: document.querySelector('.honest')?.innerText || '' })`)
    const L = JSON.parse(landing)
    check(tag + 'landing: "' + w.how + '" with 4 numbered steps, "' + w.before + '" with a 5-item checklist, a Start button and a Help button', L.steps === 4 && L.checks === 5 && L.startBtn && L.helpBtn && (await text()).includes(w.how) && (await text()).includes(w.before))
    check(tag + 'landing: no sideways scroll', L.sw <= L.cw, `${L.sw}/${L.cw}`)
    check(tag + 'landing: the first-aid checklist names Chrome or Safari, Location, a charged phone, a tape and the team leader', lang === 'fil' ? /Chrome o Safari/.test(await text()) && /Lokasyon/.test(await text()) && /power bank/.test(await text()) && /panukat/.test(await text()) && /lider ng grupo/.test(await text()) : /Chrome or Safari/.test(await text()) && /Location/.test(await text()) && /power bank/.test(await text()) && /tape measure/.test(await text()) && /team leader/.test(await text()))
    await noBadText(tag + 'the landing page')
    const sizes = await ev(`JSON.stringify([...document.querySelectorAll('button, input[type=checkbox]')].filter((e) => e.id !== 'bannerclose' && e.getBoundingClientRect().width > 0).map((e) => Math.min(e.getBoundingClientRect().width, e.getBoundingClientRect().height)).sort((a, c) => a - c).slice(0, 3))`)
    check(tag + 'landing: buttons are at least 48 px (the checklist ticks are 28 px but their whole line is 48 px)', JSON.parse(sizes)[0] >= 27, sizes)
    check(tag + 'landing: the language switch has both languages and shows the one in use', await ev(`(() => { const b = [...document.querySelectorAll('.lang .langbtn')]; return b.length === 2 && b.find((x) => x.dataset.lang === ${JSON.stringify(lang)}).getAttribute('aria-pressed') === 'true' })()`))
    check(tag + 'the prototype notice is visible on first load, in this language', await ev(`(() => { const e = document.getElementById('banner'); return !e.hidden && e.getBoundingClientRect().height > 0 && e.innerText.length > 20 })()`))
    await b.shot(`flow_${lang}_${W}_1_landing`)

    // ---- language switch remembered
    if (lang === 'fil') {
      await tap('English'); await sleep(300)
      check(tag + 'switching to English changes the words at once', (await text()).includes('How to use') && (await ev('document.documentElement.lang')) === 'en')
      await b.send('Page.reload'); await sleep(1300)
      check(tag + 'English is remembered after a reload', (await text()).includes('How to use'))
      await tap('Filipino'); await sleep(300)
      check(tag + 'and back to Filipino', (await text()).includes('Paano gamitin'))
    }

    // ---- help from every screen
    const helpWorks = async (where) => {
      await tap(w.help); await sleep(300)
      const ok = await ev(`(() => { const o = document.querySelector('.overlay[data-kind="help"]'); if (!o) return 'no overlay'; const t = o.innerText; return JSON.stringify({ trouble: o.querySelectorAll('.trouble').length, how: o.querySelectorAll('ol.steps li').length, gps: t.includes(${JSON.stringify(w.honest)}), fits: o.querySelector('.overlaybox').getBoundingClientRect().right <= innerWidth + 1 }) })()`)
      const j = ok.startsWith('{') ? JSON.parse(ok) : null
      check(tag + 'Help opens on ' + where + ' with the 4 "if something goes wrong" topics, the how-to, and the honest GPS line', !!j && j.trouble === 4 && j.how === 4 && j.gps && j.fits, ok)
      await noBadText(tag + 'Help on ' + where)
      await tap(w.close); await sleep(250)
      check(tag + 'Help closes on ' + where, !(await ev(`!!document.querySelector('.overlay')`)))
    }
    await helpWorks('the landing page')
    await b.shot(`flow_${lang}_${W}_2_help`)
    await tap(w.start); await sleep(300)

    // ---- home
    await helpWorks('the block list')
    check(tag + 'home: no sideways scroll, the name field is 16 px, block cards with a progress bar', await ev(`document.documentElement.scrollWidth <= document.documentElement.clientWidth && parseFloat(getComputedStyle(document.getElementById('observer')).fontSize) >= 16 && document.querySelectorAll('.bcard .bar').length === 6`))
    await noBadText(tag + 'the block list')
    await ev("document.getElementById('observer').value = 'Flow Tester'; document.getElementById('observer').dispatchEvent(new Event('input', { bubbles: true }))")
    const pack = JSON.parse(await ev("document.getElementById('pack-data').textContent"))
    const blk = pack.blocks[0]
    const off = blk.first_offset_m, sp = blk.spacing_m
    await tap(blk.ref)
    await waitExpr(`document.querySelectorAll('#map .treeicon').length === ${blk.n}`)
    await sleep(500)

    // ---- step 1: go to the START corner (GPS arrow and words: far / close / here)
    await helpWorks('the block screen')
    check(tag + 'step 1 is shown first for a new block, with the plain title and the step counter', (await text()).includes(w.step(1)) && (await ev(`document.querySelector('.steptitle').textContent.includes('1')`)))
    check(tag + 'step 1: the Start GPS button is visible without scrolling and not hidden under the main button', await ev(`(() => { const g = [...document.querySelectorAll('button')].find((x) => x.textContent.trim() === ${JSON.stringify(w.gpsStart)}); if (!g) return false; const r = g.getBoundingClientRect(); const p = document.querySelector('.btnrow').getBoundingClientRect(); return r.bottom <= p.top + 1 && r.height >= 48 })()`))
    await noBadText(tag + 'step 1 before GPS')
    await tap(w.gpsStart)
    await noBadText(tag + 'step 1 just after tapping Start GPS')
    const S = blk.start
    await gps(S[0] + 0.00036, S[1], 6) // 40 m north of START
    await waitFor(new RegExp(w.far))
    let sheet = await ev(`document.querySelector('.sheet').innerText`)
    check(tag + 'step 1: far from START, in words, with the distance', sheet.includes(w.far) && /40 m/.test(sheet), sheet.replace(/\n+/g, ' | ').slice(0, 170))
    check(tag + 'step 1: the direction is said in words (south), not as letters or degrees', lang === 'fil' ? /timog \(south\)/.test(sheet) : /Go south/.test(sheet))
    check(tag + 'step 1: it says how sure the phone is, in plain words', sheet.includes(w.fix) && /6 m/.test(sheet))
    check(tag + 'step 1: the words "accuracy" and "bearing" are not used', !/accuracy|bearing/i.test(sheet))
    await gps(S[0] + 0.00013, S[1], 6) // about 14 m from START
    await waitFor(new RegExp(w.closeTo))
    check(tag + 'step 1: within 30 m it says "close"', (await text()).includes(w.closeTo))
    await gps(S[0], S[1], 3)
    await waitFor(new RegExp(w.here))
    check(tag + 'step 1: on the corner it says "you are at START"', (await text()).includes(w.here))
    await noBadText(tag + 'step 1 with a GPS reading')
    await b.shot(`flow_${lang}_${W}_3_step1`)
    await tap(w.goStart); await sleep(400)

    // ---- step 2: the stake and tree 1, with the real numbers
    check(tag + 'step 2 is shown', (await text()).includes(w.step(2)))
    const t2 = await ev(`document.querySelector('.steptext').textContent`)
    check(tag + `step 2: tree 1 at ${off[0]} m east and ${off[1]} m north, about ${paces(off[0])} and ${paces(off[1])} paces (the numbers of this block)`, sameList(numbers(t2), [1, off[0], off[1], paces(off[0]), paces(off[1])]), t2)
    check(tag + 'step 2: says the map is only approximate and the tape sets the spot', /approximate|Tinatayang/.test(await ev(`document.querySelector('.sheet').innerText`)))
    await noBadText(tag + 'step 2')
    await tap(w.stake); await sleep(400)

    // ---- step 3: walk and plant; the next tree; the drawing
    check(tag + 'step 3 is shown, with the little drawing of the block', (await text()).includes(w.step(3)) && (await ev(`!!document.querySelector('.mini svg') && !document.querySelector('.mini').hidden`)))
    const t3 = await ev(`document.querySelector('.steptext').textContent`)
    check(tag + `step 3: walk east every ${sp} m (about ${paces(sp)} paces), the row is full after ${blk.per_row} trees, go north ${sp} m`, sameList(numbers(t3), [sp, paces(sp), blk.per_row, sp]), t3)
    check(tag + 'step 3: "next tree 1 of N, row 1 place 1"', sameList(numbers(await ev(`document.querySelector('.nextline').textContent`)), [1, blk.n, 1, 1]), await ev(`document.querySelector('.nextline').textContent`))
    check(tag + 'step 3: the sheet says the map is approximate', (await ev(`document.querySelector('.sheet').innerText`)).includes(lang === 'fil' ? 'Tinatayang lugar lang' : 'approximate place'))
    await noBadText(tag + 'step 3')
    await tap(w.planted); await sleep(400)
    check(tag + 'step 3: after Planted the next tree is 2 and the top bar counts 1', sameList(numbers(await ev(`document.querySelector('.nextline').textContent`)), [2, blk.n, 1, 2]) && numbers(await ev(`document.querySelector('.topbar .done').textContent`))[0] === 1)
    await tap(w.skipBtn); await sleep(300)
    check(tag + 'skip: the reasons are in plain words', (await text()).includes(w.rock) && (await ev(`document.querySelectorAll('.reasons .btn').length`)) === 8)
    check(tag + 'skip: it says what to do if something blocks the spot (move up to 10 m, never plant on paved land)', /10 m/.test(await ev(`document.querySelector('.sheet').innerText`)) && (await ev(`document.querySelector('.sheet').innerText`)).length > 0)
    await tap(w.rock); await sleep(400)
    check(tag + 'skipped: tree 3 is next, "2 of N" in the top bar', sameList(numbers(await ev(`document.querySelector('.nextline').textContent`)), [3, blk.n, 1, 3]) && numbers(await ev(`document.querySelector('.topbar .done').textContent`))[0] === 2)
    check(tag + 'marking never asks "are you sure you are at the tree?" (the tape decides, not the GPS)', b.dialogs.length === 0, JSON.stringify(b.dialogs))
    await b.shot(`flow_${lang}_${W}_4_step3`)

    // ---- step 4: count, chips, undo
    await tap(w.nextStep); await sleep(400)
    check(tag + 'step 4: the counts (planted, skipped, still to do) and the chips of all trees', sameList(numbers(await ev(`document.querySelector('.steptext').textContent`)), [1, 1, blk.n - 2]) && (await ev(`document.querySelectorAll('.chip').length`)) === blk.n, await ev(`document.querySelector('.steptext').textContent`))
    await tap('3'); await sleep(200)
    await tap(w.planted); await sleep(300)
    await tap('1'); await sleep(250)
    await tap(w.undo); await sleep(300)
    check(tag + 'step 4: choose a tree with its chip, mark it, undo another one', numbers(await ev(`document.querySelector('.topbar .done').textContent`))[0] === 2, await ev(`document.querySelector('.topbar .done').textContent`))
    await noBadText(tag + 'step 4')
    check(tag + 'blocks screen: no sideways scroll, no page scroll, the map fills the screen', await ev(`document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight + 1 && document.querySelector('.stage').getBoundingClientRect().bottom >= innerHeight - 1`))
    const bs = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('.stage button, .topbar button')].filter((e) => e.getBoundingClientRect().width > 0 && !e.disabled).map((e) => Math.min(e.getBoundingClientRect().width, e.getBoundingClientRect().height)).sort((a, c) => a - c).slice(0, 2))`))
    check(tag + 'block screen: every button is at least 48 px', bs[0] >= 47.5, JSON.stringify(bs))
    await b.shot(`flow_${lang}_${W}_5_step4`)

    // ---- the marks stay after a reload; the results file
    await b.send('Page.reload'); await sleep(1500)
    await tap(w.start); await sleep(300)
    await tap(blk.ref)
    await waitExpr(`document.querySelectorAll('.chip').length === ${blk.n}`)
    check(tag + 'after a reload the marks and the step are still there (step 4, 2 done)', numbers(await ev(`document.querySelector('.topbar .done').textContent`))[0] === 2 && (await text()).includes(w.step(4)))
    await tap(w.back); await sleep(300)
    await ev("window.__blobs = []; const o = URL.createObjectURL.bind(URL); URL.createObjectURL = (x) => { window.__blobs.push(x); return o(x) }")
    await tap(w.save)
    await sleep(500)
    const csv = await ev('window.__blobs[0] ? window.__blobs[0].text() : null')
    check(tag + 'a results file was made', !!csv)
    if (csv) {
      const lines = csv.replace(/^﻿/, '').trim().split(/\r?\n/)
      const parse = (line) => { const out = []; let cur = '', q = false; for (let i = 0; i < line.length; i++) { const c = line[i]; if (q) { if (c === '"' && line[i + 1] === '"') { cur += '"'; i++ } else if (c === '"') q = false; else cur += c } else if (c === '"') q = true; else if (c === ',') { out.push(cur); cur = '' } else cur += c } out.push(cur); return out }
      const head = parse(lines[0]), r1 = parse(lines[1]), col = (n) => head.indexOf(n)
      check(tag + 'results file: blocks.csv columns first, one row per block, in English whatever the language', lines.length === pack.blocks.length + 1 && head.slice(0, pack.columns.length).join(',') === pack.columns.join(','))
      check(tag + 'results file: block 1 planted with its count, by the name typed, plan and check code kept', r1[col('status')] === 'planted' && Number(r1[col('trees_planted')]) >= 1 && r1[col('observer')] === 'Flow Tester' && r1[col('plan_id')] === pack.plan_id && r1[col('check_code')] === pack.check_code)
      check(tag + 'results file: the English prototype notice is in every row', lines.slice(1).every((l) => parse(l)[col('pack_notice')].startsWith('Prototype. GPS accuracy not yet field-tested.')))
      check(tag + 'results file: moved_lat and moved_lon stay empty', lines.slice(1).every((l) => parse(l)[col('moved_lat')] === '' && parse(l)[col('moved_lon')] === ''))
    }
    await noBadText(tag + 'the block list after marking')
  }
}
check('no uncaught page errors during the whole run', b.events.length === 0, b.events.length ? JSON.stringify(b.events[0].params.exceptionDetails).slice(0, 200) : '')
await b.done('flow_report')
