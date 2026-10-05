// Wording and symbols for saved field checks. Shape always comes with a word: never colour alone.
export const STATUS_LABEL = { verified_plantable: 'Verified plantable', not_plantable: 'Not plantable', needs_recheck: 'Needs recheck' }
export const STATUS_SYMBOL = { verified_plantable: '◯', not_plantable: '✕', needs_recheck: '△' }
export const STATUS_SHAPE = { verified_plantable: 'ring', not_plantable: 'cross', needs_recheck: 'triangle' }

export const REASONS = [
  ['paved', 'Paved'],
  ['building', 'Building'],
  ['rock_or_ledge', 'Rock or ledge'],
  ['creek_or_waterlogged', 'Creek bank or waterlogged'],
  ['too_steep', 'Too steep'],
  ['existing_tree', 'Existing tree'],
  ['owner_refused', 'Owner refused'],
  ['other', 'Other'],
]
export const REASON_LABEL = Object.fromEntries(REASONS)

// The compact status codes of GET /grid: 1 verified, 2 not plantable, 3 needs recheck, +4 = disputed.
const CODE = { 1: 'verified_plantable', 2: 'not_plantable', 3: 'needs_recheck' }
export function decodeFieldCode(code) {
  return { status: CODE[code % 4], disputed: code >= 4 }
}

export function when(iso) {
  return typeof iso === 'string' ? iso.replace('T', ' ').slice(0, 16) : ''
}
