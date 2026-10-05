import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import DashboardSwitch from './DashboardSwitch.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <DashboardSwitch />
  </StrictMode>,
)
