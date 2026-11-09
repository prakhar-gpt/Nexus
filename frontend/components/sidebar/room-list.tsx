"use client"

import React, { useState } from "react"
import { useRouter } from "next/navigation"
import { Trash2, AlertCircle } from "lucide-react"
import type { WorkspaceSummary } from "@/lib/api"
import { ConfirmDialog } from "@/components/confirm-dialog"

interface RoomListProps {
  workspaces: WorkspaceSummary[]
  activeRoomId?: number | string | null
  loading?: boolean
  error?: string | null
  onRetry?: () => void
  onSelectWorkspace?: (id: number) => void
  onDeleteWorkspace?: (id: number) => Promise<void> | void
}

function categorizeDate(dateStr?: string): "Today" | "Yesterday" | "Earlier" {
  if (!dateStr) return "Today"
  const date = new Date(dateStr)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return "Today"
  if (diffDays === 1) return "Yesterday"
  return "Earlier"
}

export function RoomList({
  workspaces,
  activeRoomId,
  loading = false,
  error = null,
  onRetry,
  onSelectWorkspace,
  onDeleteWorkspace,
}: RoomListProps) {
  const router = useRouter()
  const [roomToDelete, setRoomToDelete] = useState<{ id: number; name: string } | null>(null)

  // Sort by last activity / created_at newest first
  const sorted = [...workspaces].sort((a, b) => {
    const da = a.created_at ? new Date(a.created_at).getTime() : 0
    const db = b.created_at ? new Date(b.created_at).getTime() : 0
    return db - da
  })

  const shouldGroup = sorted.length > 8

  function handleOpenRoom(id: number) {
    if (onSelectWorkspace) {
      onSelectWorkspace(id)
    } else {
      router.push(`/rooms/${id}`)
    }
  }

  function renderRoomItem(ws: WorkspaceSummary) {
    const isActive = activeRoomId != null && String(activeRoomId) === String(ws.id)
    const datasetCount = Number(ws.upload_count ?? 1)
    const formattedDate = ws.created_at ? ws.created_at.slice(0, 10) : "Recent"

    return (
      <div
        key={ws.id}
        role="button"
        tabIndex={0}
        aria-current={isActive ? "page" : undefined}
        onClick={() => handleOpenRoom(ws.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            handleOpenRoom(ws.id)
          }
        }}
        className={`group relative flex items-center justify-between px-2.5 py-1.5 text-xs transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-sidebar-ring ${
          isActive
            ? "bg-sidebar-accent text-sidebar-foreground border-l-2 border-foreground font-medium"
            : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent/50 border-l-2 border-transparent"
        }`}
      >
        <div className="flex flex-col min-w-0 flex-1 pr-2">
          <span className="truncate font-medium text-foreground block text-xs" title={ws.name}>
            {ws.name}
          </span>
          <span className="text-[11px] font-mono tabular-nums text-muted-foreground truncate">
            {datasetCount} {datasetCount === 1 ? "dataset" : "datasets"} · {formattedDate}
          </span>
        </div>

        {onDeleteWorkspace && (
          <button
            type="button"
            aria-label={`Delete data room ${ws.name}`}
            onClick={(e) => {
              e.stopPropagation()
              setRoomToDelete({ id: ws.id, name: ws.name })
            }}
            className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity p-1 text-muted-foreground hover:text-destructive shrink-0 max-sm:opacity-100 outline-none focus-visible:ring-1 focus-visible:ring-sidebar-ring"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    )
  }

  return (
    <nav aria-label="Data rooms" className="flex flex-col flex-1 min-h-0">
      <div className="flex items-center justify-between px-2.5 pb-1">
        <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
          Data rooms
        </span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-0.5">
        {/* Loading State: 3 skeleton rows */}
        {loading ? (
          <div className="space-y-1.5 px-2.5 py-1">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-9 w-full bg-sidebar-accent/50 border border-sidebar-border/40 animate-pulse"
              />
            ))}
          </div>
        ) : null}

        {/* Error State: inline banner with retry */}
        {error ? (
          <div
            role="alert"
            className="m-2 p-2 bg-destructive/10 border border-destructive/20 text-xs text-destructive flex items-center justify-between gap-2"
          >
            <div className="flex items-center gap-1.5 min-w-0">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate text-[11px]">{error}</span>
            </div>
            {onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                className="underline underline-offset-2 hover:opacity-80 shrink-0 text-[11px] font-medium"
              >
                Retry
              </button>
            ) : null}
          </div>
        ) : null}

        {/* List items without grouping (<= 8 rooms) */}
        {!loading && !error && !shouldGroup && sorted.map((ws) => renderRoomItem(ws))}

        {/* List items grouped by Today / Yesterday / Earlier (> 8 rooms) */}
        {!loading && !error && shouldGroup && (
          <div className="space-y-3">
            {(["Today", "Yesterday", "Earlier"] as const).map((group) => {
              const inGroup = sorted.filter((w) => categorizeDate(w.created_at) === group)
              if (inGroup.length === 0) return null
              return (
                <div key={group} className="space-y-0.5">
                  <span className="px-2.5 text-[10px] font-medium text-muted-foreground/70 uppercase tracking-wider block py-0.5">
                    {group}
                  </span>
                  {inGroup.map((ws) => renderRoomItem(ws))}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Confirm Delete Dialog */}
      <ConfirmDialog
        isOpen={!!roomToDelete}
        onClose={() => setRoomToDelete(null)}
        onConfirm={async () => {
          if (roomToDelete && onDeleteWorkspace) {
            await onDeleteWorkspace(roomToDelete.id)
            setRoomToDelete(null)
          }
        }}
        title={`Delete "${roomToDelete?.name}"?`}
        description="All datasets and chats in this data room will be permanently removed."
        confirmText="Delete"
      />
    </nav>
  )
}

