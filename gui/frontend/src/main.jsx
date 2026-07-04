import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'

// Helper to set dark mode class if system prefers it
function ThemeProvider({ children }) {
  useEffect(() => {
    // For now we default to dark theme for that premium aesthetic
    document.documentElement.classList.add('dark')
  }, [])
  return children
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
)
