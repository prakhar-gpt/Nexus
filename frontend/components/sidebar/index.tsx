"use client"

import React, { useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowLeft, Plus } from "lucide-react"
import { type Dataset, type Thread, type WorkspaceSummary } from "@/lib/api"
import type { RoomStatus } from "@/lib/room-status"
import { ThreadList } from "./thread-list"
import { RoomList } from "./room-list"
import { DatasetSection, type PendingUploadItem } from "./dataset-section"
import { UserProfileFooter } from "./user-profile-footer"

export interface SidebarProps {
  mode?: "hub" | "room"
  // Room mode props
  roomId?: string | number
  roomName?: string
  threads?: Thread[]
  datasets?: Dataset[]
  pendingUploads?: PendingUploadItem[]
  activeThreadId?: string
  selectedDatasetIds?: number[]
  status?: RoomStatus
  isUploadRunning?: boolean
  isReviewPending?: boolean
  onToggleDataset?: (datasetId: number, checked: boolean) => void
  onAddDatasetClick?: () => void
  onOpenSetupCard?: (uploadId: string | number) => void
  onRemoveDataset?: (datasetId: number) => Promise<void> | void
  onRenameDataset?: (datasetId: number, newLabel: string) => Promise<void> | void
  onBackToWorkspaces?: () => void
  onSelectThread?: (threadId: string) => void
  onNewThread?: () => void
  onDeleteThread?: (threadId: string) => Promise<void> | void
  onOpenDataModal?: () => void
  attentionWarning?: string | null
  healthSummary?: {
    rows: string | null
    dates: string | null
  }
  // Hub mode props
  workspaces?: WorkspaceSummary[]
  activeRoomId?: number | string | null
  loadingWorkspaces?: boolean
  workspacesError?: string | null
  onRetryWorkspaces?: () => void
  onSelectWorkspace?: (id: number) => void
  onNewWorkspace?: () => void
  onDeleteWorkspace?: (id: number) => Promise<void> | void
  onOpenAuthModal?: () => void
}

