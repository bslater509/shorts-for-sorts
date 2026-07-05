import { Outlet } from "react-router-dom"
import { useEffect, useRef } from "react"
import Sidebar from "./Sidebar"
import { useAppStore } from "@/store/useAppStore"
import * as Sentry from "@sentry/react"

export default function AppLayout() {
  const initializeData = useAppStore(state => state.initializeData)

  const settings = useAppStore(state => state.settings)

  useEffect(() => {
    initializeData()
  }, [initializeData])

  // Guard against re-initialization on every settings re-fetch
  const sentryInitialized = useRef(false)

  useEffect(() => {
    if (settings?.sentry_dsn && !sentryInitialized.current) {
      Sentry.init({
        dsn: settings.sentry_dsn,
        // 10% sampling — 100% (1.0) would cause significant performance overhead
        tracesSampleRate: 0.1,
      });
      sentryInitialized.current = true
    }
  }, [settings?.sentry_dsn])
  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-background text-foreground selection:bg-blue-500/30 pb-8 md:pb-0">
      <Sidebar />
      <main className="flex-1 overflow-x-hidden min-h-screen flex flex-col">
        <div className="flex-1 p-4 md:p-8 max-w-7xl mx-auto w-full">
          <Sentry.ErrorBoundary fallback={
            <div className="flex flex-col items-center justify-center h-full text-center p-8 bg-card rounded-xl border border-red-500/20 text-red-400">
              <h2 className="text-xl font-bold mb-2">Something went wrong</h2>
              <p className="text-sm opacity-80">Our team has been notified. Please refresh the page or try again.</p>
            </div>
          }>
            <Outlet />
          </Sentry.ErrorBoundary>
        </div>
      </main>
    </div>
  )
}
