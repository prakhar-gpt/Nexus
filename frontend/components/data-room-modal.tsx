"use client"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Dropzone } from "@/components/dropzone"
import { PipelineStepper } from "@/components/pipeline-stepper"
import { MappingTable } from "@/components/mapping-table"
import { API_URL, type Mapping } from "@/lib/api"
import { Download } from "lucide-react"

interface DataRoomModalProps {
  isOpen: boolean
  onClose: () => void
  roomName: string
  fileName: string | null
  status: string | null
  reason: string | null
  stages: { stage: string; status: string; reason?: string }[]
  mappings: Mapping[]
  uploadId: string | null
  quarantine: { row_number: string; reason: string; raw_value?: string }[]
  confirming: boolean
  onFile: (file: File) => void
  onConfirm: (decisions: Record<string, string>) => Promise<boolean>
  healthSummary?: {
    rows: string | null
    dates: string | null
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
  const isUploading = status === "uploading" || (stages.length > 0 && status !== "loaded" && status !== "rejected")

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[720px] max-h-[85vh] overflow-y-auto rounded-[var(--radius)] border border-border bg-popover p-6 shadow-none">
        <DialogHeader className="gap-1 p-0 text-left pb-4 border-b border-border">
          <DialogTitle className="text-base font-medium text-foreground">
            {roomName} dataset
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            Manage spreadsheet ingestion, column mapping decisions, and quarantine audits.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col divide-y divide-border pt-1">
          {/* Section 1: Summary */}
          <div className="py-4">
            <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground block mb-2">
              Dataset summary
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="border border-border/60 bg-muted/20 p-2.5">
                <span className="text-[11px] text-muted-foreground block">Rows loaded</span>
                <span className="font-mono text-sm font-medium tabular-nums text-foreground">
                  {healthSummary?.rows ?? "0 rows"}
                </span>
              </div>
              <div className="border border-border/60 bg-muted/20 p-2.5">
                <span className="text-[11px] text-muted-foreground block">Date range</span>
                <span className="font-mono text-xs font-medium tabular-nums text-foreground truncate block">
                  {healthSummary?.dates ?? "None"}
                </span>
              </div>
              <div className="border border-border/60 bg-muted/20 p-2.5">
                <span className="text-[11px] text-muted-foreground block">Last upload</span>
                <span className="font-mono text-xs font-medium text-foreground truncate block">
                  {fileName ?? "No file"}
                </span>
              </div>
            </div>
          </div>

          {/* Section 2: Dropzone */}
          <div className="py-4">
            <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground block mb-2">
              Upload spreadsheet
            </span>
            <Dropzone
              onFileSelect={onFile}
              disabled={isUploading}
              currentFileName={fileName}
              errorReason={reason}
            />
          </div>

          {/* Section 3: Pipeline stepper */}
          {(stages.length > 0 || status) && (
            <div className="py-4">
              <PipelineStepper
                stages={stages}
                overallStatus={status}
                overallReason={reason}
              />
            </div>
          )}

          {/* Section 4: Column mapping */}
          {mappings.length > 0 && (
            <div className="py-4">
              <MappingTable
                mappings={mappings}
                confirming={confirming}
                onConfirm={onConfirm}
              />
            </div>
          )}

          {/* Section 5: Quarantine (hidden if quarantine is empty) */}
          {quarantine.length > 0 && (
            <div className="py-4 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                  Quarantine ({quarantine.length}{" "}
                  {quarantine.length === 1 ? "row set aside" : "rows set aside"})
                </span>
                {uploadId ? (
                  <a
                    href={`${API_URL}/uploads/${uploadId}/health?download=quarantine`}
                    className="inline-flex items-center gap-1 text-[11px] text-foreground hover:underline"
                  >
                    <Download className="h-3 w-3" />
                    <span>Download report CSV</span>
                  </a>
                ) : null}
              </div>

              <div className="overflow-x-auto border border-border">
                <table className="w-full border-collapse text-left text-xs">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 font-mono text-[11px] text-muted-foreground">
                      <th className="py-1.5 px-3 w-20">Row</th>
                      <th className="py-1.5 px-3">Reason</th>
                      <th className="py-1.5 px-3">Raw value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {quarantine.slice(0, 10).map((q, idx) => (
                      <tr key={idx} className="hover:bg-muted/20">
                        <td className="py-1.5 px-3 font-mono tabular-nums text-muted-foreground">
                          {q.row_number}
                        </td>
                        <td className="py-1.5 px-3 text-destructive">{q.reason}</td>
                        <td className="py-1.5 px-3 font-mono text-[11px] text-muted-foreground truncate max-w-xs">
                          {q.raw_value ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
