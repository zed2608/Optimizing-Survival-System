import { getLang, tr } from './i18n.js'

// "team_decision:file (not a sourced fact)" / "provisional_map:file" in plain words (English or Taglish): what an input is when it has no cited source. Tested in inputWords.test.mjs.
export function otherInputText(o, lang = getLang()) {
  const text = String(o)
  const i = text.indexOf(':')
  const kind = i < 0 ? text : text.slice(0, i)
  const what = (i < 0 ? '' : text.slice(i + 1)).replace(/\s*\(not a sourced fact\)\s*$/, '').trim()
  if (kind === 'team_decision') return tr('x.teamDecision', { what }, lang)
  if (kind === 'provisional_map') return tr('x.provMap', { what }, lang)
  return text
}
