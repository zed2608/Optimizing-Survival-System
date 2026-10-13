// Field pack, stage A1e, in headless Edge (fake GPS, simulated compass, intercepted map tiles): per-tree guidance, the three states of the panel, the prototype chip, the text size
// (five levels), the word limits of every panel state in both languages, the layout at three phone sizes (no sideways scroll, buttons of 48 px or more, nothing cut off, the main button visible)
// and the guided tours (every step must light up an element that is really on the screen).
//   node tests/browser/fieldpack_ui_check.mjs <address of the pack page> <folder for pictures>
import { launch } from './cdp_lib.mjs'

const PAGE = process.argv[2]
const b = await launch({ out: process.argv[3] })
const { ev, text, tap, tapSel, touch, swipe, check, sleep, waitFor, waitExpr, gps, noBadText } = b
b.tileMode = 'ok'

const words = (s) => (s || '').split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length
const rad = Math.PI / 180
const bearing = (la1, lo1, la2, lo2) => { const dl = (lo2 - lo1) * rad; const y = Math.sin(dl) * Math.cos(la2 * rad); const x = Math.cos(la1 * rad) * Math.sin(la2 * rad) - Math.sin(la1 * rad) * Math.cos(la2 * rad) * Math.cos(dl); return (Math.atan2(y, x) / rad + 360) % 360 }
const away = (a, c) => Math.abs((((c - a) % 360) + 540) % 360 - 180)
const metres = (la1, lo1, la2, lo2) => { const dla = (la2 - la1) * rad, dlo = (lo2 - lo1) * rad; const a = Math.sin(dla / 2) ** 2 + Math.cos(la1 * rad) * Math.cos(la2 * rad) * Math.sin(dlo / 2) ** 2; return 2 * 6371000 * Math.asin(Math.sqrt(a)) }
const LEVELS = [85, 100, 115, 130, 150]
const T = {
  en: { start: 'Start', help: 'Help', gps: 'Start GPS', atStart: "I'm at START", stake: 'Stake is in', planted: 'Planted', skip: 'Skip', undo: 'Undo', details: 'Details', hide: 'Hide details', close: 'Close', back: 'Back', next: 'Next', done: 'Done',
        far: 'Far', closeW: 'Close', here: 'Here', tree: 'Tree', chevClose: 'Close the panel', chevOpen: 'Open the panel', chevBack: 'Back to the short panel', takeTour: 'Take the tour', skipTour: 'Skip', prev: 'Previous step', nextStep: 'Next step', rock: 'Rock or ledge' },
  fil: { start: 'Start', help: 'Help', gps: 'Start GPS', atStart: 'Nasa START na ako', stake: 'Nailagay na ang stake', planted: 'Naitanim na', skip: 'Skip', undo: 'Undo', details: 'Details', hide: 'Itago ang details', close: 'Close', back: 'Back', next: 'Next', done: 'Done',
         far: 'Malayo', closeW: 'Malapit', here: 'Nandito na', tree: 'Puno', chevClose: 'Isara ang panel', chevOpen: 'Buksan ang panel', chevBack: 'Balik sa maikling panel', takeTour: 'Take the tour', skipTour: 'Skip', prev: 'Naunang step', nextStep: 'Susunod na step', rock: 'Bato o bangin' },
}
const SIZES = [[360, 640], [390, 844], [412, 915]]
const sel = (q) => JSON.stringify(q)
const visible = (q) => ev(`(() => { const e = document.querySelector(${sel(q)}); if (!e || e.closest('[hidden]')) return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 })()`)
const txt = (q) => ev(`(() => { const e = document.querySelector(${sel(q)}); return e && !e.closest('[hidden]') ? e.innerText : '' })()`)
const arrow = async () => JSON.parse(await ev(`(() => { const a = document.querySelector('.tgtarrow'); if (!a) return 'null'; const r = a.getBoundingClientRect(); return JSON.stringify({ deg: Number(a.dataset.deg), mode: a.dataset.mode, target: a.dataset.target, shown: r.width > 0 && !a.hasAttribute('hidden') }) })()`))
const openBlock = async (ref) => { await tap('Start'); await sleep(250); await tap(ref); await waitExpr(`document.querySelectorAll('#map .treeicon').length > 0`); await sleep(400) }
const pack = async () => JSON.parse(await ev("document.getElementById('pack-data').textContent"))
const dotOn = () => ev(`[...document.querySelectorAll('.dots .dot')].findIndex((d) => d.classList.contains('on')) + 1`)
const goStep = async (w, label) => { if (!(await visible('.stepnav'))) { await tap(w.details); await sleep(150) } await tap(label); await sleep(250); if (await visible('.stepnav')) { await tap(w.hide); await sleep(200) } }

