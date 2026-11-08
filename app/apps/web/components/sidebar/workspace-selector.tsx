"use client"

import { useState } from "react"
import { Layers, Plus, Database, Sparkles, Check, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { type WorkspaceSummary } from "@/lib/api"

interface WorkspaceSelectorProps {
  workspaces: WorkspaceSummary[]
  currentRoomId: number | null
  onSelectWorkspace: (id: number) => void
  onCreateWorkspace: (name: string) => void
  onOpenWorkspacesModal: () => void
  healthSummary?: {
    rows: string | null
    dates: string | null
    revenue?: string | null
  }
}

export function WorkspaceSelector({
  workspaces,
  currentRoomId,
  onSelectWorkspace,
  onCreateWorkspace,
  onOpenWorkspacesModal,
  healthSummary,
}: WorkspaceSelectorProps) {
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState("")

  const activeWs = workspaces.find((w) => w.id === currentRoomId)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (name.trim()) {
      onCreateWorkspace(name.trim())
      setName("")
      setCreating(false)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between px-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/80">
          Data Room
        </span>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={onOpenWorkspacesModal}
            className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            title="View all data rooms"
          >
            Browse ({workspaces.length})
          </button>
          <span className="text-muted-foreground/40">•</span>
          <button
            type="button"
            onClick={() => setCreating((prev) => !prev)}
            className="text-[11px] text-primary hover:text-primary/80 flex items-center gap-0.5 font-medium transition-colors"
            title="Create new data room"
          >
            <Plus className="h-3 w-3" />
            <span>New</span>
          </button>
        </div>
      </div>

      {creating ? (
        <form onSubmit={handleSubmit} className="flex gap-1.5">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Data room name..."
            autoFocus
            className="h-7 flex-1 rounded border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <Button type="submit" size="sm" className="h-7 px-2 text-xs">
            Add
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setCreating(false)}
            className="h-7 px-2 text-xs"
          >
            Cancel
          </Button>
        </form>
      ) : (
        <div className="flex flex-col gap-1.5">
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

          {/* Quick Metrics Under Workspace */}
          <div className="flex items-center justify-between text-[11px] text-muted-foreground px-1">
            <span className="font-medium text-foreground/80">
              {healthSummary?.rows ? `${healthSummary.rows}` : "0 rows loaded"}
            </span>
            {healthSummary?.dates ? (
              <span className="truncate max-w-[140px] text-right font-mono text-[10px]">
                {healthSummary.dates}
              </span>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
