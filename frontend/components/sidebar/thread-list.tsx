"use client"

import React, { useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { Trash2 } from "lucide-react"
import { type Thread } from "@/lib/api"
import { ConfirmDialog } from "@/components/confirm-dialog"

interface ThreadListProps {
  roomId?: string | number
  threads: Thread[]
  activeThreadId?: string
  onSelectThread?: (threadId: string) => void
  onDeleteThread?: (threadId: string) => Promise<void> | void
}

function categorizeThread(dateStr?: string): "Today" | "Yesterday" | "Earlier" {
  if (!dateStr) return "Today"
  const date = new Date(dateStr)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return "Today"
  if (diffDays === 1) return "Yesterday"
  return "Earlier"
}

export function ThreadList({
  roomId = "1",
  threads,
  activeThreadId,
  onSelectThread,
  onDeleteThread,
}: ThreadListProps) {
  const router = useRouter()
  const params = useParams()
  const currentThreadId = activeThreadId || (params?.threadId as string) || ""

  const [threadToDelete, setThreadToDelete] = useState<string | null>(null)
  const shouldGroup = threads.length > 8

  async function handleConfirmDelete() {
    if (!threadToDelete) return
    const id = threadToDelete
    setThreadToDelete(null)

    if (onDeleteThread) {
      await onDeleteThread(id)
    }

    if (currentThreadId === id) {
      router.replace(`/rooms/${roomId}`)
    }
  }

  function renderThreadItem(th: Thread) {
    const isActive = currentThreadId === th.id
    const formattedDate = th.created_at
      ? th.created_at.replace("T", " ").slice(0, 16)
      : undefined

    return (
      <div
        key={th.id}
        title={formattedDate}
        className={`group relative flex items-center justify-between px-2.5 py-1.5 text-xs transition-colors ${isActive
            ? "bg-sidebar-accent text-sidebar-foreground border-l-2 border-foreground font-medium"
            : "text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent/50 border-l-2 border-transparent"
          }`}
      >
        {onSelectThread ? (
          <button
            type="button"
            onClick={() => onSelectThread(th.id)}
            className="flex-1 text-left truncate pr-2 outline-none"
          >
            <span className="truncate block font-normal">{th.title}</span>
          </button>
        ) : (
          <Link
            href={`/rooms/${roomId}/c/${th.id}`}
            prefetch={true}
            className="flex-1 text-left truncate pr-2 outline-none"
          >
            <span className="truncate block font-normal">{th.title}</span>
          </Link>
        )}

        <div className="flex items-center shrink-0">
          {th.turn_count > 0 ? (
            <span className="font-mono text-[10px] tabular-nums text-muted-foreground/70 group-hover:hidden">
              {th.turn_count}
            </span>
          ) : null}

          {onDeleteThread && (
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                setThreadToDelete(th.id)
              }}
              aria-label="Delete thread"
              className="hidden group-hover:inline-flex p-0.5 text-muted-foreground hover:text-destructive transition-colors"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
    )
  }

  let content = null
  if (threads.length === 0) {
    content = (
      <p className="px-2 py-3 text-xs text-muted-foreground select-none">
        No chats yet
      </p>
    )
  } else if (!shouldGroup) {
    content = (
      <div className="flex flex-col gap-0.5">
        {threads.map((th) => renderThreadItem(th))}
      </div>
    )
  } else {
    const groups: Record<"Today" | "Yesterday" | "Earlier", Thread[]> = {
      Today: [],
      Yesterday: [],
      Earlier: [],
    }
    for (const th of threads) {
      const cat = categorizeThread(th.created_at)
      groups[cat].push(th)
    }

    content = (
      <div className="flex flex-col gap-3">
        {(["Today", "Yesterday", "Earlier"] as const).map((cat) => {
          const list = groups[cat]
          if (list.length === 0) return null
          return (
            <div key={cat} className="flex flex-col gap-0.5">
              <span className="px-2 text-[10px] font-mono uppercase tracking-wider text-muted-foreground/60">
                {cat}
              </span>
              {list.map((th) => renderThreadItem(th))}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-y-auto">
      <span className="px-2 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground select-none">
        Chats
      </span>

      {content}

      <ConfirmDialog
        isOpen={!!threadToDelete}
        onClose={() => setThreadToDelete(null)}
        onConfirm={handleConfirmDelete}
        title="Delete this chat thread?"
        description="All messages, SQL queries, and audit logs within this conversation will be permanently removed."
        confirmText="Delete"
      />
    </div>
  )
}
