"use client"

import { useState } from "react"
import { Plus, Trash2, MessageSquare } from "lucide-react"
import { type Thread } from "@/lib/api"
import { ConfirmDialog } from "@/components/confirm-dialog"

interface ThreadListProps {
  threads: Thread[]
  activeThreadId: string
  onSelectThread: (threadId: string) => void
  onNewThread: () => void
  onDeleteThread: (threadId: string) => void
}

export function ThreadList({
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
}: ThreadListProps) {
  const [threadToDelete, setThreadToDelete] = useState<string | null>(null)

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between px-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/80">
          Chats
        </span>
        <button
          type="button"
          onClick={onNewThread}
          className="text-[11px] text-primary hover:text-primary/80 flex items-center gap-1 font-medium transition-colors"
          title="Start a new chat thread"
        >
          <Plus className="h-3.5 w-3.5" />
          <span>New Chat</span>
        </button>
      </div>

      <div className="flex flex-col gap-0.5 max-h-56 overflow-y-auto pr-0.5">
        {threads.length === 0 ? (
          <button
            type="button"
            onClick={onNewThread}
            className="text-left py-2 px-2.5 rounded border border-dashed border-input/60 text-xs text-muted-foreground hover:bg-accent/40 hover:text-foreground transition-colors"
          >
            + Start your first chat
          </button>
        ) : (
          threads.map((th) => {
            const isActive = activeThreadId === th.id
            return (
              <div
                key={th.id}
                className={`group flex items-center justify-between py-1.5 px-2 rounded text-xs transition-colors ${
                  isActive
                    ? "bg-accent text-accent-foreground font-medium shadow-xs"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/40"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectThread(th.id)}
                  className="flex-1 flex items-center gap-2 text-left truncate min-w-0"
                >
                  <MessageSquare className={`h-3.5 w-3.5 shrink-0 ${isActive ? "text-primary" : "text-muted-foreground/60"}`} />
                  <span className="truncate">{th.title}</span>
                </button>

                <div className="flex items-center gap-1 shrink-0 ml-1">
                  {th.turn_count > 0 ? (
                    <span className="text-[10px] text-muted-foreground/60 font-mono px-1">
                      {th.turn_count}
                    </span>
                  ) : null}

                  {/* Delete Thread Button opening Shadcn AlertDialog */}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      setThreadToDelete(th.id)
                    }}
                    className="opacity-0 group-hover:opacity-100 p-0.5 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all"
                    title="Delete chat"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Shadcn Alert Dialog for Chat Deletion */}
      <ConfirmDialog
        isOpen={!!threadToDelete}
        onClose={() => setThreadToDelete(null)}
        onConfirm={() => {
          if (threadToDelete) {
            onDeleteThread(threadToDelete)
            setThreadToDelete(null)
          }
        }}
        title="Delete Conversation"
        description="Are you sure you want to delete this chat thread? This conversation history will be permanently cleared from this data room."
        confirmText="Delete Chat"
      />
    </div>
  )
}
