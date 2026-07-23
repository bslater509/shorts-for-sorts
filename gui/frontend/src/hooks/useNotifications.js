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
          const { status, message, level, metadata } = data

          // Determine toast title and action based on event type
          let toastTitle = "Notification"
          let action = undefined

          const isMajor = status === "success" || status === "error"
          
          if (status === "job_failed" && metadata?.job_id) {
            toastTitle = `Job #${metadata.job_id} Failed`
          } else if (isMajor) {
            toastTitle = status === "success" ? "Success" : "Error"
            action = {
              label: "View Gallery",
              onClick: () => navigate("/gallery")
            }
          }

          // 1. Sonner In-App Toast
          if (level === "error") {
            toast.error(toastTitle, { description: message, action })
          } else if (level === "success") {
            toast.success(toastTitle, { description: message, action })
          } else {
            toast.info(toastTitle, { description: message, action })
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
