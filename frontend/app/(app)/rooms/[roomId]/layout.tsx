"use client"

import React, { useEffect, useState, useRef, use } from "react"
import { useRouter, usePathname } from "next/navigation"
import { Menu, X } from "lucide-react"
import { Sidebar } from "@/components/sidebar"
import { useResource } from "@/lib/use-resource"
import { API_URL, apiFetch, type Room } from "@/lib/api"
import { deriveRoomStatus } from "@/lib/room-status"
import { RoomContext } from "@/lib/room-context"
import { useChatStore } from "@/lib/chat-store"

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
  datasets: [],
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
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { uploadFile } = useChatStore()

  const {
    data: room,
    error,
    isLoading,
    mutate: mutateRoom,
  } = useResource(`room:${roomId}`, () => fetchRoomData(roomId))

  const status = deriveRoomStatus(room)

  // Derive active thread ID and selection state
  const activeThreadId = pathname.includes("/c/")
    ? pathname.split("/c/")[1]?.split("/")[0]
    : undefined

  const activeThread = room?.threads?.find((t) => t.id === activeThreadId)
  const datasets = room?.datasets || []
  const allDatasetIds = datasets.map((d) => d.id)

  const [ephemeralSelectedIds, setEphemeralSelectedIds] = useState<number[] | null>(null)

  // When on an existing thread, read its selection; otherwise read ephemeral or all
  const selectedDatasetIds = activeThread?.selected_dataset_ids
    ?? (ephemeralSelectedIds ?? allDatasetIds)

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

  const handleToggleDataset = async (datasetId: number, checked: boolean) => {
    const current = selectedDatasetIds
    const next = checked
      ? Array.from(new Set([...current, datasetId]))
      : current.filter((id) => id !== datasetId)

    if (activeThreadId) {
      mutateRoom((curr: Room | undefined) => {
        if (!curr) return curr!
        return {
          ...curr,
          threads: (curr.threads || []).map((t) =>
            t.id === activeThreadId ? { ...t, selected_dataset_ids: next } : t
          ),
        }
      })
      try {
        await apiFetch(`${API_URL}/workspaces/${roomId}/threads/${activeThreadId}/datasets`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dataset_ids: next }),
        })
      } catch {
        mutateRoom()
      }
    } else {
      setEphemeralSelectedIds(next)
    }
  }

  const handleRemoveDataset = async (datasetId: number) => {
    mutateRoom((curr: Room | undefined) => {
      if (!curr) return curr!
      return {
        ...curr,
        datasets: (curr.datasets || []).filter((d) => d.id !== datasetId),
        threads: (curr.threads || []).map((t) => ({
          ...t,
          selected_dataset_ids: (t.selected_dataset_ids || []).filter((id) => id !== datasetId),
        })),
      }
    })
    try {
      await apiFetch(`${API_URL}/workspaces/${roomId}/datasets/${datasetId}`, {
        method: "DELETE",
      })
    } catch {
      mutateRoom()
    }
  }

  const handleRenameDataset = async (datasetId: number, newLabel: string) => {
    mutateRoom((curr: Room | undefined) => {
      if (!curr) return curr!
      return {
        ...curr,
        datasets: (curr.datasets || []).map((d) =>
          d.id === datasetId ? { ...d, table_label: newLabel } : d
        ),
      }
    })
    try {
      await apiFetch(`${API_URL}/workspaces/${roomId}/datasets/${datasetId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ table_label: newLabel }),
      })
    } catch {
      mutateRoom()
    }
  }

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ""
    const targetThread = activeThreadId || `thread-${Date.now().toString(36)}`
    await uploadFile(roomId, targetThread, file, (tId) => {
      router.replace(`/rooms/${roomId}/c/${tId}`)
    })
  }

  const pendingUploads = (room?.uploads || [])
    .filter((u) => ["received", "processing", "uploading", "profiling", "needs_schema_review"].includes(u.status))
    .map((u) => ({
      id: u.id,
      fileName: u.original_name,
      status: u.status,
    }))

  const pendingUpload = (room?.uploads || []).find((u) =>
    ["received", "processing", "uploading", "profiling", "needs_schema_review"].includes(u.status)
  )
  const isUploadRunning = Boolean(
    pendingUpload && ["received", "processing", "uploading", "profiling"].includes(pendingUpload.status)
  )
  const isReviewPending = Boolean(
    pendingUpload && pendingUpload.status === "needs_schema_review"
  )

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
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx"
        className="hidden"
        onChange={handleFileSelected}
      />
      <div className="flex h-svh w-full flex-col bg-background text-foreground md:flex-row overflow-hidden">
        {/* Desktop Sidebar: 260px fixed, never remounts across threads */}
        <aside className="hidden md:block h-full shrink-0">
          <Sidebar
            mode="room"
            roomId={roomId}
            roomName={room?.name ?? "Data Room"}
            threads={room?.threads || []}
            datasets={datasets}
            pendingUploads={pendingUploads}
            selectedDatasetIds={selectedDatasetIds}
            activeThreadId={activeThreadId}
            status={status}
            isUploadRunning={isUploadRunning}
            isReviewPending={isReviewPending}
            onToggleDataset={handleToggleDataset}
            onAddDatasetClick={() => fileInputRef.current?.click()}
            onRemoveDataset={handleRemoveDataset}
            onRenameDataset={handleRenameDataset}
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
                mode="room"
                roomId={roomId}
                roomName={room?.name ?? "Data Room"}
                threads={room?.threads || []}
                datasets={datasets}
                pendingUploads={pendingUploads}
                selectedDatasetIds={selectedDatasetIds}
                activeThreadId={activeThreadId}
                status={status}
                isUploadRunning={isUploadRunning}
                isReviewPending={isReviewPending}
                onToggleDataset={handleToggleDataset}
                onAddDatasetClick={() => fileInputRef.current?.click()}
                onRemoveDataset={handleRemoveDataset}
                onRenameDataset={handleRenameDataset}
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
