"use client"

import { useEffect, useRef } from "react"
import { API_URL } from "@/lib/api"

/**
 * Render free tier web services spin down after 15 minutes of inactivity.
 * Pinging every 14 minutes (840,000 ms) guarantees the instance stays awake.
 */
const KEEP_ALIVE_INTERVAL_MS = 14 * 60 * 1000

export function KeepAlive() {
  const timerRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (typeof window === "undefined") return

    const sendPing = async () => {
      try {
        const payload = JSON.stringify({
          client_time: new Date().toISOString(),
          source: "nexus-frontend-keepalive",
        })

        // Use fetch with keepalive: true so requests succeed even during tab transitions
        await fetch(`${API_URL}/ping`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
          },
          body: payload,
          keepalive: true,
        }).catch(() => {
          // Fallback to GET /health if POST is intercepted
          return fetch(`${API_URL}/health`, { method: "GET" }).catch(() => {})
        })
      } catch {
        // Silent catch: keepalive is a non-blocking background heartbeat
      }
    }

    // 1. Immediate heartbeat on mount to warm up any cold instances
    sendPing()

    // 2. Recurring heartbeat every 14 minutes
    timerRef.current = setInterval(sendPing, KEEP_ALIVE_INTERVAL_MS)

    // 3. Wake-up ping whenever user switches focus back to this tab
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        sendPing()
      }
    }
    document.addEventListener("visibilitychange", handleVisibilityChange)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      document.removeEventListener("visibilitychange", handleVisibilityChange)
    }
  }, [])

  return null
}