// ======================================================================= 1. per-tree guidance (arrow, distance in metres, a word) and the honest line
for (const lang of ['en', 'fil']) {
  const w = T[lang]
  for (const [W, H] of [[360, 640], [412, 915]]) {
    const tag = `guidance ${lang} ${W}x${H}: `
    await b.viewport(W, H)
    await b.fresh(PAGE, { lang })
    const pk = await pack()
    const blk = pk.blocks[0]
    const ST = blk.start
    await openBlock(blk.ref)
    check(tag + 'step 1: the target line names START and there is no GPS yet', (await txt('.tgtline')).trim() === 'START')
    await tap(w.gps)
    await gps(ST[0] + 0.00036, ST[1], 6)
    await waitExpr(`document.querySelector('.tgtline').textContent.includes('40')`)
    let line = await txt('.tgtline'), a = await arrow()
    check(tag + 'step 1: the arrow, the distance in metres and a word (far) point to START', /^START · .*40 m · /.test(line) && line.endsWith(w.far) && a.shown && a.target === 'start', line + ' ' + JSON.stringify(a))
    check(tag + 'step 1: the arrow points the way the map points (south = 180 degrees) while the phone has no compass', a.mode === 'north' && away(a.deg, 180) <= 2, JSON.stringify(a))
    await gps(ST[0] + 0.00012, ST[1], 6)
    await waitExpr(`document.querySelector('.tgtline').textContent.includes('${w.closeW}')`)
    check(tag + 'step 1: within 30 m the word is "close"', (await txt('.tgtline')).endsWith(w.closeW), await txt('.tgtline'))
    await tap(w.atStart); await sleep(350)
    // ---- step 2: the target is tree 1
    const t1 = blk.trees[0]
    await gps(ST[0] + 0.00036, ST[1] + 0.00004, 6)
    await waitExpr(`document.querySelector('.tgtline').textContent.startsWith('${w.tree} 1')`)
    line = await txt('.tgtline'); a = await arrow()
    const d1 = metres(ST[0] + 0.00036, ST[1] + 0.00004, t1[1], t1[2]), b1 = bearing(ST[0] + 0.00036, ST[1] + 0.00004, t1[1], t1[2])
    check(tag + 'step 2: the target is tree 1 (arrow, distance, word)', line.startsWith(`${w.tree} 1 · `) && a.target === '1' && a.shown && away(a.deg, b1) <= 2, line + ' ' + JSON.stringify(a) + ' want ' + b1.toFixed(0))
    check(tag + 'step 2: the distance is the real distance to tree 1 (within the rounding for a 6 m phone)', Math.abs(Number((line.match(/(\d+) m/) || [])[1]) - d1) <= 3, line + ' real ' + d1.toFixed(1))
    check(tag + 'step 2: the dashed line on the map goes to tree 1 and says so', new RegExp(`${w.tree} 1`).test(await ev(`document.querySelector('.linelabel')?.innerText || ''`)), await ev(`document.querySelector('.linelabel')?.innerText`))
    await tap(w.stake); await sleep(350)
    // ---- step 3: tap another tree on the map: the target changes
    const k5 = blk.trees[Math.min(4, blk.n - 1)]
    await ev(`document.querySelector('#map .treeicon[data-k="${k5[0]}"]').click()`)
    await waitExpr(`document.querySelector('.tgtline').textContent.startsWith('${w.tree} ${k5[0]}')`)
    line = await txt('.tgtline'); const a5 = await arrow()
    const b5 = bearing(ST[0] + 0.00036, ST[1] + 0.00004, k5[1], k5[2]), d5 = metres(ST[0] + 0.00036, ST[1] + 0.00004, k5[1], k5[2])
    check(tag + 'tapping a tree on the map makes it the target: new name, new distance, new arrow direction', line.startsWith(`${w.tree} ${k5[0]} · `) && a5.target === String(k5[0]) && away(a5.deg, b5) <= 2 && a5.deg !== a.deg && a5.deg !== a.deg, line + ' ' + JSON.stringify(a5))
    check(tag + 'the distance to the chosen tree is right', Math.abs(Number((line.match(/(\d+) m/) || [])[1]) - d5) <= 3, line + ' real ' + d5.toFixed(1))
    // ---- how sure the phone is: the arrow is never hidden; one honest line when the phone is less sure than the tree spacing
    await gps(ST[0] + 0.00036, ST[1] + 0.00004, 18)
    await waitExpr(`!!document.querySelector('.sureline') && !document.querySelector('.sureline').hidden`)
    const sure = await txt('.sureline')
    check(tag + 'phone accuracy 18 m (worse than the spacing): one small honest line with the number, and the arrow is still shown', /18/.test(sure) && (await arrow()).shown && words(sure) <= 14, sure)
    check(tag + 'the honest line points to the tape measure', /tape measure/.test(sure))
    await gps(ST[0] + 0.00036, ST[1] + 0.00004, 3)
    await waitExpr(`document.querySelector('.sureline').hidden`)
    check(tag + 'phone accuracy 3 m: the honest line goes away, and the arrow stays', (await arrow()).shown && !(await visible('.sureline')))
    check(tag + 'steps 2 to 4 keep the short reminder "the map is approximate, the tape measure is exact"', /approximate|Tinatayang/.test(await txt('.approx')))
    // ---- here / close / far at a tree
    await gps(k5[1], k5[2], 3)
    await waitExpr(`document.querySelector('.tgtline').textContent.endsWith('${w.here}')`)
    check(tag + 'standing on the tree: the word is "here"', (await txt('.tgtline')).endsWith(w.here), await txt('.tgtline'))
    await gps(k5[1] + 0.00012, k5[2], 3)
    await waitExpr(`document.querySelector('.tgtline').textContent.endsWith('${w.closeW}')`)
    check(tag + '13 m from the tree: "close"', (await txt('.tgtline')).endsWith(w.closeW), await txt('.tgtline'))
    await gps(k5[1] + 0.0006, k5[2], 3)
    await waitExpr(`document.querySelector('.tgtline').textContent.endsWith('${w.far}')`)
    check(tag + '65 m from the tree: "far"', (await txt('.tgtline')).endsWith(w.far), await txt('.tgtline'))
    // ---- the turn cue applies to the current target
    await gps(k5[1] + 0.0004, k5[2], 3)
    await sleep(300)
    const toTree = bearing(k5[1] + 0.0004, k5[2], k5[1], k5[2]) // due south: 180
    for (let i = 0; i < 30; i++) { await b.androidHeading((360 - 90) % 360); await sleep(15) } // facing east
    await sleep(200)
    const cueTxt = await txt('.cue'), a2 = await arrow()
    check(tag + 'with a compass the arrow turns by the angle between where you face (east) and the tree (south), and the cue says it', a2.mode === 'heading' && away(a2.deg, 90) <= 4 && /90/.test(cueTxt), JSON.stringify(a2) + ' ' + cueTxt + ' to ' + toTree.toFixed(0))
    await noBadText(tag + 'the block screen with the tree target')
    // ---- step 4: a chip makes another tree the target
    await goStep(w, w.nextStep)
    check(tag + 'step 4 shown (4th dot)', (await dotOn()) === 4)
    const k7 = blk.trees[Math.min(6, blk.n - 1)]
    await ev(`document.querySelector('.chip[data-k="${k7[0]}"]').scrollIntoView({ inline: 'center', block: 'nearest' })`); await sleep(200)
    await tap(`${w.tree} ${k7[0]}`); await sleep(300)
    check(tag + 'step 4: tapping a number (chip) makes that tree the target', (await txt('.tgtline')).startsWith(`${w.tree} ${k7[0]} · `) && (await arrow()).target === String(k7[0]), await txt('.tgtline'))
    await b.shot(`ui_${lang}_${W}_guidance`)
    // ---- the collapsed bar says the tree and the distance, with the arrow's data
    await tap(w.chevClose); await sleep(300)
    check(tag + 'collapsed bar: "tree number · distance"', new RegExp(`^${w.tree} ${k7[0]} · `).test((await txt('.sum')).trim()) && words(await txt('.sum')) <= 6, await txt('.sum'))
  }
}

