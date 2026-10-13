// Test helper: runs the field pack's own core.js on JSON given on stdin, so the Python tests can compare it with the Python code.
//   {"mode": "csv", "pack": {...}, "observer": "Ana", "actions": [{"ref": "CHE-B01", "k": 1, "s": "planted", "lat": .., "lon": .., "acc": .., "t": "..."}]}  ->  the results file (text)
//   {"mode": "distance", "pairs": [[lat1, lon1, lat2, lon2], ...]}  ->  JSON list of [distance, bearing]
const Core = require('../../fieldpack/core.js')
let input = ''
process.stdin.on('data', (c) => (input += c))
process.stdin.on('end', () => {
  const req = JSON.parse(input)
  if (req.mode === 'csv') {
    const block = (ref) => req.pack.blocks.find((b) => b.ref === ref)
    const state = Core.emptyState()
    state.observer = req.observer || ''
    for (const a of req.actions) {
      const rec = { s: a.s, t: a.t }
      if (a.reason) rec.reason = a.reason
      if (a.lat !== undefined) Object.assign(rec, { lat: a.lat, lon: a.lon, acc: a.acc })
      state.trees[Core.key(block(a.ref), a.k)] = rec
    }
    process.stdout.write(Core.exportCsv(req.pack, state, undefined, req.notice))
  } else if (req.mode === 'distance') {
    process.stdout.write(JSON.stringify(req.pairs.map((p) => [Core.distanceM(...p), Core.bearingDeg(...p)])))
  }
})
