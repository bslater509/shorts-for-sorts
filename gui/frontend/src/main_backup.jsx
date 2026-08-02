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

// Forward frontend errors to backend terminal (production only)
// Guarded to avoid spamming backend with React dev warnings and to prevent
// the override from chaining on each Vite hot-reload in development.
if (import.meta.env.PROD) {
  const originalError = console.error;
  console.error = (...args) => {
    originalError(...args);
    try {
      const msg = args.map(a => (a instanceof Error ? a.stack : (typeof a === 'object' ? JSON.stringify(a) : String(a)))).join(' ');
      fetch('/api/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ level: 'error', message: msg })
      }).catch(() => {});
    } catch (e) {
      // Ignore circular JSON errors
    }
  };
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
