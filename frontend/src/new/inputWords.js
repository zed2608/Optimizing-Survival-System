// "team_decision:file (not a sourced fact)" / "provisional_map:file" in plain Filipino: what an input is when it has no cited source. Tested in inputWords.test.mjs.
export function otherInputText(o) {
  const text = String(o)
  const i = text.indexOf(':')
  const kind = i < 0 ? text : text.slice(0, i)
  const what = (i < 0 ? '' : text.slice(i + 1)).replace(/\s*\(not a sourced fact\)\s*$/, '').trim()
  if (kind === 'team_decision') return `desisyon ng team, hindi sourced na datos (${what})`
  if (kind === 'provisional_map') return `pansamantalang mapa ng team, hindi sourced na datos (${what})`
  return text
}
