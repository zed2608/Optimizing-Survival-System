import { lazy, Suspense } from 'react'

// The tour overlay lives beside the dashboard, above its lazy-loaded pages and its error boundary: opening Weather or Analytics (lazy) cannot close a tour (R1 W3).
const TourHost = lazy(() => import('./new/tours/TourHost.jsx'))

export default function TourRoot() {
  return (
    <Suspense fallback={null}>
      <TourHost />
    </Suspense>
  )
}
