"use client"

import { useEffect, useState } from "react"
import { Database, Plus, RefreshCw, AlertCircle, FileSpreadsheet, Check, CheckCircle2 } from "lucide-react"

import { API_URL, type Mapping, type Thread } from "@/lib/api"
import { Button } from "@/components/ui/button"

const CANONICAL = [
  "order_date",
  "customer_id",
  "product_id",
  "quantity",
  "revenue",
  "unit_price",
  "discount_pct",
  "cost",
  "profit",
  "segment",
  "region",
  "category",
  "sub_category",
  "channel",
] as const

const STAGE_LABEL: Record<string, string> = {
  safety: "Checking file",
  structure: "Reading sheet",
  profiling: "Detecting header",
  mapping: "Matching columns",
  load: "Loading rows",
}

const SCORE_LABEL: Record<string, string> = {
  sql_correctness: "SQL",
  numeric_faithfulness: "Numbers",
  refusal_accuracy: "Refusals",
}

export function DataPane({
  roomName,
  workspaces,
  currentRoomId,
  onSelectWorkspace,
  onCreateWorkspace,
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
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
}: {
  roomName: string
  workspaces: { id: number; name: string }[]
  currentRoomId: number | null
  onSelectWorkspace: (id: number) => void
  onCreateWorkspace: (name: string) => void
  threads: Thread[]
  activeThreadId: string
  onSelectThread: (threadId: string) => void
  onNewThread: () => void
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
}) {
  const [creatingRoom, setCreatingRoom] = useState(false)
  const [newRoomName, setNewRoomName] = useState("")

  const pending = mappings.filter((item) => item.needs_confirmation)
  const pendingKey = pending.map((item) => `${item.source}:${item.canonical ?? ""}`).join("|")
  const [choices, setChoices] = useState<Record<string, string>>({})
  const latestStage = [...stages].reverse().find((item) => item.status !== "done")

  useEffect(() => {
    const next: Record<string, string> = {}
    for (const item of pending) {
      if (item.canonical) {
        next[item.source] = item.canonical
      }
    }
    setChoices(next)
  }, [pendingKey])

  const rows = health?.rows && health.rows !== "0" ? `${Number(health.rows).toLocaleString()} rows` : null
  const dates =
    health?.first_order && health.last_order
      ? `${health.first_order} – ${health.last_order}`
      : null

  function handleCreateRoomSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (newRoomName.trim()) {
      onCreateWorkspace(newRoomName.trim())
      setNewRoomName("")
      setCreatingRoom(false)
    }
  }

  return (
    <div className="flex h-full flex-col justify-between overflow-y-auto px-4 py-4 text-[13px]">
      <div className="flex flex-col gap-5">
        {/* Top App Header with Brand Logo */}
        <div className="flex items-center justify-between pb-2 border-b border-sidebar-border/60">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded bg-primary text-[11px] font-bold text-primary-foreground tracking-wider">
              N
            </span>
            <span className="font-semibold text-sm tracking-tight text-foreground">Nexus</span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest ml-1 font-mono">Copilot</span>
          </div>
        </div>

        {/* Data Room Switcher */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">Data Room</span>
            <button
              type="button"
              onClick={() => setCreatingRoom((prev) => !prev)}
              className="text-[11px] text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
              title="Create new data room"
            >
              <Plus className="h-3 w-3" />
              <span>New</span>
            </button>
          </div>

          {creatingRoom ? (
            <form onSubmit={handleCreateRoomSubmit} className="flex gap-1.5 mt-1">
              <input
                type="text"
                value={newRoomName}
                onChange={(e) => setNewRoomName(e.target.value)}
                placeholder="Data room name..."
                autoFocus
                className="h-7 flex-1 rounded border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <Button type="submit" size="sm" className="h-7 px-2 text-xs">
                Add
              </Button>
            </form>
          ) : (
            <select
              className="h-8 w-full rounded border border-input/60 bg-background/50 px-2 text-xs font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              value={currentRoomId ?? ""}
              onChange={(e) => onSelectWorkspace(Number(e.target.value))}
            >
              {workspaces.map((ws) => (
                <option key={ws.id} value={ws.id}>
                  {ws.name}
                </option>
              ))}
            </select>
          )}

          {/* Quick Stats */}
          <div className="flex flex-wrap gap-x-2 text-[11px] text-muted-foreground pt-0.5">
            {rows ? <span>{rows}</span> : null}
            {dates && rows ? <span>•</span> : null}
            {dates ? <span className="truncate">{dates}</span> : null}
          </div>
        </div>

        {/* Conversation Threads (Claude Style) */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">Chats</span>
            <button
              type="button"
              onClick={onNewThread}
              className="text-[11px] text-primary hover:text-primary/80 flex items-center gap-1 font-medium transition-colors"
              title="Start a new chat thread"
            >
              <Plus className="h-3 w-3" />
              <span>New Chat</span>
            </button>
          </div>

          <div className="flex flex-col gap-0.5 max-h-48 overflow-y-auto">
            {threads.length === 0 ? (
              <button
                type="button"
                onClick={onNewThread}
                className="text-left py-1.5 px-2 rounded text-xs text-muted-foreground hover:bg-accent/40"
              >
                Start your first chat
              </button>
            ) : (
              threads.map((th) => {
                const isActive = activeThreadId === th.id
                return (
                  <button
                    key={th.id}
                    type="button"
                    onClick={() => onSelectThread(th.id)}
                    className={`flex items-center justify-between py-1.5 px-2 rounded text-left text-xs transition-colors ${
                      isActive
                        ? "bg-accent text-accent-foreground font-medium"
                        : "text-muted-foreground hover:text-foreground hover:bg-accent/40"
                    }`}
                  >
                    <span className="truncate pr-2">{th.title}</span>
                    {th.turn_count > 0 ? (
                      <span className="text-[10px] text-muted-foreground/60">{th.turn_count}</span>
                    ) : null}
                  </button>
                )
              })
            )}
          </div>
        </div>

        {/* Upload / Ingestion Section */}
        <div className="flex flex-col gap-2 pt-2 border-t border-sidebar-border/40">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">Data Source</span>
          </div>

          {fileName ? (
            <div className="flex items-center gap-1.5 text-xs text-foreground/90 truncate">
              <FileSpreadsheet className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">{fileName}</span>
            </div>
          ) : null}

          {latestStage ? (
            <p className="text-xs text-muted-foreground animate-pulse">
              {STAGE_LABEL[latestStage.stage] ?? "Reading sheet"}…
            </p>
          ) : status && status !== "loaded" ? (
            <p className="text-xs text-muted-foreground">{status.replaceAll("_", " ")}</p>
          ) : null}

          {reason ? (
            <div className="flex items-start gap-1 text-xs text-destructive">
              <AlertCircle className="h-3 w-3 mt-0.5 shrink-0" />
              <span>{reason}</span>
            </div>
          ) : null}

          <label
            className="w-full text-center py-2 px-3 border border-dashed border-input rounded cursor-pointer text-xs text-muted-foreground hover:text-foreground hover:border-muted-foreground/60 transition-colors"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault()
              const next = event.dataTransfer.files.item(0)
              if (next) {
                onFile(next)
              }
            }}
          >
            <span>+ Drop sales CSV/Excel</span>
            <input
              className="sr-only"
              type="file"
              accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => {
                const next = event.target.files?.item(0)
                if (next) {
                  onFile(next)
                }
                event.target.value = ""
              }}
            />
          </label>
        </div>

        {/* Column Mapping Confirmation Modal / Block */}
        {pending.length > 0 ? (
          <div className="flex flex-col gap-2 p-2.5 rounded bg-muted/30 border border-border text-xs">
            <p className="font-medium text-foreground">Confirm ambiguous columns</p>
            {pending.map((item) => (
              <label key={item.source} className="flex flex-col gap-0.5">
                <span className="text-muted-foreground font-mono text-[11px]">{item.source}</span>
                <select
                  className="h-7 border border-input bg-background rounded px-1.5 text-xs"
                  value={choices[item.source] ?? ""}
                  onChange={(event) =>
                    setChoices((current) => ({
                      ...current,
                      [item.source]: event.target.value,
                    }))
                  }
                >
                  <option value="">Skip column</option>
                  {CANONICAL.map((column) => (
                    <option key={column} value={column}>
                      {column}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            <Button size="sm" className="h-7 text-xs mt-1" disabled={confirming} onClick={() => onConfirm(choices)}>
              {confirming ? "Saving…" : "Confirm Mapping"}
            </Button>
          </div>
        ) : null}

        {/* Quarantined Rows */}
        {quarantine.length > 0 ? (
          <div className="flex flex-col gap-1 text-xs text-muted-foreground pt-1 border-t border-sidebar-border/40">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">Quarantine</span>
            {quarantine.slice(0, 3).map((row) => (
              <p key={`${row.row_number}-${row.reason}`} className="truncate text-[11px]">
                Row {row.row_number}: {row.reason}
              </p>
            ))}
            {uploadId ? (
              <a
                className="mt-0.5 text-[11px] text-primary hover:underline"
                href={`${API_URL}/uploads/${uploadId}/health?download=quarantine`}
              >
                Download report CSV
              </a>
            ) : null}
          </div>
        ) : null}

        {error ? (
          <p className="text-xs text-destructive" role="alert">
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
