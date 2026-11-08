"use client"

import { Plus, ArrowLeft, Table2, Upload, Sparkles, Check, ChevronRight } from "lucide-react"
import { type Mapping, type Thread, type WorkspaceSummary } from "@/lib/api"
import { ThreadList } from "./thread-list"
import { UserProfileFooter } from "./user-profile-footer"
import { Button } from "@/components/ui/button"

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
  healthSummary,
}: SidebarProps) {
  return (
    <div className="flex h-full flex-col justify-between overflow-y-auto px-3.5 py-4 text-[13px]">
      <div className="flex flex-col gap-4">
        {/* Clean Back to Data Rooms Navigation */}
        <div className="flex items-center justify-between pb-2 border-b border-sidebar-border/60">
          <button
            type="button"
            onClick={onBackToWorkspaces}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors group"
            title="Return to Data Rooms Menu"
          >
            <ArrowLeft className="h-3.5 w-3.5 group-hover:-translate-x-0.5 transition-transform" />
            <span className="font-medium">Data Rooms</span>
          </button>

          <span className="text-[11px] font-semibold text-foreground tracking-tight">
            Nexus
          </span>
        </div>

        {/* Current Data Room Card with Dataset Health Action */}
        <div className="flex flex-col gap-1 p-2 rounded-lg bg-sidebar-accent/30 border border-sidebar-border/80">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-foreground truncate">{roomName}</span>
            <button
              type="button"
              onClick={onOpenDataModal}
              className="text-[11px] text-primary hover:underline font-medium"
            >
              Dataset
            </button>
          </div>

          <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-0.5">
            <span>{healthSummary?.rows ?? "0 rows"}</span>
            {healthSummary?.dates ? (
              <span className="font-mono text-[10px] truncate max-w-[120px]">{healthSummary.dates}</span>
            ) : null}
          </div>
        </div>

        {/* Clean, Focused Conversation Threads List */}
        <div className="flex-1 flex flex-col min-h-0">
          <ThreadList
            threads={threads}
            activeThreadId={activeThreadId}
            onSelectThread={onSelectThread}
            onNewThread={onNewThread}
            onDeleteThread={onDeleteThread}
          />
        </div>
      </div>

      {/* User Profile Footer with Working Log Out */}
      <UserProfileFooter onOpenAuthModal={onOpenAuthModal} />
    </div>
  )
}
