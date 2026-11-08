"use client"

import { useEffect, useState } from "react"

import { API_URL, type Mapping } from "@/lib/api"
import { Button } from "@/components/ui/button"

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
  safety: "Checking the file",
  structure: "Reading the sheet",
  profiling: "Finding the header",
  mapping: "Matching columns",
  load: "Loading rows",
}

const SCORE_LABEL: Record<string, string> = {
  sql_correctness: "SQL",
  numeric_faithfulness: "Numbers",
  refusal_accuracy: "Refusals",
}

export function DataPane({
  roomName,
  fileName,
  status,
  reason,
  stages,
  mappings,
  health,
  quarantine,
  uploadId,
  error,
  confirming,
  scores,
  runningEval,
  onFile,
  onConfirm,
  onRunEval,
}: {
  roomName: string
  fileName: string | null
  status: string | null
  reason: string | null
  stages: { stage: string; status: string }[]
  mappings: Mapping[]
  health: {
    rows: string
    first_order: string
    last_order: string
    revenue: string
    quarantine: string
  } | null
  quarantine: { row_number: string; reason: string }[]
  uploadId: string | null
  error: string | null
  confirming: boolean
  scores: Record<string, number> | null
  runningEval: boolean
  onFile: (file: File) => void
  onConfirm: (decisions: Record<string, string>) => void
  onRunEval: () => void
}) {
  const pending = mappings.filter((item) => item.needs_confirmation)
  const pendingKey = pending.map((item) => `${item.source}:${item.canonical ?? ""}`).join("|")
  const [choices, setChoices] = useState<Record<string, string>>({})
  const latestStage = [...stages].reverse().find((item) => item.status !== "done")

  useEffect(() => {
    const next: Record<string, string> = {}
    for (const item of pending) {
      if (item.canonical) {
        next[item.source] = item.canonical
      }
    }
    setChoices(next)
  }, [pendingKey])

  const rows = health?.rows && health.rows !== "0" ? `${Number(health.rows).toLocaleString()} rows` : null
  const dates =
    health?.first_order && health.last_order
      ? `${health.first_order} to ${health.last_order}`
      : null

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto px-4 py-5">
      <div>
        <p className="text-xl tracking-tight">{roomName}</p>
        {rows ? <p className="mt-1 text-sm text-muted-foreground">{rows}</p> : null}
        {dates ? <p className="text-sm text-muted-foreground">{dates}</p> : null}
      </div>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <div className="flex flex-col gap-2 text-sm">
        {fileName ? <p className="truncate text-foreground/80">{fileName}</p> : null}
        {latestStage ? (
          <p className="text-muted-foreground">
            {STAGE_LABEL[latestStage.stage] ?? "Reading the file"}…
          </p>
        ) : status && status !== "loaded" ? (
          <p className="text-muted-foreground">{status.replaceAll("_", " ")}</p>
        ) : null}
        {reason ? <p className="text-destructive">{reason}</p> : null}
        <label
          className="w-fit cursor-pointer text-muted-foreground hover:text-foreground"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault()
            const next = event.dataTransfer.files.item(0)
            if (next) {
              onFile(next)
            }
          }}
        >
          Add a spreadsheet
          <input
            className="sr-only"
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(event) => {
              const next = event.target.files?.item(0)
              if (next) {
                onFile(next)
              }
              event.target.value = ""
            }}
          />
        </label>
      </div>

      {pending.length > 0 ? (
        <div className="flex flex-col gap-3 text-sm">
          <p>These columns need a confirmation before they load.</p>
          {pending.map((item) => (
            <label key={item.source} className="flex flex-col gap-1">
              <span className="text-muted-foreground">{item.source}</span>
              <select
                className="h-8 border border-input bg-transparent px-2"
                value={choices[item.source] ?? ""}
                onChange={(event) =>
                  setChoices((current) => ({
                    ...current,
                    [item.source]: event.target.value,
                  }))
                }
              >
                <option value="">Skip</option>
                {CANONICAL.map((column) => (
                  <option key={column} value={column}>
                    {column}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <Button size="sm" disabled={confirming} onClick={() => onConfirm(choices)}>
            {confirming ? "Saving…" : "Confirm"}
          </Button>
        </div>
      ) : null}

      {quarantine.length > 0 ? (
        <div className="flex flex-col gap-1 text-sm text-muted-foreground">
          <p className="text-foreground/80">Set aside</p>
          {quarantine.slice(0, 5).map((row) => (
            <p key={`${row.row_number}-${row.reason}`}>
              Line {row.row_number}: {row.reason}
            </p>
          ))}
          {uploadId ? (
            <a
              className="mt-1 w-fit underline-offset-4 hover:underline"
              href={`${API_URL}/uploads/${uploadId}/health?download=quarantine`}
            >
              Download
            </a>
          ) : null}
        </div>
      ) : null}

      <div className="mt-auto flex flex-col gap-1 pt-6 text-xs text-muted-foreground">
        {scores ? (
          <p>
            {Object.entries(scores)
              .map(([name, score]) => `${SCORE_LABEL[name] ?? name} ${Math.round(score * 100)}%`)
              .join(" · ")}
          </p>
        ) : null}
        <button
          type="button"
          className="w-fit text-left hover:text-foreground disabled:opacity-50"
          disabled={runningEval}
          onClick={onRunEval}
        >
          {runningEval ? "Scoring…" : "Score the golden set"}
        </button>
      </div>
    </div>
  )
}
