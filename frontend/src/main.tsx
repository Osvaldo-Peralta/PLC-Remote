import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import ControlPanel from './components/ControlPanel.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
   {/* <App /> */}
   <ControlPanel />
  </StrictMode>,
)
