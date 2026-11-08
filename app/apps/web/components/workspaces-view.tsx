"use client"

import { Plus, Database, Trash2, ArrowRight, Table2, Calendar, FileSpreadsheet } from "lucide-react"
import { Button } from "@/components/ui/button"
import { type WorkspaceSummary } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"

interface WorkspacesViewProps {
  workspaces: WorkspaceSummary[]
  currentRoomId: number | null
  onSelectWorkspace: (id: number) => void
  onOpenCreateModal: () => void
  onDeleteWorkspace: (id: number) => void
  onOpenAuthModal: () => void
}

export function WorkspacesView({
  workspaces,
  currentRoomId,
  onSelectWorkspace,
  onOpenCreateModal,
  onDeleteWorkspace,
  onOpenAuthModal,
}: WorkspacesViewProps) {
  const { user } = useAuth()

  return (
    <div className="flex-1 flex flex-col h-full bg-background overflow-y-auto">
      {/* Top Header */}
      <header className="border-b border-border/60 px-8 py-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded bg-primary text-xs font-bold text-primary-foreground shadow-xs">
            N
          </span>
          <div>
            <h1 className="text-base font-semibold text-foreground">Nexus Copilot</h1>
            <p className="text-xs text-muted-foreground">Commercial Due Diligence & Retail Analytics</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {user ? (
            <span className="text-xs text-muted-foreground">
              Signed in as <strong className="text-foreground">{user.name}</strong>
            </span>
          ) : (
            <Button variant="outline" size="sm" onClick={onOpenAuthModal} className="text-xs">
              Sign In
            </Button>
          )}

          <Button size="sm" onClick={onOpenCreateModal} className="text-xs">
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            New Data Room
          </Button>
        </div>
      </header>

      {/* Main Grid Content */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-8 py-8 flex flex-col gap-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-foreground">Data Rooms</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Select an isolated data room to query sales datasets, inspect SQL queries, and chat with the copilot.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Create Card Action */}
          <button
            type="button"
            onClick={onOpenCreateModal}
            className="flex flex-col items-center justify-center p-6 rounded-xl border border-dashed border-input/80 hover:border-primary/60 hover:bg-accent/20 transition-all text-center group min-h-[170px]"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary group-hover:scale-105 transition-transform">
              <Plus className="h-5 w-5" />
            </div>
            <span className="mt-3 text-sm font-medium text-foreground">Create New Data Room</span>
            <span className="mt-1 text-xs text-muted-foreground">Upload and isolate sales data</span>
          </button>

          {/* List of Data Rooms */}
          {workspaces.map((ws) => {
            const isSelected = ws.id === currentRoomId
            return (
              <div
                key={ws.id}
                onClick={() => onSelectWorkspace(ws.id)}
                className={`group flex flex-col justify-between p-5 rounded-xl border cursor-pointer transition-all ${
                  isSelected
                    ? "border-primary bg-primary/5 ring-1 ring-primary/40 shadow-xs"
                    : "border-border/80 hover:border-foreground/30 hover:bg-accent/20 hover:shadow-xs"
                }`}
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded bg-muted text-muted-foreground">
                        <Database className="h-3.5 w-3.5" />
                      </div>
                      <h3 className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                        {ws.name}
                      </h3>
                    </div>

                    <div className="flex items-center gap-1.5">
                      {isSelected ? (
                        <span className="text-[10px] bg-primary/10 text-primary font-semibold px-2 py-0.5 rounded-full">
                          Active
                        </span>
                      ) : null}

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (confirm(`Delete Data Room "${ws.name}"?`)) {
                            onDeleteWorkspace(ws.id)
                          }
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all"
                        title="Delete Data Room"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 mt-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <FileSpreadsheet className="h-3.5 w-3.5" />
                      {ws.upload_count ?? 1} files
                    </span>
                    <span>•</span>
                    <span>{ws.run_count ?? 0} queries</span>
                  </div>
                </div>

                <div className="flex items-center justify-between mt-5 pt-3 border-t border-border/40 text-[11px] text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {new Date(ws.created_at).toLocaleDateString()}
                  </span>
                  <span className="flex items-center gap-1 font-medium text-primary group-hover:translate-x-0.5 transition-transform">
                    Enter Data Room <ArrowRight className="h-3 w-3" />
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </main>
    </div>
  )
}
