import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import ControlPanel from './components/ControlPanel.tsx'
import Dashboard from './components/Dashboard.tsx'
import InvernaderoDashboard from './components/monitor_invernadero/InvernaderoDashboard.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
   {/* <App /> */}
  {/* <ControlPanel /> */}
  {/* <Dashboard /> */}
   <InvernaderoDashboard />
  </StrictMode>,
)