"use client"

import React, { useState } from "react"
import { useRouter } from "next/navigation"
import { Menu, X } from "lucide-react"
import type { WorkspaceSummary } from "@/lib/api"
import { useSession } from "@/lib/auth/provider"
import { Sidebar } from "@/components/sidebar"
import { CreateWorkspaceModal } from "@/components/create-workspace-modal"
import { AuthModal } from "@/components/auth-modal"
import { API_URL, apiFetch } from "@/lib/api"
import { mutateResource } from "@/lib/use-resource"

interface WorkspacesViewProps {
  workspaces: WorkspaceSummary[]
  currentRoomId?: number | null
  loading?: boolean
  error?: string | null
  onRetry?: () => void
  onSelectWorkspace?: (id: number) => void
  onOpenCreateModal?: () => void
  onDeleteWorkspace?: (id: number) => Promise<void> | void
  onOpenAuthModal?: () => void
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
  onOpenAuthModal,
}: WorkspacesViewProps) {
  const router = useRouter()
  const { session } = useSession()
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [authModalOpen, setAuthModalOpen] = useState(false)

  const firstName = session?.name ? session.name.trim().split(" ")[0] : ""
  const welcomeHeading = firstName ? `Welcome, ${firstName}` : "Welcome"
  const hasRooms = workspaces.length > 0

  function handleNewRoomClick() {
    if (onOpenCreateModal) {
      onOpenCreateModal()
    } else {
      setCreateModalOpen(true)
    }
  }

  async function handleCreateRoom(name: string) {
    const res = await apiFetch(`${API_URL}/workspaces`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    })
    if (!res.ok) throw new Error("Could not create data room.")
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

  function handleSelectRoom(id: number) {
    setMobileDrawerOpen(false)
    if (onSelectWorkspace) {
      onSelectWorkspace(id)
    } else {
      router.push(`/rooms/${id}`)
    }
  }

  return (
    <div className="flex h-svh w-full flex-col bg-background text-foreground md:flex-row overflow-hidden">
      {/* Desktop Sidebar: 260px fixed shell (hub mode) */}
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
          onOpenAuthModal={() => {
            if (onOpenAuthModal) onOpenAuthModal()
            else setAuthModalOpen(true)
          }}
        />
      </aside>

      {/* Mobile Header under 768px */}
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-border px-4 md:hidden">
        <span className="text-xs font-semibold tracking-tight text-foreground select-none">
          Nexus
        </span>

        <button
          type="button"
          aria-label="Open navigation menu"
          onClick={() => setMobileDrawerOpen(true)}
          className="flex items-center gap-1.5 text-xs font-medium text-foreground hover:opacity-80 p-1 outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <Menu className="h-4 w-4" />
        </button>
      </div>

      {/* Mobile Drawer */}
      {mobileDrawerOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden bg-black/40 backdrop-blur-[2px]">
          <div className="h-full w-[260px] bg-sidebar shadow-none">
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
              onOpenAuthModal={() => {
                setMobileDrawerOpen(false)
                if (onOpenAuthModal) onOpenAuthModal()
                else setAuthModalOpen(true)
              }}
            />
          </div>
          <button
            type="button"
            aria-label="Close menu drawer"
            onClick={() => setMobileDrawerOpen(false)}
            className="flex-1 p-4 text-foreground/80 outline-none"
          >
            <X className="h-6 w-6 ml-auto" />
          </button>
        </div>
      )}

      {/* Main Hub Pane: 720px shared column, top-placed like chat empty state */}
      <main className="flex min-h-0 min-w-0 flex-1 flex-col h-full overflow-y-auto">
        <div className="w-full max-w-[720px] mx-auto px-4 sm:px-6 flex flex-col flex-1 justify-between pt-16 sm:pt-20 pb-4">
          <div className="flex flex-col text-left">
            <h1 className="text-4xl sm:text-5xl font-semibold leading-tight text-foreground tracking-tight">
              {welcomeHeading}
            </h1>

            {/* With rooms: single muted guidance line */}
            {hasRooms ? (
              <p className="text-sm sm:text-base text-muted-foreground mt-3">
                Select a data room to continue, or create a new one.
              </p>
            ) : (
              /* With zero rooms: clean text without outer box or button */
              <div className="mt-6 flex flex-col gap-1 text-left">
                <h2 className="text-sm sm:text-base font-medium text-foreground">
                  No data rooms yet
                </h2>
                <p className="text-xs sm:text-sm text-muted-foreground">
                  Create a workspace, add a spreadsheet, and ask questions in plain English.
                </p>
              </div>
            )}
          </div>

          {/* Persistent footer line matching chat view */}
          <p className="text-center text-[11px] text-muted-foreground/60 py-3 select-none">
            Answers are checked against query results. Verify before sharing.
          </p>
        </div>
      </main>

      {/* Create Data Room Modal */}
      <CreateWorkspaceModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onCreate={handleCreateRoom}
      />

      {/* Auth Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
      />
    </div>
  )
}