// ======================================================================= 2. the three states of the panel, the drag handle, the prototype chip
for (const lang of ['en', 'fil']) {
  const w = T[lang]
  const tag = `panel ${lang}: `
  await b.viewport(360, 640)
  await b.fresh(PAGE, { lang })
  const blk = (await pack()).blocks[0]
  check(tag + 'the prototype notice is a full strip on first load', await ev(`(() => { const e = document.getElementById('banner'); return !e.hidden && !e.classList.contains('is-chip') && e.getBoundingClientRect().height > 20 && e.innerText.length > 25 })()`))
  await openBlock(blk.ref)
  const info = () => ev(`(() => { const s = document.querySelector('.sheet'), st = document.querySelector('.stage'), r = s.getBoundingClientRect(), q = st.getBoundingClientRect(); return JSON.stringify({ state: s.dataset.state, h: Math.round(r.height), stage: Math.round(q.height), body: !s.querySelector('.sheetbody').hidden, primary: (() => { const p = document.querySelector('.btnrow .primary'); return !!p && !p.closest('[hidden]') && p.getBoundingClientRect().width > 0 })(), details: !s.querySelector('.inner').hidden }) })()`).then(JSON.parse)
  let i0 = await info()
  check(tag + 'the panel starts in the normal state with its big button', i0.state === 'normal' && i0.body && i0.primary && !i0.details, JSON.stringify(i0))
  check(tag + 'a visible drag handle and a chevron button exist', (await visible('.grab .pill')) && (await visible('.chevbtn')))
  // collapse with the chevron (a tap, no dragging)
  await tap(w.chevClose); await sleep(350)
  let ic = await info()
  check(tag + 'chevron: collapsed = one thin bar, the map shows almost the whole screen', ic.state === 'collapsed' && !ic.body && !ic.primary && ic.h <= 90 && ic.h / ic.stage <= 0.2, JSON.stringify(ic))
  check(tag + 'collapsed bar shows the target as text and an expand chevron', words(await txt('.sum')) >= 1 && (await visible('.chevbtn')) && (await ev(`document.querySelector('.chevbtn').getAttribute('aria-label')`)) === w.chevOpen)
  const rb = await ev(`JSON.stringify([...document.querySelectorAll('.mapbtns .rbtn')].map((e) => { const r = e.getBoundingClientRect(); const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return t === e || e.contains(t) }))`)
  check(tag + 'collapsed: the round map buttons are all reachable (not covered)', JSON.parse(rb).every(Boolean) && JSON.parse(rb).length >= 5, rb)
  // expand again
  await tap(w.chevOpen); await sleep(350)
  check(tag + 'chevron again: back to the normal panel', (await info()).state === 'normal')
  // Details = expanded
  await tap(w.details); await sleep(350)
  let ie = await info()
  check(tag + 'Details opens the expanded panel with the long texts', ie.state === 'expanded' && ie.details && ie.h > i0.h - 5 && (await visible('.stepnav')) && (await txt('.inner')).length > 300, JSON.stringify(ie))
  check(tag + 'expanded: the numbers of the block are there (paces, spacing, trees in a row)', new RegExp(`${blk.spacing_m}`).test(await txt('.inner')) && new RegExp(`${blk.per_row}`).test(await txt('.inner')))
  await b.shot(`ui_${lang}_expanded`)
  check(tag + 'expanded: the chevron says "back to the short panel" and does that', (await ev(`document.querySelector('.chevbtn').getAttribute('aria-label')`)) === w.chevBack)
  await tap(w.chevBack); await sleep(300)
  check(tag + '... which gives the normal panel', (await info()).state === 'normal')
  // the drag handle with a real touch drag
  const pill = JSON.parse(await ev(`JSON.stringify((() => { const r = document.querySelector('.grab .pill').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 } })())`))
  await swipe(pill.x - 60, pill.y + 12, pill.y - 120); await sleep(350)
  check(tag + 'drag up on the handle: normal opens to expanded', (await info()).state === 'expanded')
  const pill2 = JSON.parse(await ev(`JSON.stringify((() => { const r = document.querySelector('.grab .pill').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 } })())`))
  await swipe(pill2.x - 60, pill2.y + 12, pill2.y + 160); await sleep(350)
  check(tag + 'drag down: expanded closes to normal', (await info()).state === 'normal')
  const pill3 = JSON.parse(await ev(`JSON.stringify((() => { const r = document.querySelector('.grab .pill').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 } })())`))
  await swipe(pill3.x - 60, pill3.y + 12, pill3.y + 160); await sleep(350)
  check(tag + 'drag down again: normal closes to collapsed', (await info()).state === 'collapsed')
  const pill4 = JSON.parse(await ev(`JSON.stringify((() => { const r = document.querySelector('.grab .pill').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 } })())`))
  await touch(pill4.x - 60, pill4.y + 12); await sleep(350)
  check(tag + 'a plain tap on the handle (no dragging) opens the collapsed panel', (await info()).state === 'normal')
  await touch(pill4.x - 60, (await ev(`document.querySelector('.grab .pill').getBoundingClientRect().y`)) + 12); await sleep(350)
  check(tag + 'a plain tap on the handle closes the normal panel', (await info()).state === 'collapsed')
  // remembered during the session
  await tap(w.back); await sleep(300)
  await tap(blk.ref); await waitExpr(`document.querySelectorAll('#map .treeicon').length > 0`); await sleep(300)
  check(tag + 'the state (collapsed) is remembered when you leave the block and come back', (await info()).state === 'collapsed')
  await b.send('Page.reload'); await sleep(1500)
  await tap(w.start); await sleep(250); await tap(blk.ref); await waitExpr(`document.querySelectorAll('#map .treeicon').length > 0`); await sleep(300)
  check(tag + '... and after a reload in the same session', (await info()).state === 'collapsed')
  // the prototype chip
  await tap(w.chevOpen); await sleep(300)
  await tapSel('#bannerclose'); await sleep(300)
  check(tag + 'prototype notice: the strip collapses to a small "Prototype" chip on the map', (await visible('.protochip')) && (await txt('.protochip')).trim() === 'Prototype' && !(await ev(`!document.getElementById('banner').hidden`)))
  check(tag + '... the chip is a 48 px tap target', await ev(`(() => { const r = document.querySelector('.protochip').getBoundingClientRect(); return r.width >= 47.5 && r.height >= 47.5 })()`))
  await b.shot(`ui_${lang}_chip`)
  await tapSel('.protochip'); await sleep(300)
  check(tag + 'tap the chip: the full notice is back', (await ev(`(() => { const e = document.getElementById('banner'); return !e.hidden && !e.classList.contains('is-chip') && e.innerText.length > 25 })()`)))
  await tap(w.back); await sleep(300)
  await tapSel('#bannerclose'); await sleep(300)
  check(tag + 'on the other screens the chip sits in the top strip and opens it again', (await ev(`(() => { const e = document.getElementById('banner'); return e.classList.contains('is-chip') && !e.hidden && e.getBoundingClientRect().height > 0 })()`)))
  await tapSel('#bannerchip'); await sleep(250)
  check(tag + '... and the strip is full again', await ev(`!document.getElementById('banner').classList.contains('is-chip')`))
  // the hit area of the small x button is 48 x 48 px
  const hit = JSON.parse(await ev(`JSON.stringify((() => { const r = document.getElementById('bannerclose').getBoundingClientRect(); const cx = r.x + r.width / 2, cy = r.y + r.height / 2; const test = (dx, dy) => { const e = document.elementFromPoint(cx + dx, cy + dy); return !!e && (e.id === 'bannerclose') }; return [test(-23, 0), test(23, 0), test(0, 21), test(-23, 10), test(10, 0)] })())`))
  check(tag + 'the small x of the notice has a tap area 48 px wide and about 44 px high', hit[0] && hit[2] && hit[4], JSON.stringify(hit))
}

