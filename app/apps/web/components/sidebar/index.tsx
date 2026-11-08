"use client"

import { Plus, Database } from "lucide-react"
import { type Mapping, type Thread, type WorkspaceSummary } from "@/lib/api"
import { ThreadList } from "./thread-list"
import { WorkspaceSelector } from "./workspace-selector"
import { IngestionSection } from "./ingestion-section"
import { UserProfileFooter } from "./user-profile-footer"

interface SidebarProps {
  roomName: string
  workspaces: WorkspaceSummary[]
  currentRoomId: number | null
  onSelectWorkspace: (id: number) => void
  onOpenCreateWorkspace: () => void
  onDeleteWorkspace: (id: number) => void
  threads: Thread[]
  activeThreadId: string
  onSelectThread: (threadId: string) => void
  onNewThread: () => void
  onDeleteThread: (threadId: string) => void
  fileName: string | null
  status: string | null
  reason: string | null
  stages: { stage: string; status: string }[]
  mappings: Mapping[]
  health: {
    rows: string
    first_order: string
    last_order: string
    revenue: string
    quarantine: string
  } | null
  quarantine: { row_number: string; reason: string }[]
  uploadId: string | null
  error: string | null
  confirming: boolean
  scores: Record<string, number> | null
  runningEval: boolean
  onFile: (file: File) => void
  onConfirm: (decisions: Record<string, string>) => void
  onRunEval: () => void
  onOpenAuthModal: () => void
}

export function Sidebar({
  roomName,
  workspaces,
  currentRoomId,
  onSelectWorkspace,
  onOpenCreateWorkspace,
  onDeleteWorkspace,
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  fileName,
  status,
  reason,
  stages,
  mappings,
  health,
  quarantine,
  uploadId,
  error,
  confirming,
  scores,
  runningEval,
  onFile,
  onConfirm,
  onRunEval,
  onOpenAuthModal,
}: SidebarProps) {
  const rows = health?.rows && health.rows !== "0" ? `${Number(health.rows).toLocaleString()} rows` : null
  const dates =
    health?.first_order && health.last_order
      ? `${health.first_order} – ${health.last_order}`
      : null

  return (
    <div className="flex h-full flex-col justify-between overflow-y-auto px-3.5 py-4 text-[13px]">
      <div className="flex flex-col gap-5">
        {/* App Header & Brand */}
        <div className="flex items-center justify-between pb-1 px-1">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded bg-primary text-[11px] font-bold text-primary-foreground tracking-wider shadow-xs">
              N
            </span>
            <span className="font-semibold text-sm tracking-tight text-foreground">Nexus</span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono ml-0.5">
              Copilot
            </span>
          </div>

          <button
            type="button"
            onClick={onNewThread}
            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-accent/40 transition-colors"
            title="Start new chat"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        {/* Data Room Switcher (Shadcn Dropdown) */}
        <WorkspaceSelector
          workspaces={workspaces}
          currentRoomId={currentRoomId}
          onSelectWorkspace={onSelectWorkspace}
          onOpenCreateModal={onOpenCreateWorkspace}
          onDeleteWorkspace={onDeleteWorkspace}
          healthSummary={{ rows, dates }}
        />

        {/* Conversation Threads (Claude Style) */}
        <ThreadList
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={onSelectThread}
          onNewThread={onNewThread}
          onDeleteThread={onDeleteThread}
        />

        {/* Ingestion & Quarantine Section */}
        <IngestionSection
          fileName={fileName}
          status={status}
          reason={reason}
          stages={stages}
          mappings={mappings}
          uploadId={uploadId}
          quarantine={quarantine}
          confirming={confirming}
          onFile={onFile}
          onConfirm={onConfirm}
        />

        {error ? (
          <p className="text-xs text-destructive px-1" role="alert">
            {error}
          </p>
        ) : null}
      </div>

      {/* User Profile & Auth Footer */}
      <UserProfileFooter
        scores={scores}
        runningEval={runningEval}
        onRunEval={onRunEval}
        onOpenAuthModal={onOpenAuthModal}
      />
    </div>
  )
}
