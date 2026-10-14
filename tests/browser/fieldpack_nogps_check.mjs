// Field pack, stage A1f: "no GPS" is never a dead end. Headless Edge, fake GPS, GPS failures made by replacing watchPosition (denied, timeout, unavailable, never answers).
// For every phone size (360x640, 390x844, 412x915), both languages and text at 85 and 150 percent: the GPS bar says how the GPS is; in every state there is a visible, uncovered button of 48 px or more
// that tries GPS (again) AND one that continues without GPS; "continue without GPS" shows row and spot instead of an arrow; the way back to GPS is always there and brings the arrow back; nothing is saved.
//   node tests/browser/fieldpack_nogps_check.mjs <address of the pack page> <folder for pictures>
import { launch } from './cdp_lib.mjs'

const PAGE = process.argv[2]
const b = await launch({ out: process.argv[3] })
const { ev, text, tap, check, sleep, waitExpr, gps, noBadText } = b
b.tileMode = 'ok'

const words = (s) => (s || '').split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length
const T = {
  en: { start: 'Start', gps: 'Start GPS', contSecond: 'Continue without GPS', cont: 'Continue without GPS', again: 'Try GPS again', retry: 'Try again', use: 'Use GPS', barOk: 'GPS: working', barOff: 'GPS: not ready', barWait: 'GPS: finding you', barBlocked: 'GPS: blocked', barProblem: 'GPS: problem', barNone: 'No GPS',
        close: 'Close', atStart: "I'm at START", stake: 'Stake is in', planted: 'Planted', tree: 'Tree', allow: 'Allow', tape: /tape measure/ },
  fil: { start: 'Start', gps: 'Start GPS', contSecond: 'Ituloy, walang GPS', cont: 'Ituloy nang walang GPS', again: 'Subukan ulit ang GPS', retry: 'Subukan ulit', use: 'Gamitin ang GPS', barOk: 'GPS: gumagana', barOff: 'GPS: hindi pa handa', barWait: 'GPS: hinahanap ka', barBlocked: 'GPS: naka-block', barProblem: 'GPS: may problema', barNone: 'Walang GPS',
         close: 'Close', atStart: 'Nasa START na ako', stake: 'Nailagay na ang stake', planted: 'Naitanim na', tree: 'Puno', allow: 'Allow', tape: /tape measure/ },
}
const visible = (q) => ev(`(() => { const e = document.querySelector(${JSON.stringify(q)}); if (!e || e.closest('[hidden]') || e.hasAttribute('hidden')) return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 })()`)
const txt = (q) => ev(`(() => { const e = document.querySelector(${JSON.stringify(q)}); return e && !e.closest('[hidden]') ? e.innerText : '' })()`)
const bar = () => txt('.gpsbar')
const arrowShown = () => ev(`(() => { const a = document.querySelector('.tgtarrow'); return !!a && !a.hasAttribute('hidden') && a.getBoundingClientRect().width > 0 })()`)
const numbers = (s) => (s.match(/\d+(?:\.\d+)?/g) || []).map(Number)
// a button found by its text: shown, 48 px or more, fully on the screen and not covered (after scrolling the panel body or the page to it)
async function reach(label, press = false) {
  const r = await ev(`(() => { const L = ${JSON.stringify(label)}; const els = [...document.querySelectorAll('button')].filter((e) => !e.closest('[hidden]') && !e.hidden && e.getBoundingClientRect().width > 0); const e = els.find((x) => x.textContent.trim() === L || (x.getAttribute('aria-label') || '') === L) || els.find((x) => x.textContent.trim().includes(L)); if (!e) return 'missing'; const body = e.closest('.sheetbody'); if (body) { e.scrollIntoView({ block: 'nearest' }); for (let i = 0; i < 6; i++) { const r = e.getBoundingClientRect(); const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); if (t === e || e.contains(t)) break; body.scrollTop -= 30 } } const r = e.getBoundingClientRect(); const t = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return JSON.stringify({ x: r.x + r.width / 2, y: r.y + r.height / 2, size: Math.min(r.width, r.height), inside: r.left >= 0 && r.right <= innerWidth + 1 && r.top >= 0 && r.bottom <= innerHeight + 1, covered: !(t === e || e.contains(t)) }) })()`)
  if (r === 'missing') return { ok: false, why: 'missing' }
  const j = JSON.parse(r)
  const ok = j.size >= 47.5 && j.inside && !j.covered
  if (press && ok) await b.touch(j.x, j.y)
  return { ok, why: JSON.stringify({ size: Math.round(j.size), inside: j.inside, covered: j.covered }) }
}
const tapR = async (label) => { const r = await reach(label, true); if (!r.ok) b.check('a button was reachable and uncovered when tapped: ' + label, false, r.why); return r.ok }
const FAIL = (code) => `navigator.geolocation.watchPosition = (ok, err) => { setTimeout(() => err({ code: ${code} }), 30); return 7 }`
const NEVER = `navigator.geolocation.watchPosition = () => 9`
const REAL = `delete navigator.geolocation.watchPosition`

