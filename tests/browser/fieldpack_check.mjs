// Whole flow of the field pack in headless Edge at 360 x 640 and 390 x 844 with a FAKE GPS (tiles intercepted: no map server is contacted). Not run by pytest by default (see tests/test_field_pack_browser.py).
//   node tests/browser/fieldpack_check.mjs <page: a file path or an http address> <folder for pictures>
// Home (banner, notice, name field, block cards), the block screen (map fills the screen, top bar, bottom sheet, chips, Details), GPS far / on the point / approximate, planted, skipped with a reason,
// the marks staying after a reload, the results file (blocks.csv columns first, prototype notice in every row), and the words null / undefined / NaN never being visible.
import { pathToFileURL } from 'node:url'
import { resolve } from 'node:path'
import { launch } from './cdp_lib.mjs'

const target = process.argv[2]
const url = /^https?:/.test(target) ? target : pathToFileURL(resolve(target)).href
const b = await launch({ out: process.argv[3] })
const { ev, text, click, tap, check, sleep, waitFor, waitExpr, gps, noBadText } = b
b.tileMode = 'ok'

for (const [W, H] of [[360, 640], [390, 844]]) {
  const tag = `${W}x${H}: `
  await b.viewport(W, H)
  await b.open(url)
  await ev('sessionStorage.clear(); localStorage.clear()')
  await b.open(url)
  const pack = JSON.parse(await ev("document.getElementById('pack-data').textContent"))
  const blk = pack.blocks[0]
  const t1 = blk.trees[0]

  // ---- home
  check(tag + 'the prototype notice is visible on first load', (await ev(`(() => { const e = document.getElementById('banner'); return !e.hidden && e.getBoundingClientRect().height > 0 && e.innerText.includes('Prototype. GPS accuracy not yet field-tested.') })()`)))
  check(tag + 'home: no sideways scroll', await ev('document.documentElement.scrollWidth <= document.documentElement.clientWidth'))
  check(tag + 'home: the name field is 16 px or bigger (no zoom on iOS) and the block cards are big', await ev(`parseFloat(getComputedStyle(document.getElementById('observer')).fontSize) >= 16 && [...document.querySelectorAll('.bcard')].every((c) => c.getBoundingClientRect().height >= 70)`))
  check(tag + 'home: a card for every block with a progress bar', (await ev(`document.querySelectorAll('.bcard .bar').length`)) === pack.blocks.length)
  await noBadText(tag + 'the home screen')

  // ---- the notice can be hidden for the session; its tap area is bigger than the button; it comes back in Details
  const slop = await ev(`(() => { const r = document.getElementById('bannerclose').getBoundingClientRect(); const e = document.elementFromPoint(r.x - 6, r.y + r.height / 2); return e && e.id === 'bannerclose' })()`)
  check(tag + 'the notice close button has a bigger tap area than its drawing', slop)
  await ev("document.getElementById('observer').value = 'Flow Tester'; document.getElementById('observer').dispatchEvent(new Event('input', { bubbles: true }))")

  // ---- block screen
  await tap(blk.ref)
  await waitExpr(`document.querySelectorAll('.treeicon').length === ${blk.n}`)
  await sleep(500)
  const lay = JSON.parse(await ev(`(() => { const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return [b.x, b.y, b.width, b.height] }; const ban = document.getElementById('banner'); return JSON.stringify({ vw: innerWidth, vh: innerHeight, banner: ban.hidden ? 0 : ban.getBoundingClientRect().height, top: r('.topbar'), stage: r('.stage'), map: r('#map'), sheet: r('.sheet'), sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight }) })()`))
  check(tag + 'the map fills the screen under the slim top bar (100dvh): the stage reaches the bottom edge and the full width', Math.abs(lay.stage[1] + lay.stage[3] - lay.vh) <= 1 && lay.stage[2] === lay.vw && lay.map[2] === lay.vw, JSON.stringify({ stage: lay.stage.map(Math.round), vh: lay.vh }))
  check(tag + 'the top bar is slim', lay.top[3] <= 64, Math.round(lay.top[3]) + ' px')
  check(tag + 'no sideways scroll and no page scroll on the block screen', lay.sw <= lay.vw && lay.sh <= lay.vh + 1, `${lay.sw}x${lay.sh}`)
  check(tag + 'the bottom sheet leaves the map visible (sheet under 50% of the screen height)', lay.sheet[3] < lay.vh * 0.5, Math.round(lay.sheet[3]) + ' px of ' + lay.vh)
  const hidden = await ev(`(() => { const a = document.querySelector('.treeicon.st-active').getBoundingClientRect(); const s = document.querySelector('.sheet').getBoundingClientRect(); return a.bottom > s.top + 1 })()`)
  check(tag + 'the sheet does not cover the active tree by default', !hidden)
  const sizes = JSON.parse(await ev(`JSON.stringify({ min: Math.min(...[...document.querySelectorAll('.stage button, .topbar button')].filter((e) => e.getBoundingClientRect().width > 0).map((e) => Math.min(e.getBoundingClientRect().width, e.getBoundingClientRect().height))), primary: document.querySelector('.btnrow .primary').getBoundingClientRect().height })`))
  check(tag + 'every button is at least 48 px, and "Planted here" at least 56 px high', sizes.min >= 47.5 && sizes.primary >= 56, `smallest ${sizes.min}, primary ${sizes.primary}`)
  check(tag + 'top bar says "0 of N done"; chips for every tree', (await ev(`document.querySelector('.topbar .done').textContent`)) === `0 of ${blk.n} done` && (await ev(`document.querySelectorAll('.chip').length`)) === blk.n)
  check(tag + 'Details are collapsed (no START corner, no legend in the main view)', !(await text()).includes('START corner') && !(await text()).includes('Dotted square'))
  await tap('Details')
  await sleep(300)
  check(tag + 'Details open: target position, START corner, legend, the honest 3 to 10 m line, the notice', await ev(`(() => { const t = document.querySelector('.sheet').innerText; return t.includes('Target position') && t.includes('START corner') && t.includes('Dotted square') && t.includes('3 to 10 m') && t.includes('Prototype. GPS accuracy not yet field-tested.') })()`))
  await tap('Details')
  await noBadText(tag + 'the block screen before GPS')
  await b.shot(`flow_${W}_1_block`)

  // ---- GPS far, on the point, approximate
  await tap('Start GPS')
  await noBadText(tag + 'the block screen just after tapping Start GPS')
  await gps(t1[1] + 0.00036, t1[2], 6) // 40 m north of tree 1
  await waitFor(/about 40 m/)
  const sheet = await ev(`document.querySelector('.sheet').innerText`)
  check(tag + 'distance and bearing in the sheet, accuracy shown', /about 40 m/.test(sheet) && /S 180°/.test(sheet) && /±6 m/.test(sheet), sheet.replace(/\n+/g, ' | ').slice(0, 150))
  check(tag + 'not "arrived" while far', !sheet.includes('You are at the tree'))
  await noBadText(tag + 'the block screen with a GPS reading')
  await gps(t1[1], t1[2], 3)
  await waitFor(/You are at the tree/)
  check(tag + '"arrived" only inside the reported accuracy (3 m)', (await text()).includes('You are at the tree'))
  await gps(t1[1], t1[2], 12)
  await waitFor(/only approximate/)
  check(tag + 'accuracy worse than the spacing says the position is only approximate', (await text()).includes('only approximate') && blk.spacing_m < 12)
  await gps(t1[1], t1[2], 3)
  await waitFor(/You are at the tree/)

  // ---- planted, then skipped with a reason
  await tap('Planted here')
  await sleep(500)
  check(tag + 'planted: the next tree is the target and the chip is green', (await ev(`document.querySelector('.ttl2').textContent`)) === `Tree 2 of ${blk.n}` && (await ev(`document.querySelector('.chip[data-k="1"]').className`)).includes('planted'))
  await gps(blk.trees[1][1] + 0.0005, blk.trees[1][2], 5) // away from tree 2: the planted tap will ask (the dialog is accepted by the check)
  await sleep(700)
  await tap('Skip')
  await sleep(300)
  check(tag + 'skip shows the README reasons', (await text()).includes('Rock or ledge') && (await text()).includes('Owner refused') && (await text()).includes('Creek or waterlogged'))
  await tap('Rock or ledge')
  await sleep(500)
  check(tag + 'skipped: tree 3 is next, "2 of N done" in the top bar', (await ev(`document.querySelector('.ttl2').textContent`)) === `Tree 3 of ${blk.n}` && (await ev(`document.querySelector('.topbar .done').textContent`)) === `2 of ${blk.n} done`)
  await tap('Planted here')
  await sleep(500)
  check(tag + 'planting while away from the tree asked first ("anyway?")', b.dialogs.some((d) => /anyway/.test(d)))
  await tap('Tree 3')
  await sleep(300)
  await tap('Undo')
  await sleep(400)
  check(tag + 'undo takes a mark back ("2 of N done" again)', (await ev(`document.querySelector('.topbar .done').textContent`)) === `2 of ${blk.n} done`)
  await noBadText(tag + 'the block screen after marking')

  // ---- the marks stay after a reload
  await b.send('Page.reload')
  await sleep(1500)
  await tap(blk.ref)
  await waitExpr(`document.querySelectorAll('.chip').length === ${blk.n}`)
  check(tag + 'after a reload the marks are still there', (await ev(`document.querySelector('.topbar .done').textContent`)) === `2 of ${blk.n} done`, await ev(`document.querySelector('.topbar .done').textContent`))

  // ---- results file
  await tap('Back')
  await sleep(300)
  await ev("window.__blobs = []; const o = URL.createObjectURL.bind(URL); URL.createObjectURL = (x) => { window.__blobs.push(x); return o(x) }")
  await tap('Save results file')
  await sleep(500)
  const csv = await ev('window.__blobs[0] ? window.__blobs[0].text() : null')
  check(tag + 'a results file was made', !!csv)
  if (csv) {
    const lines = csv.replace(/^﻿/, '').trim().split(/\r?\n/)
    const parse = (line) => { const out = []; let cur = '', q = false; for (let i = 0; i < line.length; i++) { const c = line[i]; if (q) { if (c === '"' && line[i + 1] === '"') { cur += '"'; i++ } else if (c === '"') q = false; else cur += c } else if (c === '"') q = true; else if (c === ',') { out.push(cur); cur = '' } else cur += c } out.push(cur); return out }
    const head = parse(lines[0])
    const r1 = parse(lines[1])
    const col = (n) => head.indexOf(n)
    check(tag + 'results file: blocks.csv columns first, one row per block', lines.length === pack.blocks.length + 1 && head.slice(0, pack.columns.length).join(',') === pack.columns.join(','))
    check(tag + 'results file: block 1 planted with its count, by the name typed, plan and check code kept', r1[col('status')] === 'planted' && Number(r1[col('trees_planted')]) >= 1 && r1[col('observer')] === 'Flow Tester' && r1[col('plan_id')] === pack.plan_id && r1[col('check_code')] === pack.check_code)
    check(tag + 'results file: the prototype notice is in every row', lines.slice(1).every((l) => parse(l)[col('pack_notice')].startsWith('Prototype. GPS accuracy not yet field-tested.')))
    check(tag + 'results file: moved_lat and moved_lon stay empty', lines.slice(1).every((l) => parse(l)[col('moved_lat')] === '' && parse(l)[col('moved_lon')] === ''))
  }
  await noBadText(tag + 'the home screen after marking trees')
}
check('no uncaught page errors during the whole run', b.events.length === 0, b.events.length ? JSON.stringify(b.events[0].params.exceptionDetails).slice(0, 200) : '')
await b.done('flow_report')
