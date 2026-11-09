"use client"

import React, { useState, useRef } from "react"
import { useRouter } from "next/navigation"
import { Menu } from "lucide-react"
import type { WorkspaceSummary } from "@/lib/api"
import { useSession } from "@/lib/auth/provider"
import { Sidebar } from "@/components/sidebar"
import { CreateWorkspaceModal } from "@/components/create-workspace-modal"
import { MobileRoomsDrawer } from "@/components/mobile-rooms-drawer"
import { API_URL, apiFetch } from "@/lib/api"
import { mutateResource } from "@/lib/use-resource"

const HOW_IT_WORKS_STEPS = [
  {
    title: "1. Add a spreadsheet.",
    description: "Drop in a .csv or .xlsx. Nexus works out what each column means, and you approve it first.",
  },
  {
    title: "2. Ask in plain English.",
    description: "Nexus looks at your data and shows each step as it goes.",
  },
  {
    title: "3. Check the answer.",
    description: "Every number is compared with the results. Click one to see where it came from.",
  },
] as const

interface WorkspacesViewProps {
  workspaces: WorkspaceSummary[]
  currentRoomId?: WorkspaceSummary["id"] | null
  loading?: boolean
  error?: string | null
  onRetry?: () => void
  onSelectWorkspace?: (id: WorkspaceSummary["id"]) => void
  onOpenCreateModal?: () => void
  onDeleteWorkspace?: (id: WorkspaceSummary["id"]) => Promise<void> | void
}

export function WorkspacesView({
  workspaces,
  currentRoomId = null,
  loading = false,
  error = null,
  onRetry,
  onSelectWorkspace,
  onOpenCreateModal,
  onDeleteWorkspace,
}: WorkspacesViewProps) {
  const router = useRouter()
  const { user } = useSession()
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  const firstName = user?.name ? user.name.trim().split(" ")[0] : ""
  const welcomeHeading = firstName ? `Welcome, ${firstName}` : "Welcome"
  const hasRooms = workspaces.length > 0

  function handleNewRoomClick() {
    if (onOpenCreateModal) onOpenCreateModal()
    else setCreateModalOpen(true)
  }

  async function handleCreateRoom(name: string) {
    const res = await apiFetch(`${API_URL}/workspaces`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    })
    if (!res.ok) {
      let message = "Could not create data room."
      try {
        const body = await res.json()
        if (body?.detail) message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)
        else if (body?.message) message = String(body.message)
      } catch { }
      throw new Error(message)
    }
    const data = await res.json()
    mutateResource<WorkspaceSummary[]>("workspaces", (curr) => {
      const item: WorkspaceSummary = {
        id: data.id,
        name: data.name || name,
        created_at: new Date().toISOString(),
        upload_count: 0,
        run_count: 0,
      }
      return curr ? [item, ...curr] : [item]
    })
    router.push(`/rooms/${data.id}`)
  }

  function handleSelectRoom(id: WorkspaceSummary["id"]) {
    setMobileDrawerOpen(false)
    if (onSelectWorkspace) onSelectWorkspace(id)
    else router.push(`/rooms/${id}`)
  }

  return (
    <div className="flex h-svh w-full flex-col bg-background text-foreground md:flex-row overflow-hidden font-mono">
      <aside className="hidden md:block h-full shrink-0">
        <Sidebar
          mode="hub"
          workspaces={workspaces}
          activeRoomId={currentRoomId}
          loadingWorkspaces={loading}
          workspacesError={error}
          onRetryWorkspaces={onRetry}
          onSelectWorkspace={handleSelectRoom}
          onNewWorkspace={handleNewRoomClick}
          onDeleteWorkspace={onDeleteWorkspace}
        />
      </aside>

      <div className="flex h-12 shrink-0 items-center justify-between border-b border-border px-4 md:hidden">
        <span className="text-lg font-bold tracking-tight text-foreground select-none">Nexus</span>
        <button
          ref={menuButtonRef}
          type="button"
          aria-label="Open navigation menu"
          onClick={() => setMobileDrawerOpen(true)}
          className="flex items-center gap-1.5 text-xs font-medium text-foreground hover:opacity-80 p-1 outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <Menu className="h-4 w-4" />
        </button>
      </div>

      <MobileRoomsDrawer
        isOpen={mobileDrawerOpen}
        onClose={() => setMobileDrawerOpen(false)}
        menuButtonRef={menuButtonRef}
      >
        <Sidebar
          mode="hub"
          workspaces={workspaces}
          activeRoomId={currentRoomId}
          loadingWorkspaces={loading}
          workspacesError={error}
          onRetryWorkspaces={onRetry}
          onSelectWorkspace={handleSelectRoom}
          onNewWorkspace={() => {
            setMobileDrawerOpen(false)
            handleNewRoomClick()
          }}
          onDeleteWorkspace={onDeleteWorkspace}
        />
      </MobileRoomsDrawer>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col h-full overflow-y-auto">
        <div className="w-full max-w-[720px] mx-auto px-4 sm:px-6 flex flex-col flex-1 justify-between pt-16 sm:pt-20 pb-4">
          <div className="flex flex-col text-left gap-6">
            <h1 className="text-4xl sm:text-5xl font-semibold leading-tight text-foreground tracking-tight">
              {welcomeHeading}
            </h1>

            {error && (
              <div
                role="alert"
                className="border border-destructive/40 bg-destructive/10 p-3 text-xs text-foreground flex items-center justify-between gap-3"
              >
                <span>{error}</span>
                {onRetry && (
                  <button
                    type="button"
                    onClick={onRetry}
                    className="text-xs font-medium underline underline-offset-4 hover:opacity-80 transition-opacity shrink-0"
                  >
                    Retry
                  </button>
                )}
              </div>
            )}

            {loading ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono animate-pulse">
                <div className="h-4 w-48 bg-muted" />
              </div>
            ) : hasRooms ? (
              <p className="text-sm sm:text-base text-muted-foreground">
                Select a data room to continue, or create a new one.
              </p>
            ) : (
              <div className="border border-dashed border-border p-6 text-left flex flex-col items-start gap-4">
                <div className="flex flex-col gap-1">
                  <h2 className="text-sm sm:text-base font-medium text-foreground">No data rooms yet</h2>
                  <p className="text-xs sm:text-sm text-muted-foreground">
                    Create a workspace, add a spreadsheet, and ask questions in plain English.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleNewRoomClick}
                  className="bg-primary text-primary-foreground hover:bg-primary/90 px-3.5 py-1.5 text-xs font-medium transition-colors"
                >
                  New data room
                </button>
              </div>
            )}

            <div className="mt-2 border-t border-border pt-6 flex flex-col gap-4 text-left">
              <span className="text-sm font-medium text-muted-foreground">How it works</span>
              <div className="flex flex-col divide-y divide-border border-b border-border">
                {HOW_IT_WORKS_STEPS.map((step, idx) => (
                  <div key={idx} className="py-3 text-xs sm:text-sm leading-relaxed">
                    <h1 className="text-lg font-medium text-foreground">{step.title} </h1>
                    <span className="text-muted-foreground">{step.description}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <p className="text-left text-xs text-muted-foreground/60 py-3 select-none">
            Answers are checked against query results. Verify before sharing.
          </p>
        </div>
      </main>

      <CreateWorkspaceModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onCreate={handleCreateRoom}
      />
    </div>
  )
}
