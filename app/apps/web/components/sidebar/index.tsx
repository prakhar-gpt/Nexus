"use client"

import { useEffect } from "react"
import { ArrowLeft, Plus } from "lucide-react"
import { type Thread } from "@/lib/api"
import { ThreadList } from "./thread-list"
import { UserProfileFooter } from "./user-profile-footer"

interface SidebarProps {
  roomName: string
  onBackToWorkspaces: () => void
  threads: Thread[]
  activeThreadId: string
  onSelectThread: (threadId: string) => void
  onNewThread: () => void
  onDeleteThread: (threadId: string) => void
  onOpenDataModal: () => void
  onOpenAuthModal: () => void
  attentionWarning?: string | null
  healthSummary?: {
    rows: string | null
    dates: string | null
  }
}

export function Sidebar({
  roomName,
  onBackToWorkspaces,
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  onOpenDataModal,
  onOpenAuthModal,
  attentionWarning,
  healthSummary,
}: SidebarProps) {
  // Global ⌘K / Ctrl+K listener for New Chat
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        onNewThread()
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [onNewThread])

  return (
    <div className="flex h-full w-[260px] flex-col justify-between bg-sidebar p-3 text-sidebar-foreground border-r border-sidebar-border select-none">
      <div className="flex flex-col gap-3 min-h-0 flex-1">
        {/* 1. Header row: Back to Data Rooms + Nexus wordmark */}
        <div className="flex items-center justify-between pb-1">
          <button
            type="button"
            onClick={onBackToWorkspaces}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-sidebar-foreground transition-colors group"
          >
            <ArrowLeft className="h-3.5 w-3.5 group-hover:-translate-x-0.5 transition-transform" />
            <span>Data rooms</span>
          </button>

          <span className="text-xs font-medium tracking-tight text-sidebar-foreground">
            Nexus
          </span>
        </div>

        {/* 2. Data Room block (no card border; subtle accent background) */}
        <div className="flex flex-col gap-1 bg-sidebar-accent/50 p-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-sidebar-foreground truncate max-w-[150px]">
              {roomName}
            </span>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={onOpenDataModal}
                className="text-[11px] text-muted-foreground hover:text-sidebar-foreground underline underline-offset-2 flex items-center gap-1 transition-colors"
              >
                <span>Dataset</span>
                {attentionWarning ? (
                  <span
                    className="h-1.5 w-1.5 rounded-full bg-warn shrink-0"
                    title={attentionWarning}
                  />
                ) : null}
              </button>
            </div>
          </div>

          <p className="font-mono text-[11px] tabular-nums text-muted-foreground truncate">
            {healthSummary?.rows ?? "0 rows"}
            {healthSummary?.dates ? ` · ${healthSummary.dates}` : ""}
          </p>

          <p className="font-mono text-[11px] tabular-nums text-muted-foreground/80">
            Eval 92%
          </p>
        </div>

        {/* 3. New Chat full-width outlined button with ⌘K hint */}
        <button
          type="button"
          onClick={onNewThread}
          className="flex w-full items-center justify-between border border-sidebar-border bg-sidebar px-2.5 py-1.5 text-xs text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
        >
          <div className="flex items-center gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            <span>New chat</span>
          </div>
          <kbd className="font-mono text-[10px] text-muted-foreground border border-sidebar-border px-1">
            ⌘K
          </kbd>
        </button>

        {/* 4. Section label Chats & Thread List */}
        <ThreadList
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={onSelectThread}
          onDeleteThread={onDeleteThread}
        />
      </div>

      {/* 5. Pinned bottom: User Profile Footer */}
      <UserProfileFooter onOpenAuthModal={onOpenAuthModal} />
    </div>
  )
}