for (const [W, H] of [[360, 640], [390, 844], [412, 915]]) {
  for (const lang of ['en', 'fil']) {
    for (const lvl of [0, 4]) {
      const w = T[lang]
      const tag = `no GPS ${W}x${H} ${lang} ${[85, 100, 115, 130, 150][lvl]}%: `
      if (process.env.ONLY && process.env.ONLY !== `${W}:${lang}:${lvl}`) continue // only for looking at one combination
      await b.viewport(W, H)
      await b.fresh(PAGE, { lang, size: lvl })
      const pk = JSON.parse(await ev("document.getElementById('pack-data').textContent"))
      const blk = pk.blocks[0], ST = blk.start, off = blk.first_offset_m
      await tap(w.start); await sleep(250)
      await tap(blk.ref); await waitExpr(`document.querySelectorAll('#map .treeicon').length > 0`); await sleep(500)

      // ---- GPS not on yet (step 1): the main button starts it, the second one continues without it, the bar says it
      check(tag + 'GPS off: the bar says "' + w.barOff + '"', (await bar()).startsWith(w.barOff), await bar())
      let r1 = await reach(w.gps), r2 = await reach(w.contSecond), r3 = await reach(w.barOff)
      check(tag + 'GPS off, step 1: "Start GPS", "continue without GPS" and the GPS bar are all visible, uncovered, 48 px or more', r1.ok && r2.ok && r3.ok, [r1.why, r2.why, r3.why].join(' | '))
      await tap(w.barOff); await sleep(250)
      check(tag + 'the bar opens a small panel with a way to start GPS and a way to continue without it', (await visible('.gpspanel')) && (await reach(w.gps)).ok && (await reach(w.cont)).ok, await txt('.gpspanel'))
      check(tag + 'the panel is short (60 words at most) and the bar 4 words at most', words(await txt('.gpspanel')) <= 60 && words((await bar()).replace('›', '')) <= 4, String(words(await txt('.gpspanel'))))
      await noBadText(tag + 'the GPS panel')
      await b.shot(`nogps_${lang}_${W}_${lvl}_panel`)
      await tapR(w.close); await sleep(200)
      check(tag + 'Close brings the step back (its big button is there again)', !(await visible('.gpspanel')) && (await reach(w.gps)).ok)

      // ---- continue without GPS
      await tapR(w.contSecond); await sleep(350)
      check(tag + 'continue without GPS: the bar says "' + w.barNone + '", still step 1, no arrow, and the way to find START without GPS', (await bar()).startsWith(w.barNone) && !(await arrowShown()) && /START/.test(await txt('.steptext')), await bar() + ' / ' + (await txt('.steptext')))
      check(tag + 'continue without GPS: the main button goes on ("' + w.atStart + '")', (await reach(w.atStart)).ok)
      await tap(w.atStart); await sleep(350)
      const t2 = await txt('.steptext')
      check(tag + 'step 2 without GPS: tree 1 at the real offset (' + off[0] + ' m east, ' + off[1] + ' m north), no arrow, row and spot of the tree, the tape measure line', numbers(t2).join() === [1, off[0], off[1]].join() && !(await arrowShown()) && new RegExp(`${w.tree} 1 · row 1, spot 1`).test(await txt('.tgtline')) && w.tape.test(await txt('.sureline')), t2 + ' | ' + (await txt('.tgtline')))
      await tap(w.stake); await sleep(350)
      await tap(w.planted); await sleep(350)
      check(tag + 'step 3 without GPS: after Planted the next tree is 2: "row 1, spot 2" (from the plan), still no arrow', new RegExp(`${w.tree} 2 · row 1, spot 2`).test(await txt('.tgtline')) && !(await arrowShown()), await txt('.tgtline'))
      check(tag + 'the GPS bar is still there in step 3 and says "no GPS"', (await bar()).startsWith(w.barNone) && (await reach(w.barNone)).ok)
      await noBadText(tag + 'step 3 without GPS')
      await b.shot(`nogps_${lang}_${W}_${lvl}_step3`)

      // ---- the way back: Use GPS brings the arrow back
      await tap(w.barNone); await sleep(250)
      check(tag + 'no GPS: the panel offers "' + w.use + '" (and not "continue without GPS" again)', (await reach(w.use)).ok && !(await ev(`[...document.querySelectorAll('.gpspanel button')].some((x) => !x.hidden && x.textContent.trim() === ${JSON.stringify(w.cont)})`)), await txt('.gpspanel'))
      await tapR(w.use); await sleep(300)
      await gps(ST[0] + 0.00036, ST[1], 6)
      await waitExpr(`document.querySelector('.tgtline').textContent.includes(' m')`)
      check(tag + 'GPS back: the arrow and the distance are back, the bar says "' + w.barOk + '"', (await arrowShown()) && /\d+ m/.test(await txt('.tgtline')) && (await bar()).startsWith(w.barOk), (await bar()) + ' / ' + (await txt('.tgtline')))

      // ---- every failure: a button to try again AND a button to continue without GPS, in step 1 and in step 3
      for (const [name, script, barKey, panelNeeds] of [['location blocked', FAIL(1), 'barBlocked', w.allow], ['timeout', FAIL(3), 'barProblem', null], ['no signal / unavailable', FAIL(2), 'barProblem', null], ['never answers', NEVER, 'barWait', null]]) {
        // go to "no GPS" first, so that "Use GPS" starts the failing watch
        await tap(w.barOk); await sleep(200); await tapR(w.cont); await sleep(250)
        await ev(script)
        await tap(w.barNone); await sleep(200); await tapR(w.use); await sleep(500)
        const t0 = `${tag}${name}: `
        check(t0 + 'the bar says what is wrong (' + w[barKey] + ')', (await bar()).startsWith(w[barKey]), await bar())
        if (name !== 'never answers') {
          r1 = await reach(w.again); r2 = await reach(w.cont)
          check(t0 + 'in step 3 two buttons stand right under the message: "' + w.again + '" and "' + w.cont + '"', r1.ok && r2.ok, [r1.why, r2.why].join(' | '))
          check(t0 + 'the message says what to do, in 12 words or less', words(await txt('.msg')) <= 12 && (await txt('.msg')).length > 5, await txt('.msg'))
        }
        await tap(w[barKey]); await sleep(250)
        const panel = await txt('.gpspanel')
        r1 = await reach(w.again); r2 = await reach(w.cont)
        const rc = await reach(w.close)
        check(t0 + 'the panel has both ways out ("' + w.again + '", "' + w.cont + '") and a Close button', r1.ok && r2.ok && rc.ok, [r1.why, r2.why, rc.why].join(' | '))
        if (panelNeeds) check(t0 + 'blocked: the panel shows the short steps to allow Location again (Android and iPhone)', panel.includes(panelNeeds) && /Android/.test(panel) && /iPhone/.test(panel), panel)
        check(t0 + 'the panel is short (60 words at most)', words(panel) <= 60, String(words(panel)))
        await noBadText(t0 + 'the GPS panel')
        // the way out works: restore the real GPS and try again
        await ev(REAL)
        await tapR(w.again); await sleep(300)
        await gps(ST[0] + 0.00036, ST[1], 6)
        await waitExpr(`document.querySelector('.gpsbar').textContent.startsWith(${JSON.stringify(w.barOk)})`, 8000)
        check(t0 + 'after "' + w.again + '" with a working GPS the arrow is back', (await arrowShown()) && (await bar()).startsWith(w.barOk), await bar())
      }

      // ---- step 1 with a failing GPS: "try again" is the main button, "continue without GPS" the second
      await tap(w.barOk); await sleep(200); await tapR(w.cont); await sleep(250)
      await ev(`for (let i = 0; i < 4; i++) document.querySelector('.stepnav .arrow').click()`); await sleep(300) // back to step 1 (the step arrows are under Details)
      await ev(FAIL(1))
      await tap(w.barNone); await sleep(200); await tapR(w.use); await sleep(500)
      r1 = await reach(w.retry); r2 = await reach(w.contSecond)
      check(tag + 'step 1 with blocked location: "' + w.retry + '" and "' + w.contSecond + '" are both visible', r1.ok && r2.ok, [r1.why, r2.why].join(' | ') + ' / ' + (await txt('.sheet')).slice(0, 80))
      await ev(REAL)

      // ---- nothing about "no GPS" is saved: a reload starts fresh
      await tapR(w.contSecond); await sleep(250)
      const saved = await ev(`JSON.stringify(Object.keys(localStorage).map((k) => localStorage.getItem(k))).includes('nogps')`)
      check(tag + 'the choice is not saved (nothing in the browser storage)', saved === false)
      await b.send('Page.reload'); await sleep(1500)
      await tap(w.start); await sleep(250); await tap(blk.ref); await waitExpr(`document.querySelectorAll('#map .treeicon').length > 0`); await sleep(400)
      check(tag + 'after a reload the GPS is "not ready" again, with the buttons to start it or continue without it', (await bar()).startsWith(w.barOff))
      check(tag + 'no sideways scroll', await ev(`document.documentElement.scrollWidth <= document.documentElement.clientWidth`))
    }
  }
}
check('no uncaught page errors during the whole run', b.events.length === 0, b.events.length ? JSON.stringify(b.events[0].params.exceptionDetails).slice(0, 300) : '')
await b.done('nogps_report')
