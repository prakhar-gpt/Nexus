"use client"

import { FileSpreadsheet, Upload } from "lucide-react"

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

const STAGES = ["Safety", "Structure", "Profiling", "Mapping"] as const

const HEALTH = ["Rows", "Date range", "Revenue", "Quarantine"] as const

export type LocalFile = {
  name: string
  size: number
}

function formatSize(size: number) {
  if (size < 1024) {
    return `${size} B`
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function DataPane({
  file,
  error,
  onFile,
}: {
  file: LocalFile | null
  error: string | null
  onFile: (file: File) => void
}) {
  return (
    <section className="flex min-h-[32rem] min-w-0 flex-col border-b xl:min-h-0 xl:border-r xl:border-b-0">
      <header className="flex h-12 shrink-0 items-center px-4">
        <h2 className="text-sm font-medium">Data & Health</h2>
      </header>
      <ScrollArea className="min-h-0 flex-1">
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
            <span className="text-xs text-muted-foreground">
              csv or xlsx. The file stays in this browser until upload is connected.
            </span>
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

          {file ? (
            <Card size="sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileSpreadsheet className="size-4" />
                  <span className="truncate">{file.name}</span>
                </CardTitle>
                <CardDescription>{formatSize(file.size)}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Badge variant="outline">Selected</Badge>
                <ul className="flex flex-col gap-2">
                  {STAGES.map((stage) => (
                    <li
                      key={stage}
                      className="flex items-center justify-between text-sm"
                    >
                      <span>{stage}</span>
                      <span className="text-muted-foreground">Not started</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : (
            <Empty className="border">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <FileSpreadsheet />
                </EmptyMedia>
                <EmptyTitle>No file selected</EmptyTitle>
                <EmptyDescription>
                  Safety, structure, profiling, and mapping appear after a file is chosen.
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
            <CardContent>
              <p className="text-sm text-muted-foreground">
                No columns are waiting.
              </p>
            </CardContent>
          </Card>

          <Card size="sm">
            <CardHeader>
              <CardTitle>Health</CardTitle>
              <CardDescription>
                Filled from the loaded table once this screen can read it.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="flex flex-col gap-2">
                {HEALTH.map((label) => (
                  <div key={label} className="flex items-center justify-between text-sm">
                    <dt className="text-muted-foreground">{label}</dt>
                    <dd>—</dd>
                  </div>
                ))}
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
                  <TableRow>
                    <TableCell colSpan={2} className="text-muted-foreground">
                      No quarantined rows.
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
              <Button variant="outline" size="sm" disabled>
                Download CSV
              </Button>
            </CardContent>
          </Card>
        </div>
      </ScrollArea>
    </section>
  )
}
