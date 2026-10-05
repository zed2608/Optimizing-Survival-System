import { lazy, Suspense, useEffect, useState } from 'react'
import Legacy from './App.legacy.jsx'
import { chooseDashboard } from './dashboardConfig.js'

// The switch between the dashboards, by the end of the address:
//   #/legacy  -> the earlier dashboard (exactly as before)      #/new -> the revamp      #/v2 -> the first v2 page
//   anything else (including #/ and no #) -> DEFAULT_DASHBOARD (see dashboardConfig.js)
// The new pages are loaded only when asked for. The legacy dashboard is loaded the same way as before.
const AppNew = lazy(() => import('./new/AppNew.jsx'))
const App2 = lazy(() => import('./v2/App2.jsx'))

export default function DashboardSwitch() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  const which = chooseDashboard(hash)
  if (which === 'legacy') return <Legacy />
  return (
    <Suspense fallback={<p style={{ padding: 16, color: '#94a3b8', background: '#090d16', height: '100%', margin: 0 }}>Loading the dashboard…</p>}>
      {which === 'new' ? <AppNew /> : <App2 />}
    </Suspense>
  )
}
