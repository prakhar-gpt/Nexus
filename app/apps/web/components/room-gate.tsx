"use client"

import React, { forwardRef } from "react"
import Link from "next/link"
import { Loader2, AlertCircle, Plus, ArrowRight } from "lucide-react"
import { buttonVariants } from "@/components/ui/button"
import { Composer, type ComposerHandle } from "@/components/composer"
import type { RoomStatus } from "@/lib/room-status"

interface RoomGateProps {
  status: RoomStatus
  roomId: string | number
  datasetName?: string
  draft: string
  busy: boolean
  lastQuestion?: string
  onDraft: (value: string) => void
  onAsk: (question: string) => void
  onAbort?: () => void
}

export const RoomGate = forwardRef<ComposerHandle, RoomGateProps>(function RoomGate(
  {
    status,
    roomId,
    datasetName = "Superstore",
    draft,
    busy,
    lastQuestion,
    onDraft,
    onAsk,
    onAbort,
  },
  ref
) {
  // If status is ready, render the normal composer
  if (status.type === "ready") {
    return (
      <Composer
        ref={ref}
        draft={draft}
        busy={busy}
        lastQuestion={lastQuestion}
        placeholder={`Ask a question about ${datasetName}…`}
        onDraft={onDraft}
        onAsk={onAsk}
        onAbort={onAbort}
      />
    )
  }

  // Otherwise, render gated states replacing the composer in the centered 720px column
  return (
    <div className="w-full max-w-[720px] mx-auto px-4 pb-4">
      {status.type === "empty" && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border border-border bg-card p-4">
          <div className="flex flex-col gap-0.5">
            <h3 className="text-xs font-medium text-foreground">
              Add a dataset to start
            </h3>
            <p className="text-[11px] text-muted-foreground">
              Upload a .csv or .xlsx of retail sales to begin analysis.
            </p>
          </div>
          <Link
            href={`/rooms/${roomId}/dataset`}
            className={buttonVariants({ size: "sm", className: "h-8 text-xs font-medium shrink-0" })}
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            <span>Add dataset</span>
          </Link>
        </div>
      )}

      {status.type === "ingesting" && (
        <div className="flex items-center justify-between border border-border bg-card p-3.5 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-foreground" />
            <span>Loading your file…</span>
          </div>
          <Link
            href={`/rooms/${roomId}/dataset`}
            className="text-xs font-medium text-foreground underline underline-offset-4 hover:opacity-80"
          >
            View progress
          </Link>
        </div>
      )}

      {status.type === "needs_confirmation" && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border border-warn/30 bg-warn/5 p-4 text-xs">
          <div className="flex items-center gap-2 text-warn">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="font-medium text-foreground">
              {status.count}{" "}
              {status.count === 1 ? "column needs" : "columns need"} confirming before you can ask questions.
            </span>
          </div>
          <Link
            href={`/rooms/${roomId}/dataset`}
            className={buttonVariants({ size: "sm", className: "h-8 text-xs font-medium shrink-0" })}
          >
            <span>Review columns</span>
            <ArrowRight className="h-3 w-3 ml-1" />
          </Link>
        </div>
      )}

      {status.type === "rejected" && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border border-destructive/20 bg-destructive/10 p-4 text-xs text-destructive">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <div className="flex flex-col gap-0.5">
              <span className="font-medium text-foreground">Upload rejected</span>
              <span className="text-[11px] text-destructive">{status.reason}</span>
            </div>
          </div>
          <Link
            href={`/rooms/${roomId}/dataset`}
            className={buttonVariants({ variant: "outline", size: "sm", className: "h-8 text-xs shrink-0" })}
          >
            <span>Upload a different file</span>
          </Link>
        </div>
      )}

      <p className="mt-2 text-center text-[11px] text-muted-foreground select-none">
        Answers are checked against query results. Verify before sharing.
      </p>
    </div>
  )
})
