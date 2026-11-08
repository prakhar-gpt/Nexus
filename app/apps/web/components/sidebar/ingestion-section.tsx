"use client"

import { FileSpreadsheet, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { API_URL, type Mapping } from "@/lib/api"

const CANONICAL = [
  "order_date",
  "customer_id",
  "product_id",
  "quantity",
  "revenue",
  "unit_price",
  "discount_pct",
  "cost",
  "profit",
  "segment",
  "region",
  "category",
  "sub_category",
  "channel",
] as const

const STAGE_LABEL: Record<string, string> = {
  safety: "Checking file",
  structure: "Reading sheet",
  profiling: "Detecting header",
  mapping: "Matching columns",
  load: "Loading rows",
}

interface IngestionSectionProps {
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
}

export function IngestionSection({
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
}: IngestionSectionProps) {
  const pending = mappings.filter((item) => item.needs_confirmation)
  const latestStage = [...stages].reverse().find((item) => item.status !== "done")

  return (
    <div className="flex flex-col gap-2 pt-2 border-t border-sidebar-border/40">
      <div className="flex items-center justify-between px-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/80">
          Spreadsheet Data
        </span>
      </div>

      {fileName ? (
        <div className="flex items-center gap-1.5 text-xs text-foreground/90 truncate px-1">
          <FileSpreadsheet className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="truncate">{fileName}</span>
        </div>
      ) : null}

      {latestStage ? (
        <p className="text-xs text-muted-foreground animate-pulse px-1">
          {STAGE_LABEL[latestStage.stage] ?? "Reading sheet"}…
        </p>
      ) : status && status !== "loaded" ? (
        <p className="text-xs text-muted-foreground px-1">{status.replaceAll("_", " ")}</p>
      ) : null}

      {reason ? (
        <div className="flex items-start gap-1 text-xs text-destructive px-1">
          <AlertCircle className="h-3 w-3 mt-0.5 shrink-0" />
          <span>{reason}</span>
        </div>
      ) : null}

      <label
        className="w-full text-center py-2 px-3 border border-dashed border-input rounded cursor-pointer text-xs text-muted-foreground hover:text-foreground hover:border-muted-foreground/60 transition-colors"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          const file = e.dataTransfer.files.item(0)
          if (file) onFile(file)
        }}
      >
        <span>+ Drop sales CSV/Excel</span>
        <input
          className="sr-only"
          type="file"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(e) => {
            const file = e.target.files?.item(0)
            if (file) onFile(file)
            e.target.value = ""
          }}
        />
      </label>

      {/* Confirmation for Ambiguous Columns */}
      {pending.length > 0 ? (
        <div className="flex flex-col gap-2 p-2.5 rounded bg-muted/40 border border-border text-xs">
          <p className="font-medium text-foreground">Confirm Column Mappings</p>
          {pending.map((item) => (
            <label key={item.source} className="flex flex-col gap-0.5">
              <span className="text-muted-foreground font-mono text-[11px]">{item.source}</span>
              <select
                className="h-7 border border-input bg-background rounded px-1.5 text-xs"
                defaultValue={item.canonical ?? ""}
                id={`map-${item.source}`}
              >
                <option value="">Skip column</option>
                {CANONICAL.map((col) => (
                  <option key={col} value={col}>
                    {col}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <Button
            size="sm"
            className="h-7 text-xs mt-1"
            disabled={confirming}
            onClick={() => {
              const decisions: Record<string, string> = {}
              for (const item of pending) {
                const el = document.getElementById(`map-${item.source}`) as HTMLSelectElement | null
                if (el) decisions[item.source] = el.value
              }
              onConfirm(decisions)
            }}
          >
            {confirming ? "Saving…" : "Confirm Mapping"}
          </Button>
        </div>
      ) : null}

      {/* Quarantined Rows */}
      {quarantine.length > 0 ? (
        <div className="flex flex-col gap-1 text-xs text-muted-foreground pt-1 border-t border-sidebar-border/40 px-1">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/80">
            Quarantine
          </span>
          {quarantine.slice(0, 3).map((row) => (
            <p key={`${row.row_number}-${row.reason}`} className="truncate text-[11px]">
              Row {row.row_number}: {row.reason}
            </p>
          ))}
          {uploadId ? (
            <a
              className="mt-0.5 text-[11px] text-primary hover:underline"
              href={`${API_URL}/uploads/${uploadId}/health?download=quarantine`}
            >
              Download report CSV
            </a>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

