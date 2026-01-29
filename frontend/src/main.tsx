import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { initializeApp } from './stores/initialize'
import { useUIStore } from './stores/uiStore'

// Initialize app state
void initializeApp().catch((e) => {
  const message = e instanceof Error ? e.message : 'Unknown error'
  useUIStore.getState().showErrorModal('Initialization Failed', message)
  console.error('App initialization failed:', e)
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
