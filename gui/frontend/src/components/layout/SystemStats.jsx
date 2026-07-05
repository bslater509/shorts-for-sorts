import { useState, useEffect } from "react"
import { Cpu, MemoryStick } from "lucide-react" // Or whatever icons are available, or simple SVG

export default function SystemStats() {
  const [stats, setStats] = useState({ cpu_percent: 0, memory_percent: 0 })
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    let ws = null
    let reconnectTimer = null
    // cancelled flag prevents the onclose handler from scheduling reconnects after unmount
    let cancelled = false

    const connect = () => {
      if (cancelled) return
      // Use wss:// if https://, ws:// if http://
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
      // We assume the API is on the same host:port
      const host = window.location.host
      ws = new WebSocket(`${protocol}//${host}/api/system_stats`)

      ws.onopen = () => {
        setConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setStats(data)
        } catch (e) {
          console.error("Error parsing stats", e)
        }
      }

      ws.onclose = () => {
        setConnected(false)
        // Only schedule reconnect if the component is still mounted
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, 3000)
        }
      }

      ws.onerror = (err) => {
        console.error("WebSocket error:", err)
        ws.close()
      }
    }

    connect()

    return () => {
      cancelled = true  // Prevent onclose from scheduling more reconnects
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (ws) ws.close()
    }
  }, [])

  if (!connected && stats.cpu_percent === 0) return null

  // Usage Color
  const getUsageColor = (percent) => {
    if (percent < 50) return "bg-green-500"
    if (percent < 80) return "bg-yellow-500"
    return "bg-red-500"
  }

  return (
    <div className="mt-2 bg-secondary/50 rounded-lg p-3 text-xs font-mono flex flex-col gap-2">
      {!connected ? (
        <div className="flex items-center justify-center gap-2 text-red-400 font-medium py-1">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          Offline
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2">
            <span className="w-8 text-zinc-400 text-left">CPU</span>
            <div className="flex-1 h-1.5 bg-background rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all duration-500 ease-out ${getUsageColor(stats.cpu_percent)}`}
                style={{ width: `${Math.min(100, stats.cpu_percent)}%` }}
              />
            </div>
            <span className="w-10 text-right text-zinc-300">{stats.cpu_percent.toFixed(1)}%</span>
          </div>

          <div className="flex items-center gap-2">
            <span className="w-8 text-zinc-400 text-left">MEM</span>
            <div className="flex-1 h-1.5 bg-background rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all duration-500 ease-out ${getUsageColor(stats.memory_percent)}`}
                style={{ width: `${Math.min(100, stats.memory_percent)}%` }}
              />
            </div>
            <span className="w-10 text-right text-zinc-300">{stats.memory_percent.toFixed(1)}%</span>
          </div>
        </>
      )}
    </div>
  )
}
