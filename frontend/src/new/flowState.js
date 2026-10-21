// The four steps of the goal "I have species": what each one needs before "Next", and the short summary of a finished step (UX round 4). Pure (tested in flowState.test.mjs). English or Taglish (the last argument, default the page language).
import { getLang, tr } from './i18n.js'

export const stepTitle = (n, lang = getLang()) => tr(`flow.step${n}`, {}, lang)

// ctx = { selNames: [names of the chosen species], where: {kind: all|barangay|zone, name}, whereLabel, planAreaLabel (text of the area the plan will use, '' when none), planCreated }
export function flowSteps(ctx, lang = getLang()) {
  const t = (k, p) => tr(k, p, lang)
  const short = (names) => (names.length <= 2 ? names.join(', ') : t('flow.sum.more', { names: names.slice(0, 2).join(', '), n: names.length - 2 }))
  const speciesDone = ctx.selNames.length > 0
  const whereDone = ctx.where.kind === 'all' || !!ctx.where.name
  const areaDone = !!ctx.planAreaLabel
  return [
    { n: 1, title: t('flow.step1'), done: speciesDone, summary: speciesDone ? short(ctx.selNames) : '', requirement: speciesDone ? '' : t('flow.req.species') },
    {
      n: 2,
      title: t('flow.step2'),
      done: whereDone,
      summary: whereDone ? (ctx.where.kind === 'all' ? t('flow.sum.all') : ctx.whereLabel || ctx.where.name) : '',
      requirement: whereDone ? '' : ctx.where.kind === 'barangay' ? t('flow.req.barangay') : t('flow.req.zone'),
    },
    { n: 3, title: t('flow.step3'), done: areaDone, summary: areaDone ? ctx.planAreaLabel : '', requirement: areaDone ? '' : t('flow.req.area') },
    { n: 4, title: t('flow.step4'), done: !!ctx.planCreated, summary: ctx.planCreated ? t('flow.sum.created') : '', requirement: '' },
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
