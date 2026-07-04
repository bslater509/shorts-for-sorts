import { useState, useEffect } from "react"
import { Cpu, MemoryStick } from "lucide-react" // Or whatever icons are available, or simple SVG

export default function SystemStats() {
  const [stats, setStats] = useState({ cpu_percent: 0, memory_percent: 0 })
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    let ws = null
    let reconnectTimer = null

    const connect = () => {
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
        // Reconnect after 3 seconds
        reconnectTimer = setTimeout(connect, 3000)
      }

      ws.onerror = (err) => {
        console.error("WebSocket error:", err)
        ws.close()
      }
    }

    connect()

    return () => {
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
    <div className="fixed bottom-0 left-0 right-0 h-8 bg-zinc-950 border-t border-white/5 flex items-center justify-end px-4 z-50 text-xs font-mono text-zinc-400 gap-6">
      <div className="flex items-center gap-2">
        <span>CPU</span>
        <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div 
            className={`h-full transition-all duration-500 ease-out ${getUsageColor(stats.cpu_percent)}`}
            style={{ width: `${Math.min(100, stats.cpu_percent)}%` }}
          />
        </div>
        <span className="w-8 text-right">{stats.cpu_percent.toFixed(1)}%</span>
      </div>

      <div className="flex items-center gap-2">
        <span>MEM</span>
        <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div 
            className={`h-full transition-all duration-500 ease-out ${getUsageColor(stats.memory_percent)}`}
            style={{ width: `${Math.min(100, stats.memory_percent)}%` }}
          />
        </div>
        <span className="w-8 text-right text-zinc-300">{stats.memory_percent.toFixed(1)}%</span>
      </div>
      
      {!connected && (
        <div className="flex items-center gap-1 text-red-400">
          <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
          Offline
        </div>
      )}
    </div>
  )
}
