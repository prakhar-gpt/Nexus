"use client"

import React, { useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowLeft, Plus, Loader2 } from "lucide-react"
import { type Thread } from "@/lib/api"
import type { RoomStatus } from "@/lib/room-status"
import { ThreadList } from "./thread-list"
import { UserProfileFooter } from "./user-profile-footer"

interface SidebarProps {
  roomId?: string | number
  roomName: string
  threads: Thread[]
  activeThreadId?: string
  status?: RoomStatus
  onBackToWorkspaces?: () => void
  onSelectThread?: (threadId: string) => void
  onNewThread?: () => void
  onDeleteThread?: (threadId: string) => Promise<void> | void
  onOpenDataModal?: () => void
  onOpenAuthModal?: () => void
  attentionWarning?: string | null
  healthSummary?: {
    rows: string | null
    dates: string | null
  }
}

export function Sidebar({
  roomId = "1",
  roomName,
  threads,
  activeThreadId,
  status,
  onBackToWorkspaces,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  onOpenDataModal,
  onOpenAuthModal,
  attentionWarning,
  healthSummary,
}: SidebarProps) {
  const router = useRouter()

  // Global ⌘K / Ctrl+K listener for New Chat
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        if (onNewThread) {
          onNewThread()
        } else {
          router.push(`/rooms/${roomId}`)
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [router, roomId, onNewThread])

  const isIngesting = status?.type === "ingesting"

  return (
    <div className="flex h-full w-[260px] flex-col justify-between bg-sidebar p-3 text-sidebar-foreground border-r border-sidebar-border select-none">
      <div className="flex flex-col gap-3 min-h-0 flex-1">
        {/* 1. Top row: Back to Data rooms + Nexus wordmark */}
        <div className="flex items-center justify-between pb-1">
          {onBackToWorkspaces ? (
            <button
              type="button"
              onClick={onBackToWorkspaces}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-sidebar-foreground transition-colors group"
            >
              <ArrowLeft className="h-3.5 w-3.5 group-hover:-translate-x-0.5 transition-transform" />
              <span>Data rooms</span>
            </button>
          ) : (
            <Link
              href="/rooms"
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-sidebar-foreground transition-colors group"
            >
              <ArrowLeft className="h-3.5 w-3.5 group-hover:-translate-x-0.5 transition-transform" />
              <span>Data rooms</span>
            </Link>
          )}

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

            {isIngesting ? (
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-muted-foreground font-mono">
                  Analyzing…
                </span>
              </div>
            ) : null}
          </div>

          {healthSummary?.dates ? (
            <p className="font-mono text-[11px] tabular-nums text-muted-foreground truncate">
              {healthSummary.dates}
            </p>
          ) : null}
        </div>

        {/* 3. New Chat full-width outlined button with ⌘K hint */}
        {onNewThread ? (
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
        ) : (
          <Link
            href={`/rooms/${roomId}`}
            className="flex w-full items-center justify-between border border-sidebar-border bg-sidebar px-2.5 py-1.5 text-xs text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
          >
            <div className="flex items-center gap-1.5">
              <Plus className="h-3.5 w-3.5" />
              <span>New chat</span>
            </div>
            <kbd className="font-mono text-[10px] text-muted-foreground border border-sidebar-border px-1">
              ⌘K
            </kbd>
          </Link>
        )}

        {/* 4. Chats Section & Thread List */}
        <ThreadList
          roomId={roomId}
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={onSelectThread}
          onDeleteThread={onDeleteThread as any}
        />
      </div>

      {/* 5. Pinned bottom: User Profile Footer */}
      <UserProfileFooter />
    </div>
  )
}
