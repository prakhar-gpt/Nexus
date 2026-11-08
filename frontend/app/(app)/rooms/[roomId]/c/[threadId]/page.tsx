"use client"

import React, { useEffect, useState, use } from "react"
import Link from "next/link"
import { ArrowLeft, Plus } from "lucide-react"
import { buttonVariants } from "@/components/ui/button"
import { useRoom } from "@/lib/room-context"
import { ChatPane } from "@/components/chat-pane"
import { RoomGate } from "@/components/room-gate"
import { useChatStore, useThreadState, getThreadStateDirect } from "@/lib/chat-store"
import { API_URL, apiFetch, type Turn } from "@/lib/api"

export default function ExistingThreadPage({
  params,
}: {
  params: Promise<{ roomId: string; threadId: string }>
}) {
  const unwrapped = use(params)
  const { roomId, threadId } = unwrapped

  const { room, status } = useRoom()
  const {
    getThreadState,
    setDraft,
    initThreadTurns,
    ask,
    abortStream,
    recordFeedback,
  } = useChatStore()

  const [loadingTurns, setLoadingTurns] = useState(false)
  const [threadExists, setThreadExists] = useState(true)
  const [toastMessage, setToastMessage] = useState<string | null>(null)

  function showToast(msg: string) {
    setToastMessage(msg)
    setTimeout(() => setToastMessage(null), 4000)
  }

  // Load thread turns on mount or thread switch
  useEffect(() => {
    const currentState = getThreadStateDirect(roomId, threadId)
    if (currentState.messages.length > 0) return

    let active = true
    setLoadingTurns(true)

    async function load() {
      try {
        const res = await apiFetch(`${API_URL}/workspaces/${roomId}/threads/${threadId}/turns`)
        if (res.ok) {
          const turns = (await res.json()) as Turn[]
          if (active) {
            initThreadTurns(roomId, threadId, turns)
            setThreadExists(true)
          }
          return
        }

        // Fallback: check room.turns
        if (room?.turns) {
          const filtered = room.turns.filter((t) => (t.thread_id || "default") === threadId)
          if (active) {
            initThreadTurns(roomId, threadId, filtered)
            setThreadExists(true)
          }
          return
        }

        if (active) setThreadExists(false)
      } catch {
        if (active && room?.turns) {
          const filtered = room.turns.filter((t) => (t.thread_id || "default") === threadId)
          initThreadTurns(roomId, threadId, filtered)
        }
      } finally {
        if (active) setLoadingTurns(false)
      }
    }

    load()
    return () => {
      active = false
    }
  }, [roomId, threadId, room, getThreadState, initThreadTurns])

  const threadState = useThreadState(roomId, threadId)

  // Unknown thread ID: show calm inline notice, not a full-page 404
  if (!threadExists && !loadingTurns && threadState.messages.length === 0) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center p-6 text-center">
        <h2 className="text-base font-medium text-foreground">
          This chat doesn't exist
        </h2>
        <p className="mt-1 text-xs text-muted-foreground mb-4">
          This conversation may have been deleted or never created.
        </p>
        <Link
          href={`/rooms/${roomId}`}
          className={buttonVariants({ size: "sm", className: "h-8 text-xs font-medium" })}
        >
          <Plus className="h-3.5 w-3.5 mr-1" />
          <span>New chat</span>
        </Link>
      </div>
    )
  }

  if (loadingTurns && threadState.messages.length === 0) {
    return (
      <div className="flex h-full w-full flex-col justify-between p-8 animate-pulse">
        <div className="mx-auto flex h-full w-full max-w-[720px] flex-col gap-6 py-6">
          <div className="h-4 bg-muted w-1/3 self-end" />
          <div className="h-20 bg-muted/40 w-full" />
          <div className="h-4 bg-muted w-1/4 self-end" />
          <div className="h-24 bg-muted/40 w-full" />
        </div>
        <div className="mx-auto w-full max-w-[720px] h-12 bg-muted/30 border border-border" />
      </div>
    )
  }

  return (
    <div className="relative flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <ChatPane
        draft={threadState.draft}
        messages={threadState.messages}
        busy={threadState.busy}
        datasetName={room?.name ?? "Superstore"}
        onDraft={(val) => setDraft(roomId, threadId, val)}
        onAsk={(q) => ask(roomId, threadId, q)}
        onAbort={() => abortStream(roomId, threadId)}
        onFeedback={recordFeedback}
        onToast={showToast}
      />

      {toastMessage && (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 border border-border bg-popover px-4 py-2 text-xs text-popover-foreground shadow-none animate-in fade-in"
        >
          {toastMessage}
        </div>
      )}
    </div>
  )
}
