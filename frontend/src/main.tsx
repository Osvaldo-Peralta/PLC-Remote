import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import InvernaderoDashboard from './components/monitor_invernadero/InvernaderoDashboard.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
   {/* <App /> */}
  {/* <ControlPanel /> */}
  {/* <Dashboard /> */}
   <InvernaderoDashboard />
  </StrictMode>,
)