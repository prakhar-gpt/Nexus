"use client"

import React, { useRef, use } from "react"
import { useRouter } from "next/navigation"
import { ArrowUpRight } from "lucide-react"
import { useRoom } from "@/lib/room-context"
import { RoomGate } from "@/components/room-gate"
import { useChatStore, useThreadState } from "@/lib/chat-store"
import { DEFAULT_SUGGESTIONS } from "@/components/chat-pane"
import type { ComposerHandle } from "@/components/composer"

export default function NewChatRoomPage({
  params,
}: {
  params: Promise<{ roomId: string }>
}) {
  const unwrapped = use(params)
  const roomId = unwrapped.roomId

  const router = useRouter()
  const { room, status, mutateRoom } = useRoom()
  const { getThreadState, setDraft, ask, abortStream } = useChatStore()

  // Track the ephemeral thread ID for the new chat
  const ephemeralThreadIdRef = useRef(`thread-${Date.now().toString(36)}`)
  const currentThreadId = ephemeralThreadIdRef.current

  const threadState = useThreadState(roomId, currentThreadId)
  const composerRef = useRef<ComposerHandle>(null)

  async function handleAsk(question: string) {
    const text = question.trim()
    if (!text) return

    // Optimistically register thread in room sidebar
    const title = text.length > 35 ? text.slice(0, 32) + "…" : text
    mutateRoom((curr: any) => {
      if (!curr) return curr
      const existing = curr.threads || []
      return {
        ...curr,
        threads: [
          { id: currentThreadId, title, created_at: new Date().toISOString(), turn_count: 1 },
          ...existing,
        ],
      }
    })

    // Start stream; on first token, replace URL without flicker or remount
    await ask(roomId, currentThreadId, text, (targetId) => {
      router.replace(`/rooms/${roomId}/c/${targetId}`)
    })
  }

  const isReady = status.type === "ready"

  return (
    <section className="relative flex h-full min-h-0 min-w-0 flex-1 flex-col bg-background">
      {/* Scrollable messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-8">
        <div className="mx-auto flex h-full w-full max-w-[720px] flex-col justify-center py-12">
          {isReady ? (
            <>
              <h1 className="text-[32px] font-medium tracking-tight text-foreground select-none">
                What should we look at?
              </h1>

              <div className="mt-8 flex flex-col border-y border-border divide-y divide-border">
                {DEFAULT_SUGGESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => handleAsk(q)}
                    className="group flex w-full items-center justify-between py-3.5 text-left text-[15px] text-muted-foreground hover:text-foreground transition-colors outline-none focus-visible:bg-accent/40"
                  >
                    <span className="font-normal">{q}</span>
                    <ArrowUpRight className="h-4 w-4 text-muted-foreground/60 group-hover:text-foreground transition-colors shrink-0 ml-2" />
                  </button>
                ))}
              </div>
            </>
          ) : null}
        </div>
      </div>

      {/* Gated Composer Replacement */}
      <RoomGate
        ref={composerRef}
        status={status}
        roomId={roomId}
        datasetName={room?.name ?? "Superstore"}
        draft={threadState.draft}
        busy={threadState.busy}
        onDraft={(val) => setDraft(roomId, currentThreadId, val)}
        onAsk={handleAsk}
        onAbort={() => abortStream(roomId, currentThreadId)}
      />
    </section>
  )
}
