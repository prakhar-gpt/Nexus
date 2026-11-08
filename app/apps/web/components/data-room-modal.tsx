"use client"

import { Database, X } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { IngestionSection } from "@/components/sidebar/ingestion-section"
import { type Mapping } from "@/lib/api"

interface DataRoomModalProps {
  isOpen: boolean
  onClose: () => void
  roomName: string
  fileName: string | null
  status: string | null
  reason: string | null
  stages: { stage: string; status: string }[]
  mappings: Mapping[]
  uploadId: string | null
  quarantine: { row_number: string; reason: string }[]
  confirming: boolean
  onFile: (file: File) => void
  onConfirm: (decisions: Record<string, string>) => void
  healthSummary?: {
    rows: string | null
    dates: string | null
    revenue?: string | null
  }
}

export function DataRoomModal({
  isOpen,
  onClose,
  roomName,
  fileName,
  status,
  reason,
  stages,
  mappings,
  uploadId,
  quarantine,
  confirming,
  onFile,
  onConfirm,
  healthSummary,
}: DataRoomModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <div className="flex items-center gap-2 mb-1">
            <div className="flex h-7 w-7 items-center justify-center rounded bg-primary/10 text-primary">
              <Database className="h-4 w-4" />
            </div>
            <DialogTitle className="text-base font-semibold">{roomName} Dataset</DialogTitle>
          </div>
          <DialogDescription className="text-xs text-muted-foreground">
            Manage spreadsheet ingestion, column mapping decisions, and quarantine reports.
          </DialogDescription>
        </DialogHeader>

        {/* Quick Health Stats */}
        <div className="grid grid-cols-2 gap-2 p-3 bg-muted/40 rounded-lg text-xs">
          <div>
            <span className="text-muted-foreground block text-[11px]">Rows Loaded</span>
            <span className="font-semibold text-foreground">{healthSummary?.rows ?? "0"}</span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[11px]">Date Range</span>
            <span className="font-semibold text-foreground font-mono text-[11px]">
              {healthSummary?.dates ?? "None"}
            </span>
          </div>
        </div>

        {/* Ingestion & Quarantine Pipeline */}
        <div className="py-2">
          <IngestionSection
            fileName={fileName}
            status={status}
            reason={reason}
            stages={stages}
            mappings={mappings}
            uploadId={uploadId}
            quarantine={quarantine}
            confirming={confirming}
            onFile={onFile}
            onConfirm={onConfirm}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}