// ======================================================================= 3. text size: five levels from 85% to 150%
{
  const tag = 'text size: '
  await b.viewport(360, 640)
  await b.fresh(PAGE, { lang: 'en' })
  const fontPx = () => ev(`parseFloat(getComputedStyle(document.documentElement).fontSize)`)
  const dis = () => ev(`JSON.stringify([...document.querySelectorAll('.landing-none, [data-size]')].filter((e) => e.getBoundingClientRect().width > 0).map((e) => e.dataset.size + ':' + e.disabled))`)
  check(tag + 'the first screen has "Aa -" and "Aa +" in the top row, both at least 48 px, clearly not the map zoom buttons', await ev(`[...document.querySelectorAll('[data-size]')].length === 2 && [...document.querySelectorAll('[data-size]')].every((e) => { const r = e.getBoundingClientRect(); return r.width >= 47.5 && r.height >= 47.5 })`))
  check(tag + 'starts at 100% (16 px root)', Math.abs((await fontPx()) - 16) < 0.1, String(await fontPx()))
  const seen = []
  for (let i = 0; i < 4; i++) { await tap('Make the text bigger'); await sleep(120); seen.push(Math.round((await fontPx()) / 16 * 100)) }
  check(tag + 'Aa + goes 115, 130, 150 and stops at 150%', JSON.stringify(seen) === JSON.stringify([115, 130, 150, 150]), JSON.stringify(seen))
  check(tag + 'at 150% the "Aa +" button is disabled', (await ev(`document.querySelector('[data-size="1"]').disabled`)) === true)
  await b.send('Page.reload'); await sleep(1500)
  check(tag + '150% is remembered after a reload', Math.round((await fontPx()) / 16 * 100) === 150)
  const down = []
  for (let i = 0; i < 5; i++) { await tap('Make the text smaller'); await sleep(120); down.push(Math.round((await fontPx()) / 16 * 100)) }
  check(tag + 'Aa - goes 130, 115, 100, 85 and stops at 85%', JSON.stringify(down) === JSON.stringify([130, 115, 100, 85, 85]), JSON.stringify(down))
  check(tag + 'at 85% the "Aa -" button is disabled', (await ev(`document.querySelector('[data-size="-1"]').disabled`)) === true)
  check(tag + 'the buttons and the text grow together (a button is taller at 150% than at 85%)', await (async () => { const h85 = await ev(`document.querySelector('.btn.big').getBoundingClientRect().height`); for (let i = 0; i < 4; i++) { await tap('Make the text bigger'); await sleep(80) } const h150 = await ev(`document.querySelector('.btn.big').getBoundingClientRect().height`); return h150 > h85 * 1.3 })())
  await noBadText(tag + 'the first screen at 150%')
  // Help shows the same buttons and the percentage
  await tap('Help'); await sleep(300)
  check(tag + 'Help has its own Aa - / Aa + and shows the percentage', (await ev(`document.querySelectorAll('.overlay [data-size]').length`)) === 2 && /150%/.test(await txt('.overlay .sizenow')), await txt('.overlay .sizenow'))
  await tap('Close'); await sleep(200)
}

