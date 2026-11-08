"use client"

import { useState } from "react"
import { Layers, Plus, Database, X, ArrowRight, Calendar, Table2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { type WorkspaceSummary } from "@/lib/api"

interface WorkspacesModalProps {
  isOpen: boolean
  onClose: () => void
  workspaces: WorkspaceSummary[]
  currentRoomId: number | null
  onSelectWorkspace: (id: number) => void
  onCreateWorkspace: (name: string) => void
}

export function WorkspacesModal({
  isOpen,
  onClose,
  workspaces,
  currentRoomId,
  onSelectWorkspace,
  onCreateWorkspace,
}: WorkspacesModalProps) {
  const [newName, setNewName] = useState("")

  if (!isOpen) return null

  function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (newName.trim()) {
      onCreateWorkspace(newName.trim())
      setNewName("")
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="relative w-full max-w-2xl rounded-lg border border-border bg-background shadow-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-primary">
              <Database className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-foreground">Data Rooms</h2>
              <p className="text-xs text-muted-foreground">Select an existing data room or initialize a new workspace.</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 flex flex-col gap-5 max-h-[70vh] overflow-y-auto">
          {/* Create new room inline banner */}
          <form onSubmit={handleCreate} className="flex gap-2 p-3 rounded-lg border border-border bg-muted/30">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Create new Data Room (e.g. Nordic Retail Diligence)..."
              className="flex-1 rounded border border-input bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <Button type="submit" size="sm" className="h-8 px-3 text-xs">
              <Plus className="h-3.5 w-3.5 mr-1" />
              Create
            </Button>
          </form>

          {/* Grid of Workspaces */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {workspaces.map((ws) => {
              const isSelected = ws.id === currentRoomId
              return (
                <div
                  key={ws.id}
                  onClick={() => {
                    onSelectWorkspace(ws.id)
                    onClose()
                  }}
                  className={`flex flex-col justify-between p-4 rounded-lg border cursor-pointer transition-all ${
                    isSelected
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border hover:border-foreground/30 hover:bg-muted/20"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-medium text-sm text-foreground">{ws.name}</h3>
                      <div className="flex items-center gap-2 mt-1 text-[11px] text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Table2 className="h-3 w-3" />
                          {ws.upload_count ?? 1} files
                        </span>
                        <span>•</span>
                        <span>{ws.run_count ?? 0} queries</span>
                      </div>
                    </div>
                    {isSelected ? (
                      <span className="text-[10px] bg-primary text-primary-foreground font-semibold px-1.5 py-0.5 rounded">
                        Active
                      </span>
                    ) : null}
                  </div>

                  <div className="flex items-center justify-between mt-4 pt-3 border-t border-border/40 text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {new Date(ws.created_at).toLocaleDateString()}
                    </span>
                    <span className="flex items-center gap-0.5 text-primary group-hover:translate-x-0.5 transition-transform font-medium">
                      Open <ArrowRight className="h-3 w-3" />
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
