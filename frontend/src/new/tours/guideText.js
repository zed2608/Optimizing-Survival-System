// The text of every guided tour in English, in the order of the Tours menu: the printed guide (docs/USER_GUIDE.md, the Print button of the Help page) and the wording tests read it
// from here, so the guide is built from the SAME registry the tours run from (tourDefs.js) and cannot drift away from it.
import { TOURS, tourSteps } from './tourDefs.js'

export const guideTours = () =>
  TOURS.map((t) => ({
    id: t.id,
    title: t.title.en,
    blurb: t.blurb.en,
    sections: t.sections.map((s) => ({
      id: s.id,
      title: s.title.en,
      steps: s.steps.map((x) => ({ id: x.id, title: x.title.en, text: x.text.en, watch: x.watch?.en ?? '' })),
    })),
  }))

export const guideStepCount = () => TOURS.reduce((n, t) => n + tourSteps(t).length, 0)