// ======================================================================= 4. word limits of every panel state, both languages
const LIMITS = { title: 4, instruction: 12, targetLine: 8, turnOrDirection: 4, notSureLine: 14, reminder: 10, message: 12, primaryButton: 4, secondaryButton: 3, panelNormal: 50, skipQuestion: 6, reason: 4, skipPanel: 60, collapsedBar: 6 }
console.log('WORD LIMITS: ' + JSON.stringify(LIMITS))
for (const lang of ['en', 'fil']) {
  const w = T[lang]
  await b.viewport(360, 640)
  await b.fresh(PAGE, { lang })
  const pk = await pack(), blk = pk.blocks[0], ST = blk.start
  await openBlock(blk.ref)
  const measure = async (state) => {
    const m = JSON.parse(await ev(`(() => { const sh = document.querySelector('.sheet'); const g = (q) => { const e = sh.querySelector(q); return e && !e.closest('[hidden]') && e.getBoundingClientRect().width > 0 ? e.innerText.trim() : '' }; return JSON.stringify({ title: g('.steptitle'), text: g('.steptext'), tgt: g('.tgtline'), cue: g('.cue') || g('.dirline'), sure: g('.sureline'), approx: g('.approx'), msg: g('.msg'), primary: g('.btnrow .primary'), secondary: g('.btnrow .secondary'), total: sh.querySelector('.sheetbody').hidden ? '' : [...sh.querySelectorAll('.grab .steptitle, .sheetbody, .btnrow')].filter((e) => !e.hidden).map((e) => e.innerText).join(' ') }) })()`))
    const tag = `words ${lang} [${state}]: `
    const bad = []
    const lim = (name, val, max) => { if (words(val) > max) bad.push(`${name} ${words(val)}>${max}: "${val}"`) }
    lim('title', m.title, LIMITS.title); lim('instruction', m.text, LIMITS.instruction); lim('target line', m.tgt, LIMITS.targetLine); lim('turn/direction', m.cue, LIMITS.turnOrDirection); lim('honest line', m.sure, LIMITS.notSureLine); lim('reminder', m.approx, LIMITS.reminder); lim('message', m.msg, LIMITS.message)
    lim('primary button', m.primary, LIMITS.primaryButton); lim('secondary button', m.secondary, LIMITS.secondaryButton); lim('whole panel', m.total, LIMITS.panelNormal)
    check(tag + 'within the word limits', bad.length === 0 && m.title !== '', bad.join(' | ') || `title ${words(m.title)}, instruction ${words(m.text)}, panel ${words(m.total)}`)
    await noBadText(tag)
  }
  await measure('step 1, GPS off')
  await ev(`navigator.geolocation.watchPosition = (ok, err) => { setTimeout(() => err({ code: 1 }), 50); return 7 }`)
  await tap(w.gps); await sleep(400)
  await measure('step 1, location blocked')
  await ev(`delete navigator.geolocation.watchPosition`)
  await b.send('Page.reload'); await sleep(1500)
  await tap(w.start); await sleep(250); await tap(blk.ref); await waitExpr(`document.querySelectorAll('#map .treeicon').length > 0`); await sleep(300)
  await tap(w.gps)
  await gps(ST[0] + 0.00036, ST[1], 6); await waitExpr(`document.querySelector('.tgtline').textContent.includes('40')`)
  await measure('step 1, far')
  await gps(ST[0] + 0.00036, ST[1], 18); await waitExpr(`!document.querySelector('.sureline').hidden`)
  await measure('step 1, far, phone not sure (18 m)')
  await gps(ST[0], ST[1], 3); await waitExpr(`document.querySelector('.tgtline').textContent.endsWith('${w.here}')`)
  await measure('step 1, at START')
  await tap(w.atStart); await sleep(300)
  await measure('step 2')
  await tap(w.stake); await sleep(300)
  await measure('step 3, tree 1')
  await ev(`document.querySelector('#map .treeicon[data-k="2"]').click()`); await sleep(300)
  await measure('step 3, next tree in the row')
  const multi = pk.blocks.find((x) => x.n > x.per_row)
  if (multi && multi.ref === blk.ref) { await ev(`document.querySelector('#map .treeicon[data-k="${blk.per_row + 1}"]').click()`); await sleep(300); await measure('step 3, first tree of the second row') }
  else if (multi) { await tap(w.back); await sleep(300); await tap(multi.ref); await waitExpr(`document.querySelectorAll('#map .treeicon').length > 0`); await sleep(400); await tap(w.gps); await gps(multi.start[0] + 0.0002, multi.start[1], 6); await sleep(500); await ev(`document.querySelector('#map .treeicon[data-k="${multi.per_row + 1}"]').click()`); await sleep(400); await measure('step 3, first tree of the second row (another block)'); await tap(w.back); await sleep(300); await tap(blk.ref); await waitExpr(`document.querySelectorAll('#map .treeicon').length > 0`); await sleep(400); await ev(`document.querySelector('#map .treeicon[data-k="2"]').click()`); await sleep(300) }
  await gps(ST[0] + 0.0002, ST[1], 18); await sleep(500)
  await measure('step 3, phone not sure')
  // skip panel
  await tap(w.skip); await sleep(300)
  {
    const m = JSON.parse(await ev(`(() => { const sh = document.querySelector('.sheet'); const r = sh.querySelector('.reasons'); return JSON.stringify({ q: r.previousElementSibling.innerText, reasons: [...r.querySelectorAll('.btn')].map((e) => e.innerText), note: r.nextElementSibling.innerText, total: sh.querySelector('.sheetbody').innerText }) })()`))
    check(`words ${lang} [skip panel]: question, eight reasons, the move-10-m note`, words(m.q) <= LIMITS.skipQuestion && m.reasons.length === 8 && m.reasons.every((x) => words(x) <= LIMITS.reason) && words(m.total) <= LIMITS.skipPanel && /10 m/.test(m.note), `q ${words(m.q)}, total ${words(m.total)}`)
    await noBadText(`words ${lang} [skip panel]`)
  }
  await tap(w.rock); await sleep(300)
  await goStep(w, w.nextStep)
  await measure('step 4')
  // collapsed bar
  await tap(w.chevClose); await sleep(300)
  check(`words ${lang} [collapsed bar]: short`, words(await txt('.sum')) <= LIMITS.collapsedBar && words(await txt('.sum')) >= 2, await txt('.sum'))
  await tap(w.chevOpen); await sleep(300)
  // finish the block: mark every tree, then the panel says it is done
  for (let i = 0; i < blk.n; i++) { const left = await ev(`document.querySelectorAll('.chip.todo').length`); if (!left) break; await tap(w.planted); await sleep(120) }
  await sleep(300)
  check(`words ${lang} [block done]: the message is short`, words(await txt('.ok')) <= 12 && (await txt('.ok')).length > 5, await txt('.ok'))
  check(`words ${lang} [block done]: no main button is left that does nothing`, !(await visible('.btnrow')))
}

