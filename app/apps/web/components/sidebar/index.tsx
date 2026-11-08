"use client"

import { RefreshCw } from "lucide-react"
import { type Mapping, type Thread, type WorkspaceSummary } from "@/lib/api"
import { ThreadList } from "./thread-list"
import { WorkspaceSelector } from "./workspace-selector"
import { IngestionSection } from "./ingestion-section"

const SCORE_LABEL: Record<string, string> = {
  sql_correctness: "SQL",
  numeric_faithfulness: "Numbers",
  refusal_accuracy: "Refusals",
}

interface SidebarProps {
  roomName: string
  workspaces: WorkspaceSummary[]
  currentRoomId: number | null
  onSelectWorkspace: (id: number) => void
  onCreateWorkspace: (name: string) => void
  onOpenWorkspacesModal: () => void
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
}

export function Sidebar({
  roomName,
  workspaces,
  currentRoomId,
  onSelectWorkspace,
  onCreateWorkspace,
  onOpenWorkspacesModal,
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
}: SidebarProps) {
  const rows = health?.rows && health.rows !== "0" ? `${Number(health.rows).toLocaleString()} rows` : null
  const dates =
    health?.first_order && health.last_order
      ? `${health.first_order} – ${health.last_order}`
      : null

  return (
    <div className="flex h-full flex-col justify-between overflow-y-auto px-4 py-4 text-[13px]">
      <div className="flex flex-col gap-4">
        {/* App Branding */}
        <div className="flex items-center justify-between pb-3 border-b border-sidebar-border/60">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded bg-primary text-[11px] font-bold text-primary-foreground tracking-wider shadow-xs">
              N
            </span>
            <span className="font-semibold text-sm tracking-tight text-foreground">Nexus</span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-mono ml-0.5">
              Copilot
            </span>
          </div>
        </div>

        {/* Data Room Switcher */}
        <WorkspaceSelector
          workspaces={workspaces}
          currentRoomId={currentRoomId}
          onSelectWorkspace={onSelectWorkspace}
          onCreateWorkspace={onCreateWorkspace}
          onOpenWorkspacesModal={onOpenWorkspacesModal}
          healthSummary={{ rows, dates }}
        />

        {/* Conversation Threads */}
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

      {/* Footer: Evaluation Scorecard */}
      <div className="flex flex-col gap-1.5 pt-4 border-t border-sidebar-border/50 text-[11px] text-muted-foreground">
        {scores ? (
          <div className="flex justify-between items-center text-[10px] tracking-wide font-mono bg-muted/40 px-2 py-1 rounded">
            {Object.entries(scores).map(([name, score]) => (
              <span key={name}>
                {SCORE_LABEL[name] ?? name}: {Math.round(score * 100)}%
              </span>
            ))}
          </div>
        ) : null}
        <button
          type="button"
          className="flex items-center gap-1.5 text-left text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
          disabled={runningEval}
          onClick={onRunEval}
        >
          <RefreshCw className={`h-3 w-3 ${runningEval ? "animate-spin" : ""}`} />
          <span>{runningEval ? "Running eval..." : "Run Golden Set Eval"}</span>
        </button>
      </div>
    </div>
  )
}
