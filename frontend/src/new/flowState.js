// The four steps of the goal "I have species": what each one needs before "Next", and the short summary of a finished step (UX round 4). Pure (tested in flowState.test.mjs). Filipino first.
export const STEP_TITLES = ['Piliin ang species', 'Saan hahanapin', 'Markahan sa mapa', 'Gumawa ng plano']

const short = (names) => (names.length <= 2 ? names.join(', ') : `${names.slice(0, 2).join(', ')} at ${names.length - 2} pa`)

// ctx = { selNames: [names of the chosen species], where: {kind: all|barangay|zone, name}, whereLabel, planAreaLabel (text of the area the plan will use, '' when none), planCreated }
export function flowSteps(ctx) {
  const speciesDone = ctx.selNames.length > 0
  const whereDone = ctx.where.kind === 'all' || !!ctx.where.name
  const areaDone = !!ctx.planAreaLabel
  return [
    { n: 1, title: STEP_TITLES[0], done: speciesDone, summary: speciesDone ? short(ctx.selNames) : '', requirement: speciesDone ? '' : 'Pumili muna ng kahit isang species.' },
    {
      n: 2,
      title: STEP_TITLES[1],
      done: whereDone,
      summary: whereDone ? (ctx.where.kind === 'all' ? 'Buong San Mateo' : ctx.whereLabel || ctx.where.name) : '',
      requirement: whereDone ? '' : ctx.where.kind === 'barangay' ? 'Pumili ng barangay, o piliin ang Buong San Mateo.' : 'Pumili ng zone, o piliin ang Buong San Mateo.',
    },
    {
      n: 3,
      title: STEP_TITLES[2],
      done: areaDone,
      summary: areaDone ? ctx.planAreaLabel : '',
      requirement: areaDone ? '' : 'Pumili ng lugar para sa plano: markahan ito sa mapa (isang puntos o tatlo o higit pa para sa area), o pumili ng barangay o zone sa Hakbang 2.',
    },
    { n: 4, title: STEP_TITLES[3], done: !!ctx.planCreated, summary: ctx.planCreated ? 'Nagawa na ang plano' : '', requirement: '' },
  ]
}

// Can the person go from step n to step n + 1? { ok, reason }. A step is passable when it is done; a later step needs every earlier one.
export function canGoNext(steps, n) {
  for (let i = 0; i < n && i < 3; i++) if (!steps[i].done) return { ok: false, reason: steps[i].requirement }
  return { ok: true, reason: '' }
}

// May the person jump to step n (stepper click)? Only to a step that is already reachable: all the steps before it are done.
export function canJump(steps, n) {
  return steps.slice(0, n - 1).every((s) => s.done)
}
