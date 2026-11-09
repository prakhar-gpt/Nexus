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
  onUploadFile?: (file: File) => void
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
    onUploadFile,
  },
  ref
) {
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f && onUploadFile) {
      onUploadFile(f)
      e.target.value = ""
    }
  }

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

  // Otherwise, render clean in-place dropzone replacing the composer
  return (
    <div className="w-full max-w-[720px] mx-auto px-4 pb-4">
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx"
        className="hidden"
        onChange={handleFileChange}
      />
      {status.type === "empty" && (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border border-dashed border-border hover:border-foreground/60 bg-card p-4 cursor-pointer transition-colors"
        >
          <div className="flex flex-col gap-0.5">
            <p className="text-xs font-medium text-foreground">
              Add a dataset to start
            </p>
            <p className="text-[11px] text-muted-foreground">
              Drop or select a .csv or .xlsx to analyze.
            </p>
          </div>
          <button
            type="button"
            className={buttonVariants({ size: "sm", className: "h-8 text-xs font-medium shrink-0 pointer-events-none" })}
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            <span>Select file</span>
          </button>
        </div>
      )}

      {status.type === "ingesting" && (
        <div className="flex items-center gap-2 border border-border bg-card p-3.5 text-xs text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-foreground shrink-0" />
          <span>Nexus is analyzing your file in chat…</span>
        </div>
      )}

      {status.type === "rejected" && (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border border-destructive/20 bg-destructive/10 p-4 text-xs text-destructive cursor-pointer hover:border-destructive/40 transition-colors"
        >
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <div className="flex flex-col gap-0.5">
              <span className="font-medium text-foreground">Upload rejected</span>
              <span className="text-[11px] text-destructive">{status.reason}</span>
            </div>
          </div>
          <button
            type="button"
            className={buttonVariants({ variant: "outline", size: "sm", className: "h-8 text-xs shrink-0 pointer-events-none" })}
          >
            <span>Upload a different file</span>
          </button>
        </div>
      )}

      <p className="mt-2 text-center text-[11px] text-muted-foreground select-none">
        Answers are checked against query results. Verify before sharing.
      </p>
    </div>
  )
})
