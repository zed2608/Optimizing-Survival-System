import { useEffect, useRef } from 'react'
import { registerBridge } from './tourController.js'

// Gives the tour engine a handle on the dashboard (R1 W3). The dashboard passes its CURRENT values and setters on every render; the engine calls them through this one object, so a tour always sees the
// latest state. The bridge only navigates and selects: it has no way to create a plan, a link or a field check.
const METHODS = [
  'snapshot', 'restore', 'setPage', 'setSidebar', 'setStep', 'setMode', 'setSpeciesSub', 'setHow', 'setTool', 'setExampleArea', 'openExamplePoint', 'closePoint', 'setView',
  'openExampleMenu', 'closeMenu', 'openSpeciesCard', 'closeSpeciesCard', 'openLatestPlan', 'setLegend', 'hasPlan',
]

export default function useTourBridge(api) {
  const ref = useRef(api)
  useEffect(() => {
    ref.current = api // the engine reads the latest values through the ref
  })
  useEffect(() => {
    const b = { page: () => ref.current.page }
    for (const m of METHODS) b[m] = (...a) => ref.current[m]?.(...a)
    return registerBridge(b)
  }, [])
}
