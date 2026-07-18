import { useEffect, useRef } from "react"
import { toast } from "sonner"
import { useNavigate } from "react-router-dom"

export function useNotifications() {
  const navigate = useNavigate()
  const wsRef = useRef(null)

  useEffect(() => {
    // Removed auto-request for OS notification permissions as iOS requires it to be triggered by a user gesture.

    const connectWebSocket = () => {
      const wsUrl = new URL("/api/notifications", window.location.href)
      wsUrl.protocol = wsUrl.protocol === "https:" ? "wss:" : "ws:"
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const { status, message, level } = data
          
          const isMajor = status === "success" || status === "error"
          
          // Action for major events (success/error)
          const action = isMajor ? {
            label: "View Gallery",
            onClick: () => navigate("/gallery")
          } : undefined

          // 1. Sonner In-App Toast
          if (level === "error") {
            toast.error("Notification", { description: message, action })
          } else if (level === "success") {
            toast.success("Notification", { description: message, action })
          } else {
            toast.info("Notification", { description: message, action })
          }

          // 2. OS-level Notification (only for major events)
          if (isMajor && "Notification" in window && Notification.permission === "granted") {
            const n = new Notification("Shorts for Sorts", {
              body: message
            })
            n.onclick = () => {
              window.focus()
              navigate("/gallery")
            }
          }

        } catch (e) {
          console.error("Error parsing notification message", e)
        }
      }

      ws.onclose = () => {
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000)
      }
    }

    connectWebSocket()

    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null // prevent auto-reconnect
        wsRef.current.close()
      }
    }
  }, [navigate])
}
