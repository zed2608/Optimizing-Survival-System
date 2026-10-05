// Which dashboard opens when the address has no #/new, #/legacy or #/v2 at the end.
//   'legacy' = the earlier dashboard (App.legacy.jsx, an unchanged copy of the original App.jsx)
//   'new'    = the revamp in src/new/
// Keep it 'legacy' until the revamp is approved. This is the ONE setting that picks the default.
export const DEFAULT_DASHBOARD = 'legacy'

// Which dashboard an address ends with: #/v2, #/new, #/legacy; anything else (including #/ and no #) -> the default above.
export function chooseDashboard(hash, fallback = DEFAULT_DASHBOARD) {
  if (hash.startsWith('#/v2')) return 'v2'
  if (hash.startsWith('#/new')) return 'new'
  if (hash.startsWith('#/legacy')) return 'legacy'
  return fallback
}