function SidebarComponent({
  mode = "room",
  roomId = "1",
  roomName = "Data Room",
  threads = [],
  datasets = [],
  pendingUploads = [],
  activeThreadId,
  selectedDatasetIds = [],
  status,
  isUploadRunning = false,
  isReviewPending = false,
  onToggleDataset,
  onAddDatasetClick,
  onOpenSetupCard,
  onRemoveDataset,
  onRenameDataset,
  onBackToWorkspaces,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  onOpenDataModal: _onOpenDataModal,
  attentionWarning: _attentionWarning,
  healthSummary,
  workspaces = [],
  activeRoomId,
  loadingWorkspaces = false,
  workspacesError = null,
  onRetryWorkspaces,
  onSelectWorkspace,
  onNewWorkspace,
  onDeleteWorkspace,
  onOpenAuthModal,
}: SidebarProps) {
  const router = useRouter()

  // Global ⌘K / Ctrl+K listener for New Chat (room mode) or New Room (hub mode)
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        if (mode === "hub") {
          if (onNewWorkspace) {
            onNewWorkspace()
          } else {
            router.push("/rooms/new")
          }
        } else {
          // Block new chat creation while an upload is running or pending schema review
          if (isUploadRunning || isReviewPending) {
            return
          }
          if (onNewThread) {
            onNewThread()
          } else {
            router.push(`/rooms/${roomId}`)
          }
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [router, roomId, mode, onNewThread, onNewWorkspace, isUploadRunning, isReviewPending])

  const isIngesting = status?.type === "ingesting"
  const hasRooms = workspaces.length > 0

  return (
    <div className="flex h-full w-[260px] flex-col justify-between bg-sidebar p-3 text-sidebar-foreground border-r border-sidebar-border select-none">
      <div className="flex flex-col gap-3 min-h-0 flex-1">
        {/* 1. Top row */}
        {mode === "hub" ? (
          <div className="flex items-center justify-between pb-1">
            <h1 className="text-sm font-semibold tracking-tight text-sidebar-foreground">
              Nexus
            </h1>
          </div>
        ) : (
          <div className="flex items-center justify-between pb-1">
            {onBackToWorkspaces ? (
              <button
                type="button"
                onClick={onBackToWorkspaces}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-sidebar-foreground transition-colors group"
              >
                <ArrowLeft className="h-3.5 w-3.5 group-hover:-translate-x-0.5 transition-transform" />
                <span>Data rooms</span>
              </button>
            ) : (
              <Link
                href="/rooms"
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-sidebar-foreground transition-colors group"
              >
                <ArrowLeft className="h-3.5 w-3.5 group-hover:-translate-x-0.5 transition-transform" />
                <span>Data rooms</span>
              </Link>
            )}

            <h1 className="text-sm font-semibold tracking-tight text-sidebar-foreground">
              Nexus
            </h1>
          </div>
        )}

        {/* 2. Room mode block */}
        {mode === "room" && (
          <>
            <div className="flex flex-col gap-1 bg-sidebar-accent/50 p-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-sidebar-foreground truncate max-w-[150px]">
                  {roomName}
                </span>

                {isIngesting ? (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] text-muted-foreground font-mono">
                      Analyzing…
                    </span>
                  </div>
                ) : null}
              </div>
            </div>

            {/* Datasets Section */}
            <DatasetSection
              roomId={roomId}
              datasets={datasets}
              pendingUploads={pendingUploads}
              selectedDatasetIds={selectedDatasetIds}
              isUploadRunning={isIngesting || isUploadRunning}
              onToggleDataset={onToggleDataset || (() => { })}
              onAddDatasetClick={onAddDatasetClick || (() => { })}
              onOpenSetupCard={onOpenSetupCard}
              onRemoveDataset={onRemoveDataset || (async () => { })}
              onRenameDataset={onRenameDataset}
            />
          </>
        )}

        {/* 3. Action button: New chat (room mode) or + New data room (hub mode) */}
        {mode === "hub" ? (
          onNewWorkspace ? (
            <button
              type="button"
              onClick={onNewWorkspace}
              className="flex w-full items-center justify-between px-2.5 py-1.5 text-xs transition-colors border bg-primary text-primary-foreground border-primary hover:bg-primary/90 font-medium"
            >
              <div className="flex items-center gap-1.5">
                <Plus className="h-3.5 w-3.5" />
                <span>New data room</span>
              </div>
              <kbd className="font-mono text-[10px] px-1 border border-primary-foreground/30 text-primary-foreground/80">
                ⌘K
              </kbd>
            </button>
          ) : (
            <Link
              href="/rooms/new"
              className="flex w-full items-center justify-between px-2.5 py-1.5 text-xs transition-colors border bg-primary text-primary-foreground border-primary hover:bg-primary/90 font-medium"
            >
              <div className="flex items-center gap-1.5">
                <Plus className="h-3.5 w-3.5" />
                <span>New data room</span>
              </div>
              <kbd className="font-mono text-[10px] px-1 border border-primary-foreground/30 text-primary-foreground/80">
                ⌘K
              </kbd>
            </Link>
          )
        ) : onNewThread ? (
          <button
            type="button"
            disabled={isUploadRunning || isReviewPending}
            onClick={onNewThread}
            className={`flex w-full items-center justify-between border border-sidebar-border bg-sidebar px-2.5 py-1.5 text-xs text-sidebar-foreground transition-colors font-normal ${
              isUploadRunning || isReviewPending
                ? "opacity-40 cursor-not-allowed pointer-events-none"
                : "hover:bg-sidebar-accent"
            }`}
            title={isUploadRunning || isReviewPending ? "Finish or approve upload before starting a new chat" : undefined}
          >
            <div className="flex items-center gap-1.5">
              <Plus className="h-3.5 w-3.5" />
              <span>New chat</span>
            </div>
            <kbd className="font-mono text-[10px] text-muted-foreground border border-sidebar-border px-1">
              ⌘K
            </kbd>
          </button>
        ) : isUploadRunning || isReviewPending ? (
          <div
            className="flex w-full items-center justify-between border border-sidebar-border bg-sidebar px-2.5 py-1.5 text-xs text-sidebar-foreground opacity-40 cursor-not-allowed select-none font-normal"
            title="Finish or approve upload before starting a new chat"
          >
            <div className="flex items-center gap-1.5">
              <Plus className="h-3.5 w-3.5" />
              <span>New chat</span>
            </div>
            <kbd className="font-mono text-[10px] text-muted-foreground border border-sidebar-border px-1">
              ⌘K
            </kbd>
          </div>
        ) : (
          <Link
            href={`/rooms/${roomId}`}
            className="flex w-full items-center justify-between border border-sidebar-border bg-sidebar px-2.5 py-1.5 text-xs text-sidebar-foreground hover:bg-sidebar-accent transition-colors font-normal"
          >
            <div className="flex items-center gap-1.5">
              <Plus className="h-3.5 w-3.5" />
              <span>New chat</span>
            </div>
            <kbd className="font-mono text-[10px] text-muted-foreground border border-sidebar-border px-1">
              ⌘K
            </kbd>
          </Link>
        )}

        {/* 4. List: RoomList (hub mode) or ThreadList (room mode) */}
        {mode === "hub" ? (
          <RoomList
            workspaces={workspaces}
            activeRoomId={activeRoomId}
            loading={loadingWorkspaces}
            error={workspacesError}
            onRetry={onRetryWorkspaces}
            onSelectWorkspace={onSelectWorkspace}
            onDeleteWorkspace={onDeleteWorkspace}
          />
        ) : (
          <ThreadList
            roomId={roomId}
            threads={threads}
            activeThreadId={activeThreadId}
            onSelectThread={onSelectThread}
            onDeleteThread={onDeleteThread}
          />
        )}
      </div>

      {/* 5. Pinned bottom: User Profile Footer */}
      <UserProfileFooter onOpenAuthModal={onOpenAuthModal} />
    </div>
  )
}

export const Sidebar = React.memo(SidebarComponent)
