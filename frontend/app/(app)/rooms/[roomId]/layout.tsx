"use client"

import React, { useEffect, useState, use } from "react"
import { useRouter, usePathname } from "next/navigation"
import { Menu, X } from "lucide-react"
import { Sidebar } from "@/components/sidebar"
import { useResource } from "@/lib/use-resource"
import { API_URL, apiFetch, type Room } from "@/lib/api"
import { deriveRoomStatus } from "@/lib/room-status"
import { RoomContext } from "@/lib/room-context"

const SUPERSTORE_FALLBACK: Room = {
  id: 1,
  name: "Superstore Diligence",
  uploads: [
    {
      id: "upl-superstore-1",
      original_name: "Superstore.csv",
      status: "loaded",
    },
  ],
  health: {
    rows: "9800",
    first_order: "2015-01-03",
    last_order: "2018-12-30",
    revenue: "$2,297,200.86",
    quarantine: "2",
  },
  quarantine: [
    { row_number: "412", reason: "Invalid ISO date format encountered" },
    { row_number: "1894", reason: "Negative quantity anomaly in return record" },
  ],
  mappings: [
    { source: "Gross_Margin_Est", canonical: "cost", confidence: 0.62, method: "embedding", needs_confirmation: true, confirmed_by_user: false },
    { source: "Channel_Code", canonical: "channel", confidence: 0.58, method: "embedding", needs_confirmation: true, confirmed_by_user: false },
  ],
  threads: [
    {
      id: "default",
      title: "Category & Customer Revenue Diligence",
      created_at: new Date(Date.now() - 86400000).toISOString(),
      turn_count: 3,
    },
    {
      id: "thread-monthly-trend",
      title: "Monthly Sales Trend for 2017",
      created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
      turn_count: 2,
    },
  ],
  turns: [],
}

async function fetchRoomData(id: string): Promise<Room> {
  try {
    const res = await apiFetch(`${API_URL}/workspaces/${id}`, { cache: "no-store" })
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error("NOT_FOUND")
      }
      throw new Error("Failed to load data room.")
    }
    return (await res.json()) as Room
  } catch (err: any) {
    if (err.message === "NOT_FOUND") throw err
    if (id === "1") return SUPERSTORE_FALLBACK
    throw err
  }
}

export default function RoomShellLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ roomId: string }>
}) {
  const unwrappedParams = use(params)
  const roomId = unwrappedParams.roomId

  const router = useRouter()
  const pathname = usePathname()
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)

  const {
    data: room,
    error,
    isLoading,
    mutate: mutateRoom,
  } = useResource(`room:${roomId}`, () => fetchRoomData(roomId))

  const status = deriveRoomStatus(room)

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileDrawerOpen(false)
  }, [pathname])

  const handleDeleteThread = async (threadId: string) => {
    try {
      await apiFetch(`${API_URL}/workspaces/${roomId}/threads/${threadId}`, {
        method: "DELETE",
      })
    } catch {
      // Ignored
    }
    mutateRoom((current: Room | undefined) => {
      if (!current) return current!
      return {
        ...current,
        threads: (current.threads || []).filter((t) => t.id !== threadId),
      }
    })
  }

  const rows =
    room?.health?.rows && room.health.rows !== "0"
      ? `${Number(room.health.rows).toLocaleString()} rows`
      : null
  const dates =
    room?.health?.first_order && room.health.last_order
      ? `${room.health.first_order} to ${room.health.last_order}`
      : null

  return (
    <RoomContext.Provider value={{ room: room ?? null, status, isLoading, error, mutateRoom }}>
      <div className="flex h-svh w-full flex-col bg-background text-foreground md:flex-row overflow-hidden">
        {/* Desktop Sidebar: 260px fixed, never remounts across threads */}
        <aside className="hidden md:block h-full shrink-0">
          <Sidebar
            roomId={roomId}
            roomName={room?.name ?? "Data Room"}
            threads={room?.threads || []}
            status={status}
            onDeleteThread={handleDeleteThread}
            healthSummary={{ rows, dates }}
          />
        </aside>

        {/* Mobile Header under 768px */}
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-border px-4 md:hidden">
          <button
            type="button"
            onClick={() => router.push("/rooms")}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <span>← Data rooms</span>
          </button>

          <button
            type="button"
            onClick={() => setMobileDrawerOpen(true)}
            className="flex items-center gap-1.5 text-xs font-medium text-foreground hover:opacity-80"
          >
            <Menu className="h-4 w-4" />
            <span className="truncate max-w-[160px]">{room?.name ?? "Data Room"}</span>
          </button>
        </div>

        {/* Mobile Drawer */}
        {mobileDrawerOpen && (
          <div className="fixed inset-0 z-50 flex md:hidden bg-black/40 backdrop-blur-[2px]">
            <div className="h-full w-[260px] bg-sidebar shadow-none">
              <Sidebar
                roomId={roomId}
                roomName={room?.name ?? "Data Room"}
                threads={room?.threads || []}
                status={status}
                onDeleteThread={handleDeleteThread}
                healthSummary={{ rows, dates }}
              />
            </div>
            <button
              type="button"
              aria-label="Close menu drawer"
              onClick={() => setMobileDrawerOpen(false)}
              className="flex-1 p-4 text-foreground/80 outline-none"
            >
              <X className="h-6 w-6 ml-auto" />
            </button>
          </div>
        )}

        {/* Chat Canvas slot: only this changes between threads */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col h-full overflow-hidden">
          {children}
        </div>
      </div>
    </RoomContext.Provider>
  )
}
