"use client"

import { useState } from "react"
import {
  Plus,
  Database,
  Trash2,
  ArrowRight,
  FileSpreadsheet,
  Calendar,
  AlertCircle,
  RefreshCw,
  Sun,
  Moon,
  LogOut,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { type WorkspaceSummary } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { useTheme } from "next-themes"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface WorkspacesViewProps {
  workspaces: WorkspaceSummary[]
  currentRoomId: number | null
  loading?: boolean
  error?: string | null
  onRetry?: () => void
  onSelectWorkspace: (id: number) => void
  onOpenCreateModal: () => void
  onDeleteWorkspace: (id: number) => void
  onOpenAuthModal: () => void
}

export function WorkspacesView({
  workspaces,
  currentRoomId,
  loading = false,
  error = null,
  onRetry,
  onSelectWorkspace,
  onOpenCreateModal,
  onDeleteWorkspace,
  onOpenAuthModal,
}: WorkspacesViewProps) {
  const { user, logout } = useAuth()
  const { resolvedTheme, setTheme } = useTheme()
  const [workspaceToDelete, setWorkspaceToDelete] = useState<{
    id: number
    name: string
  } | null>(null)

  const isDark = resolvedTheme === "dark"

  const initials = user?.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "CD"

  return (
    <div className="flex min-h-screen w-full flex-col bg-background text-foreground">
      {/* Slim Top Row (56px, bottom hairline) */}
      <header className="h-14 border-b border-border px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold tracking-tight text-foreground">
            Nexus
          </span>
          <span className="hidden sm:inline text-xs text-muted-foreground border-l border-border pl-3">
            Commercial due diligence & retail analytics
          </span>
        </div>

        <div className="flex items-center gap-3">
          {user ? (
            <DropdownMenu>
              <DropdownMenuTrigger className="flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors outline-none focus-visible:ring-1 focus-visible:ring-ring">
                <div className="flex h-6 w-6 items-center justify-center bg-accent text-accent-foreground text-[10px] font-medium border border-border">
                  {initials}
                </div>
                <span className="hidden md:inline font-normal">
                  Signed in as <strong className="font-medium text-foreground">{user.name}</strong>
                </span>
              </DropdownMenuTrigger>

              <DropdownMenuContent
                align="end"
                className="w-56 mt-1 rounded-[var(--radius)] border border-border bg-popover p-1 shadow-none"
              >
                <DropdownMenuLabel className="font-normal px-2 py-1.5">
                  <div className="flex flex-col gap-1">
                    <p className="text-xs font-medium text-foreground">{user.name}</p>
                    <p className="text-[11px] text-muted-foreground truncate">{user.email}</p>
                    <span className="mt-1 w-fit border border-border bg-muted/60 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                      Diligence Analyst
                    </span>
                  </div>
                </DropdownMenuLabel>

                <DropdownMenuSeparator className="bg-border my-1" />

                <DropdownMenuItem
                  onClick={() => setTheme(isDark ? "light" : "dark")}
                  className="flex items-center gap-2 px-2 py-1.5 text-xs text-foreground cursor-pointer focus:bg-accent focus:text-accent-foreground"
                >
                  {isDark ? (
                    <>
                      <Sun className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>Switch to light mode</span>
                    </>
                  ) : (
                    <>
                      <Moon className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>Switch to dark mode</span>
                    </>
                  )}
                </DropdownMenuItem>

                <DropdownMenuSeparator className="bg-border my-1" />

                <DropdownMenuItem
                  onClick={() => logout()}
                  className="flex items-center gap-2 px-2 py-1.5 text-xs text-destructive cursor-pointer focus:bg-destructive/10 focus:text-destructive"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  <span>Log out</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={onOpenAuthModal}
              className="text-xs h-8 text-muted-foreground hover:text-foreground"
            >
              Sign in
            </Button>
          )}

          <Button
            size="sm"
            onClick={onOpenCreateModal}
            className="h-8 px-3 text-xs font-medium"
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            New data room
          </Button>
        </div>
      </header>

      {/* Main Hub Body (max 960px centered) */}
      <main className="w-full max-w-[960px] mx-auto px-6 py-10 flex-1 flex flex-col">
        {/* Title and muted sentence */}
        <div>
          <h1 className="text-[28px] font-semibold leading-tight text-foreground tracking-tight">
            Data rooms
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Isolated workspaces for querying sales data, inspecting SQL, and chatting with the copilot.
          </p>
        </div>

        {/* Error State: inline banner with Retry button */}
        {error ? (
          <div
            role="alert"
            className="mt-6 flex items-center justify-between p-3.5 bg-destructive/10 border border-destructive/20 text-xs text-destructive"
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
            {onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-1 font-medium underline underline-offset-2 hover:opacity-80"
              >
                <RefreshCw className="h-3 w-3" />
                <span>Retry</span>
              </button>
            ) : null}
          </div>
        ) : null}

        {/* Loading State: 3 skeleton cards */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-8">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-[170px] border border-border bg-card p-5 flex flex-col justify-between animate-pulse"
              >
                <div className="flex flex-col gap-2">
                  <div className="h-4 bg-muted w-3/4" />
                  <div className="h-3 bg-muted/60 w-1/2 mt-2" />
                </div>
                <div className="h-3 bg-muted/40 w-1/3" />
              </div>
            ))}
          </div>
        ) : null}

        {/* Empty State: one centered block, no illustration */}
        {!loading && !error && workspaces.length === 0 ? (
          <div className="my-auto py-16 flex flex-col items-center justify-center text-center max-w-sm mx-auto">
            <h2 className="text-base font-medium text-foreground">
              No data rooms yet
            </h2>
            <p className="text-xs text-muted-foreground mt-1 mb-4">
              Create an isolated workspace to upload diligence spreadsheets and run SQL queries.
            </p>
            <Button
              size="sm"
              onClick={onOpenCreateModal}
              className="h-8 px-4 text-xs font-medium"
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              New data room
            </Button>
          </div>
        ) : null}

        {/* Grid of Data Rooms */}
        {!loading && workspaces.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-8">
            {/* First Tile: "New data room" dashed hairline button */}
            <button
              type="button"
              onClick={onOpenCreateModal}
              className="group flex flex-col items-center justify-center min-h-[170px] p-5 border border-dashed border-border hover:border-foreground/30 hover:bg-accent/40 transition-colors text-center cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <div className="flex h-8 w-8 items-center justify-center bg-muted text-muted-foreground group-hover:text-foreground transition-colors mb-2">
                <Plus className="h-4 w-4" />
              </div>
              <span className="text-xs font-medium text-foreground">
                New data room
              </span>
              <span className="text-[11px] text-muted-foreground mt-0.5">
                Upload and isolate sales data
              </span>
            </button>

            {/* Room Cards */}
            {workspaces.map((ws) => {
              const isActive = ws.id === currentRoomId
              const uploadCount = Number(ws.upload_count ?? 1)
              const runCount = Number(ws.run_count ?? 0)

              return (
                <div
                  key={ws.id}
                  tabIndex={0}
                  role="button"
                  onClick={() => onSelectWorkspace(ws.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      onSelectWorkspace(ws.id)
                    }
                  }}
                  className={`group relative flex flex-col justify-between min-h-[170px] p-5 border bg-card cursor-pointer outline-none transition-colors hover:border-foreground/30 focus-visible:ring-1 focus-visible:ring-ring ${
                    isActive ? "border-foreground/40" : "border-border"
                  }`}
                >
                  <div>
                    {/* Top row */}
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <Database className="h-4 w-4 text-muted-foreground shrink-0" />
                        <h3 className="text-xs font-medium text-foreground truncate">
                          {ws.name}
                        </h3>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        {isActive ? (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 bg-accent text-accent-foreground border border-border">
                            Active
                          </span>
                        ) : null}

                        {/* Trash Icon Button appears on hover/focus (always on touch) */}
                        <button
                          type="button"
                          aria-label={`Delete ${ws.name}`}
                          onClick={(e) => {
                            e.stopPropagation()
                            setWorkspaceToDelete({ id: ws.id, name: ws.name })
                          }}
                          className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity p-1 text-muted-foreground hover:text-destructive max-sm:opacity-100"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Meta row */}
                    <div className="flex items-center gap-2 mt-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <FileSpreadsheet className="h-3.5 w-3.5" />
                        <span>
                          {uploadCount} {uploadCount === 1 ? "file" : "files"}
                        </span>
                      </span>
                      <span>·</span>
                      <span>
                        {runCount} {runCount === 1 ? "query" : "queries"}
                      </span>
                    </div>
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-between pt-3 border-t border-border/40 text-[11px] text-muted-foreground mt-4">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      <span>{ws.created_at ? ws.created_at.slice(0, 10) : "Recent"}</span>
                    </span>
                    <span className="flex items-center gap-1 font-medium text-foreground group-hover:translate-x-0.5 transition-transform">
                      <span>Open</span>
                      <ArrowRight className="h-3 w-3" />
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        ) : null}
      </main>

      {/* Confirm Delete Dialog */}
      <ConfirmDialog
        isOpen={!!workspaceToDelete}
        onClose={() => setWorkspaceToDelete(null)}
        onConfirm={() => {
          if (workspaceToDelete) {
            onDeleteWorkspace(workspaceToDelete.id)
            setWorkspaceToDelete(null)
          }
        }}
        title={`Delete "${workspaceToDelete?.name}"?`}
        description="All uploaded spreadsheets and runs will be archived."
        confirmText="Delete"
      />
    </div>
  )
}