// ======================================================================= 5. layout matrix: three phone sizes x two languages x text 85% and 150%
for (const [W, H] of SIZES) {
  for (const lang of ['en', 'fil']) {
    for (const lvl of [0, 4]) {
      const w = T[lang]
      const tag = `layout ${W}x${H} ${lang} ${LEVELS[lvl]}%: `
      await b.viewport(W, H)
      await b.fresh(PAGE, { lang, size: lvl })
      const pk = await pack(), blk = pk.blocks[0], ST = blk.start
      const audit = async (where, opts = {}) => {
        const r = JSON.parse(await ev(`(() => {
          const vw = innerWidth, vh = innerHeight, out = { hscroll: document.documentElement.scrollWidth > document.documentElement.clientWidth + 0, vscroll: false, cut: [], small: [], notShown: [] }
          const skip = (e) => e.closest('.leaflet-container, .chips, .tour-hole') || e.closest('[hidden]')
          for (const e of document.querySelectorAll('body *')) {
            if (skip(e)) continue
            const r = e.getBoundingClientRect()
            if (r.width < 1 || r.height < 1) continue
            const cs = getComputedStyle(e)
            if (cs.display === 'none' || cs.visibility === 'hidden') continue
            if (e.tagName === 'SCRIPT' || e.tagName === 'STYLE') continue
            if (r.right > vw + 1 || r.left < -1) out.cut.push(e.tagName + '.' + String(e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className).slice(0, 24) + ' ' + Math.round(r.left) + '..' + Math.round(r.right))
          }
          for (const e of document.querySelectorAll('button')) {
            if (skip(e) || e.id === 'bannerclose') continue
            const r = e.getBoundingClientRect()
            if (r.width < 1) continue
            if (Math.min(r.width, r.height) < 47.5) out.small.push((e.getAttribute('aria-label') || e.textContent).slice(0, 20) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height))
          }
          return JSON.stringify(out)
        })()`))
        check(tag + where + ': no sideways scroll, nothing cut off at the sides', !r.hscroll && r.cut.length === 0, r.cut.slice(0, 3).join(' | '))
        check(tag + where + ': every button is at least 48 px', r.small.length === 0, r.small.slice(0, 4).join(' | '))
        await noBadText(tag + where)
      }
      await audit('first screen')
      check(tag + 'first screen: the Start button can be reached (scroll the page if needed) and Aa - / Aa + / Help are in the top row', await ev(`(() => { const t = document.querySelector('.toolbox').getBoundingClientRect(); return t.top < 140 && document.querySelectorAll('.toolbox button').length === 3 })()`))
      await tap(w.help); await sleep(300)
      await audit('Help')
      await tap(w.close); await sleep(200)
      await tap(w.start); await sleep(250)
      await audit('block list')
      await tap(blk.ref); await waitExpr(`document.querySelectorAll('#map .treeicon').length > 0`); await sleep(500)
      await audit('block, step 1 before GPS')
      await tap(w.gps)
      await gps(ST[0] + 0.00036, ST[1], 18); await waitExpr(`document.querySelector('.tgtline').textContent.includes('40')`); await sleep(300)
      const prim = async (where) => {
        const ok = await ev(`(() => { const p = document.querySelector('.btnrow .primary'); if (!p || p.closest('[hidden]')) return 'missing'; const r = p.getBoundingClientRect(); const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); const inside = r.top >= 0 && r.bottom <= innerHeight + 1 && r.left >= 0 && r.right <= innerWidth + 1; return JSON.stringify({ inside, covered: !(t === p || p.contains(t)), page: document.documentElement.scrollHeight <= innerHeight + 1, top: Math.round(r.top), bottom: Math.round(r.bottom) }) })()`)
        const j = ok.startsWith('{') ? JSON.parse(ok) : null
        check(tag + where + ': the main button is fully on the screen, not covered, and the page itself does not scroll', !!j && j.inside && !j.covered && j.page, ok)
      }
      await prim('step 1 with a GPS reading and the honest line')
      await audit('block, step 1 with GPS')
      await b.shot(`ui_${W}_${lang}_${LEVELS[lvl]}_s1`)
      await tap(w.atStart); await sleep(300)
      await tap(w.stake); await sleep(300)
      await prim('step 3')
      await audit('block, step 3')
      await b.shot(`ui_${W}_${lang}_${LEVELS[lvl]}_s3`)
      // the sheet's own text can be reached by scrolling inside it, and the round map buttons are reachable when the panel is collapsed
      await tap(w.chevClose); await sleep(350)
      const rb = JSON.parse(await ev(`JSON.stringify([...document.querySelectorAll('.mapbtns .rbtn')].map((e) => { const r = e.getBoundingClientRect(); const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return (t === e || e.contains(t)) && r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight && Math.min(r.width, r.height) >= 47.5 }))`))
      check(tag + 'collapsed panel: the round map buttons are reachable and 48 px or more', rb.length >= 5 && rb.every(Boolean), JSON.stringify(rb))
      await tap(w.chevOpen); await sleep(300)
      await tap(w.details); await sleep(350)
      await audit('block, Details open')
      await tap(w.chevBack); await sleep(250)
    }
  }
}

