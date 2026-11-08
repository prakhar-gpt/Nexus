"use client"

import { Check, ChevronDown, Database, Plus, Trash2 } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { type WorkspaceSummary } from "@/lib/api"

interface WorkspaceSelectorProps {
  workspaces: WorkspaceSummary[]
  currentRoomId: number | null
  onSelectWorkspace: (id: number) => void
  onOpenCreateModal: () => void
  onDeleteWorkspace: (id: number) => void
  healthSummary?: {
    rows: string | null
    dates: string | null
  }
}

export function WorkspaceSelector({
  workspaces,
  currentRoomId,
  onSelectWorkspace,
  onOpenCreateModal,
  onDeleteWorkspace,
  healthSummary,
}: WorkspaceSelectorProps) {
  const currentWs = workspaces.find((w) => w.id === currentRoomId)

  return (
    <div className="flex flex-col gap-1.5 px-1">
      <DropdownMenu>
        <DropdownMenuTrigger className="flex w-full items-center justify-between rounded-md border border-input/60 bg-background/50 px-2.5 py-1.5 text-xs text-foreground hover:bg-accent/40 focus:outline-none focus:ring-1 focus:ring-primary transition-all text-left shadow-xs">
          <div className="flex items-center gap-2 truncate">
            <Database className="h-3.5 w-3.5 shrink-0 text-primary" />
            <span className="font-medium truncate">{currentWs?.name ?? "Select Data Room"}</span>
          </div>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-60 ml-1" />
        </DropdownMenuTrigger>

        <DropdownMenuContent align="start" className="w-64">
          <DropdownMenuLabel className="text-[10px] uppercase font-semibold text-muted-foreground/80 tracking-wider">
            Data Rooms ({workspaces.length})
          </DropdownMenuLabel>
          <DropdownMenuSeparator />

          <div className="max-h-56 overflow-y-auto flex flex-col gap-0.5">
            {workspaces.map((ws) => {
              const isSelected = ws.id === currentRoomId
              return (
                <div
                  key={ws.id}
                  className={`group flex items-center justify-between px-2 py-1.5 rounded-sm text-xs cursor-pointer transition-colors ${
                    isSelected ? "bg-accent text-accent-foreground font-medium" : "hover:bg-accent/40 text-muted-foreground hover:text-foreground"
                  }`}
                  onClick={() => onSelectWorkspace(ws.id)}
                >
                  <div className="flex items-center gap-2 truncate min-w-0">
                    <Database className={`h-3 w-3 shrink-0 ${isSelected ? "text-primary" : "text-muted-foreground/60"}`} />
                    <span className="truncate">{ws.name}</span>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0 ml-1">
                    {isSelected ? (
                      <Check className="h-3.5 w-3.5 text-primary" />
                    ) : (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (confirm(`Delete Data Room "${ws.name}"?`)) {
                            onDeleteWorkspace(ws.id)
                          }
                        }}
                        className="opacity-0 group-hover:opacity-100 p-0.5 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all"
                        title="Delete Data Room"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={onOpenCreateModal}
            className="text-xs text-primary font-medium cursor-pointer"
          >
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            Create Data Room
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Dataset quick metadata */}
      <div className="flex items-center justify-between text-[11px] text-muted-foreground/80 px-1 pt-0.5">
        <span>{healthSummary?.rows ? healthSummary.rows : "0 rows loaded"}</span>
        {healthSummary?.dates ? (
          <span className="truncate max-w-[130px] font-mono text-[10px] text-right">
            {healthSummary.dates}
          </span>
        ) : null}
      </div>
    </div>
  )
}
