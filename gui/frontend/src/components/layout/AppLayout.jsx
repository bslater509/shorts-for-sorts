import { Outlet } from "react-router-dom"
import { useEffect } from "react"
import Sidebar from "./Sidebar"
import SystemStats from "./SystemStats"
import { useAppStore } from "@/store/useAppStore"

export default function AppLayout() {
  const initializeData = useAppStore(state => state.initializeData)

  useEffect(() => {
    initializeData()
  }, [initializeData])
  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-background text-foreground selection:bg-blue-500/30 pb-8">
      <Sidebar />
      <main className="flex-1 overflow-x-hidden min-h-screen flex flex-col">
        <div className="flex-1 p-4 md:p-8 max-w-7xl mx-auto w-full">
          <Outlet />
        </div>
      </main>
      <SystemStats />
    </div>
  )
}