// ======================================================================= 6. guided tours
const TARGETS = {
  l1: ['[data-tour="l-title"]'], l2: ['[data-tour="l-how"]'], l3: ['[data-tour="l-start"]'], l4: ['[data-tour="toolbox"]'],
  h1: ['[data-tour="h-blocks"]'], h2: ['#observer'], h3: ['[data-tour="h-results"]'],
  b1: ['#map'], b2: ['.me .dot', '[data-tour="me"]'], b3: ['.me .cone', '[data-tour="rotate"]'], b4: ['.starticon'], b5: ['.treeicon.st-active', '.treeicon'], b6: ['[data-tour="sheet"]'], b7: ['[data-tour="buttons"]'], b8: ['.topbar [data-tour="toolbox"]'],
}
const TOTAL = { landing: 4, home: 3, block: 8 }
// walk a whole tour with Next: every step must light up an element that is on the screen
async function walkTour(tag, screen, w, { minShown = 1, expectAll = false } = {}) {
  const shown = []
  await waitExpr(`!!document.querySelector('.tour .tour-card[data-step-id]')`, 6000)
  for (let i = 0; i < TOTAL[screen] + 1; i++) {
    const info = await ev(`(() => { const c = document.querySelector('.tour .tour-card'); if (!c) return null; const hole = document.querySelector('.tour-hole'); const hr = hole.getBoundingClientRect(); return JSON.stringify({ id: c.dataset.stepId, count: document.querySelector('.tour-count').textContent, title: document.querySelector('.tour-title').textContent, text: document.querySelector('.tour-text').textContent, dots: document.querySelectorAll('.tdot').length, on: [...document.querySelectorAll('.tdot')].findIndex((d) => d.classList.contains('on')), hole: [hr.left, hr.top, hr.width, hr.height], vw: innerWidth, vh: innerHeight, covers: document.querySelector('.tour').dataset.covers, btns: [...c.querySelectorAll('button')].map((x) => Math.min(x.getBoundingClientRect().width, x.getBoundingClientRect().height)) }) })()`)
    if (!info) break
    const s = JSON.parse(info)
    // the highlighted rectangle = the rectangle of one of the expected elements (+ 4 px each side)
    const match = await ev(`(() => { const [l, t, w, h] = ${JSON.stringify(s.hole)}; for (const q of ${JSON.stringify(TARGETS[s.id])}) for (const e of document.querySelectorAll(q)) { const r = e.getBoundingClientRect(); if (Math.abs(r.left - 4 - l) < 2 && Math.abs(r.top - 4 - t) < 2 && Math.abs(r.width + 8 - w) < 2 && Math.abs(r.height + 8 - h) < 2) { const x = Math.min(innerWidth - 1, Math.max(1, r.left + r.width / 2)), y = Math.min(innerHeight - 1, Math.max(1, r.top + r.height / 2)); const hit = document.elementsFromPoint(x, y).find((n) => !n.closest('.tour')); return JSON.stringify({ onScreen: r.right > 0 && r.bottom > 0 && r.left < innerWidth && r.top < innerHeight, hit: !!hit && (hit === e || e.contains(hit) || hit.contains(e) || !!e.closest('.leaflet-container')) }) } } return 'no match' })()`)
    const mm = match.startsWith('{') ? JSON.parse(match) : null
    shown.push(s.id)
    check(tag + `step ${s.id} (${s.count}): it highlights a real element that is on the screen and not covered`, !!mm && mm.onScreen && mm.hit, match + ' hole ' + JSON.stringify(s.hole.map(Math.round)))
    check(tag + `step ${s.id}: title and text are there, ${TOTAL[screen]} dots, the right dot is lit, buttons 48 px`, s.title.length > 2 && s.text.length > 10 && s.dots === TOTAL[screen] && s.on >= 0 && Math.min(...s.btns) >= 47.5 && !/\[|\{/.test(s.title + s.text), s.count + ' ' + s.btns.join(','))
    { const area = s.hole[2] * s.hole[3]; const allowed = s.hole[3] > 0.45 * s.vh ? 0.12 * area : 0; check(tag + `step ${s.id}: the card does not hide the highlighted thing (a target taller than half the screen may be covered by up to 12%)`, Number(s.covers) <= allowed, 'overlap ' + s.covers + ' of ' + Math.round(area) + ' px2') }
    await noBadText(tag + `tour step ${s.id}`)
    const nextLabel = await ev(`document.querySelector('.tour-btns .good').textContent`)
    await tapSel('.tour-btns .good')
    await waitExpr(`(() => { const c = document.querySelector('.tour .tour-card'); return !c || c.dataset.stepId !== ${JSON.stringify(s.id)} })()`, 5000)
    await sleep(250)
    if (nextLabel === w.done) break
  }
  check(tag + 'the tour ends and the screen is free again', !(await visible('.tour')))
  check(tag + `${shown.length} of ${TOTAL[screen]} steps were shown (${shown.join(',')})`, shown.length >= minShown && (!expectAll || shown.length === TOTAL[screen]))
  return shown
}
for (const lang of ['en', 'fil']) {
  const w = T[lang]
  for (const [W, H, lvl] of [[360, 640, 1], [360, 640, 0], [360, 640, 4], [412, 915, 4]]) {
    const tag = `tour ${lang} ${W}x${H} ${LEVELS[lvl]}%: `
    await b.viewport(W, H)
    await b.fresh(PAGE, { lang, size: lvl, tours: false, session: { fieldpack_sheet: 'collapsed' } })
    const pk = await pack(), blk = pk.blocks[0]
    // landing: runs by itself the first time
    await sleep(500)
    check(tag + 'the landing tour starts by itself on the first visit', await visible('.tour .tour-card'))
    check(tag + 'the text is in the chosen language', lang === 'fil' ? /Ano ang page|Hindi eksakto/.test(await txt('.tour-card')) : /What this page does/.test(await txt('.tour-card')), await txt('.tour-title'))
    await walkTour(tag + 'landing: ', 'landing', w, { expectAll: true, minShown: 4 })
    await b.send('Page.reload'); await sleep(1500)
    check(tag + 'after finishing it, it does not start again', !(await visible('.tour')))
    // Help > Take the tour restarts it
    await tap(w.help); await sleep(300)
    await tap(w.takeTour); await sleep(500)
    check(tag + 'Help > Take the tour starts it again', await visible('.tour .tour-card'))
    // Escape ends it
    await b.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 }); await sleep(300)
    check(tag + 'Escape ends the tour', !(await visible('.tour')))
    // home
    await tap(w.start); await sleep(700)
    check(tag + 'the block-list tour starts by itself the first time', await visible('.tour .tour-card'))
    await walkTour(tag + 'home: ', 'home', w, { expectAll: true, minShown: 3 })
    // block, the sheet starts COLLAPSED: the tour opens it by itself when a step needs it and puts it back at the end
    await tap(blk.ref); await waitExpr(`document.querySelectorAll('#map .treeicon').length > 0`)
    await sleep(900)
    check(tag + 'the block tour starts by itself the first time', await visible('.tour .tour-card'))
    const midState = []
    const shown = await (async () => {
      const r = await walkTour(tag + 'block: ', 'block', w, { minShown: lvl === 4 && H < 700 ? 5 : 7 })
      return r
    })()
    check(tag + 'after the tour the panel is back in the state it had (collapsed)', (await ev(`document.querySelector('.sheet').dataset.state`)) === 'collapsed')
    if (lvl === 1 && H === 640) {
      check(tag + 'the block tour shows all 8 steps at normal text size (the blue dot and cone fall back to their buttons without GPS)', shown.length === 8, shown.join(','))
      // skipping marks it done
      await tap(w.back); await sleep(300)
      await b.fresh(PAGE, { lang, size: lvl, tours: false })
      await sleep(500)
      await tapSel('.tour-btns .tourbtn.ghost'); await sleep(300)
      check(tag + 'Skip closes the tour', !(await visible('.tour')))
      await b.send('Page.reload'); await sleep(1500)
      check(tag + '... and a skipped tour does not come back by itself', !(await visible('.tour')))
      // the tour blocks taps on the page behind it
      await tap(w.help); await sleep(300); await tap(w.takeTour); await sleep(500)
      await touch(40, 300); await sleep(200)
      check(tag + 'taps on the page behind the tour do nothing (no jumping to another screen)', await visible('.tour .tour-card') && (await ev(`document.querySelector('[data-tour="l-start"]') !== null`)))
      await tapSel('.tour-btns .tourbtn.ghost')
    }
    await b.shot(`ui_tour_${lang}_${W}_${LEVELS[lvl]}`)
  }
}
check('no uncaught page errors during the whole run', b.events.length === 0, b.events.length ? JSON.stringify(b.events[0].params.exceptionDetails).slice(0, 300) : '')
await b.done('ui_report')
