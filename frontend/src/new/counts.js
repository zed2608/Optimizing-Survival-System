// Tree counts per species of step 5 (pure helpers).
export const COUNT_DEFAULT = 20 // trees given to a newly chosen species
export const COUNT_PRESETS = [10, 20, 50]
export const COUNT_MAX = 2000

export const countText = (counts, id) => String(counts[id] ?? COUNT_DEFAULT)
const whole = (t) => (/^\d+$/.test(String(t).trim()) ? Number(t) : NaN)

// The trees of every chosen species, and their total. Valid when every count is a whole number of at least 1 and the total is 1 to 2000.
export function countsSummary(ids, counts) {
  const nums = ids.map((id) => whole(countText(counts, id)))
  const total = nums.reduce((a, n) => a + (Number.isFinite(n) ? n : 0), 0)
  const valid = ids.length > 0 && nums.every((n) => Number.isFinite(n) && n >= 1 && n <= COUNT_MAX) && total >= 1 && total <= COUNT_MAX
  return { total, valid, nums }
}
