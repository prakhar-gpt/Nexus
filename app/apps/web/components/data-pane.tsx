"use client"

import { useEffect, useState } from "react"
import { FileSpreadsheet, Upload } from "lucide-react"

import { API_URL, type Mapping } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

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

const STAGE_LABELS = ["safety", "structure", "profiling", "mapping", "load"] as const

export function DataPane({
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
  onFile,
  onConfirm,
}: {
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
  onFile: (file: File) => void
  onConfirm: (decisions: Record<string, string>) => void
}) {
  const pending = mappings.filter((item) => item.needs_confirmation)
  const pendingKey = pending.map((item) => `${item.source}:${item.canonical ?? ""}`).join("|")
  const [choices, setChoices] = useState<Record<string, string>>({})

  useEffect(() => {
    const next: Record<string, string> = {}
    for (const item of pending) {
      if (item.canonical) {
        next[item.source] = item.canonical
      }
    }
    setChoices(next)
  }, [pendingKey])

  const dateRange =
    health?.first_order && health.last_order
      ? `${health.first_order} – ${health.last_order}`
      : "—"

  return (
    <section className="flex min-h-[32rem] min-w-0 flex-col overflow-hidden border-b xl:h-full xl:min-h-0 xl:border-r xl:border-b-0">
      <header className="flex h-12 shrink-0 items-center px-4">
        <h2 className="text-sm font-medium">Data & Health</h2>
      </header>
      <ScrollArea className="min-h-0 flex-1 basis-0 overflow-hidden">
        <div className="flex flex-col gap-4 px-4 pb-4">
          <label
            className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center transition-colors hover:bg-muted/60"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault()
              const next = event.dataTransfer.files.item(0)
              if (next) {
                onFile(next)
              }
            }}
          >
            <Upload className="size-4 text-muted-foreground" />
            <span className="text-sm font-medium">Drop a spreadsheet</span>
            <span className="text-xs text-muted-foreground">csv or xlsx</span>
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

          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}

          {fileName ? (
            <Card size="sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileSpreadsheet className="size-4" />
                  <span className="truncate">{fileName}</span>
                </CardTitle>
                {status ? <CardDescription>{status}</CardDescription> : null}
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {reason ? <p className="text-sm text-destructive">{reason}</p> : null}
                {stages.length > 0 ? (
                  <ul className="flex flex-col gap-2">
                    {STAGE_LABELS.map((stage) => {
                      const found = [...stages].reverse().find((item) => item.stage === stage)
                      return (
                        <li key={stage} className="flex items-center justify-between text-sm">
                          <span className="capitalize">{stage}</span>
                          <span className="text-muted-foreground">{found?.status ?? "Not started"}</span>
                        </li>
                      )
                    })}
                  </ul>
                ) : null}
              </CardContent>
            </Card>
          ) : (
            <Empty className="border">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FileSpreadsheet />
                </EmptyMedia>
                <EmptyTitle>No file loaded</EmptyTitle>
                <EmptyDescription>
                  Safety, structure, profiling, and mapping run after a file is uploaded.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}

          <Card size="sm">
            <CardHeader>
              <CardTitle>Mapping</CardTitle>
              <CardDescription>
                Columns under a confidence of 70 wait here for confirmation.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {pending.length === 0 ? (
                <p className="text-sm text-muted-foreground">No columns are waiting.</p>
              ) : (
                pending.map((item) => (
                  <label key={item.source} className="flex flex-col gap-1 text-sm">
                    <span>
                      {item.source}{" "}
                      <Badge variant="outline">{item.method}</Badge>
                    </span>
                    <select
                      className="h-8 rounded-lg border border-input bg-transparent px-2"
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
                ))
              )}
              {pending.length > 0 ? (
                <Button
                  size="sm"
                  disabled={confirming}
                  onClick={() => onConfirm(choices)}
                >
                  Confirm mapping
                </Button>
              ) : null}
            </CardContent>
          </Card>

          <Card size="sm">
            <CardHeader>
              <CardTitle>Health</CardTitle>
              <CardDescription>From the loaded table in this data room.</CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="flex flex-col gap-2">
                <HealthRow label="Rows" value={health?.rows || "—"} />
                <HealthRow label="Date range" value={dateRange} />
                <HealthRow label="Revenue" value={health?.revenue || "—"} />
                <HealthRow label="Quarantine" value={health?.quarantine || "—"} />
              </dl>
            </CardContent>
          </Card>

          <Card size="sm">
            <CardHeader>
              <CardTitle>Quarantine</CardTitle>
              <CardDescription>Rows kept aside, with the reason.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Line</TableHead>
                    <TableHead>Reason</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {quarantine.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={2} className="text-muted-foreground">
                        No quarantined rows.
                      </TableCell>
                    </TableRow>
                  ) : (
                    quarantine.map((row) => (
                      <TableRow key={`${row.row_number}-${row.reason}`}>
                        <TableCell>{row.row_number}</TableCell>
                        <TableCell>{row.reason}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
              {uploadId ? (
                <Button variant="outline" size="sm" render={<a href={`${API_URL}/uploads/${uploadId}/health?download=quarantine`} />}>
                  Download CSV
                </Button>
              ) : (
                <Button variant="outline" size="sm" disabled>
                  Download CSV
                </Button>
              )}
            </CardContent>
          </Card>
        </div>
      </ScrollArea>
    </section>
  )
}

function HealthRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  )
}
