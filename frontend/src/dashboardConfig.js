// Which dashboard opens when the address has no #/new, #/legacy or #/v2 at the end.
//   'new'    = the revamp in src/new/ (the dashboard of the release candidate)
//   'legacy' = the earlier dashboard (App.legacy.jsx, an unchanged copy of the original App.jsx); still reachable at #/legacy
// This is the ONE setting that picks the default (round 9: the revamp is now the default).
export const DEFAULT_DASHBOARD = 'new'

// Which dashboard an address ends with: #/v2, #/new, #/legacy; anything else (including #/ and no #) -> the default above.
export function chooseDashboard(hash, fallback = DEFAULT_DASHBOARD) {
  if (hash.startsWith('#/v2')) return 'v2'
  if (hash.startsWith('#/new')) return 'new'
  if (hash.startsWith('#/legacy')) return 'legacy'
  return fallback
}
