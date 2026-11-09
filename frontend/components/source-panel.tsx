"use client"

import React, { useCallback, useEffect, useState } from "react"
import { Calculator, Check, Copy, Database, Download, RefreshCw, X } from "lucide-react"

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  getSourceRecord,
  getSourceRows,
  getSourceRowsExportUrl,
  type ClaimProvenanceItem,
  type SourceRecord,
  type SourceRowsResult,
} from "@/lib/api"
import { explainSource, type SourceExplanation } from "@/lib/source-explanation"

const recordCache = new Map<string, SourceRecord>()

interface SourcePanelProps {
  open: boolean
  onClose: () => void
  runId: string | number | null
  claim: ClaimProvenanceItem | null
  claimIndex?: number | null
  triggerRef?: React.RefObject<HTMLElement | null>
}

function formatValue(value: unknown): string {
  if (value == null) return "—"
  if (typeof value === "number") return value.toLocaleString()
  return String(value)
}

function originFor(claim: ClaimProvenanceItem | null, record: SourceRecord | null): {
  label: string
  detail: string
  icon: typeof Database
} {
  const source = claim?.source ?? record?.origin_type
  if (source === "python") {
    return {
      label: "Calculated from your data",
      detail: "Checking the figures used in this calculation.",
      icon: Calculator,
    }
  }
  if (source === "prompt") {
    return {
      label: "Stated in your message",
      detail: "This number came from your question. It was not found in the dataset.",
      icon: Database,
    }
  }
  if (claim?.status === "untraced" || source === "none") {
    return {
      label: "Not found in the data",
      detail: "This number could not be matched to the checked results.",
      icon: Database,
    }
  }
  return {
    label: "From your data",
    detail: "Checking where this number appears in the result.",
    icon: Database,
  }
}

export function SourcePanel({
  open,
  onClose,
  runId,
  claim,
  claimIndex,
  triggerRef,
}: SourcePanelProps) {
  const [record, setRecord] = useState<SourceRecord | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showDetails, setShowDetails] = useState(false)
  const [showRows, setShowRows] = useState(false)
  const [rowsResult, setRowsResult] = useState<SourceRowsResult | null>(null)
  const [loadingRows, setLoadingRows] = useState(false)
  const [copied, setCopied] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  const loadRecord = useCallback(async (force = false) => {
    if (!runId || !claim) return
    if (claim.source === "prompt" || claim.source === "none" || claim.status === "untraced") {
      setRecord(null)
      setError(null)
      setLoading(false)
      return
    }
    const queryId = claim.query_id ?? 1
    const cacheKey = `${runId}:${queryId}:${claim.column ?? ""}:${claim.claim ?? ""}`
    const cached = recordCache.get(cacheKey)
    if (cached && !force) {
      setRecord(cached)
      setError(null)
      return
    }

    setRecord(null)
    setLoading(true)
    setError(null)
    try {
      const next = await getSourceRecord(runId, queryId, claimIndex ?? undefined)
      recordCache.set(cacheKey, next)
      setRecord(next)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the source.")
    } finally {
      setLoading(false)
    }
  }, [claim, claimIndex, runId])

  useEffect(() => {
    if (open) {
      setShowDetails(false)
      setShowRows(false)
      setRowsResult(null)
      void loadRecord()
    } else {
      triggerRef?.current?.focus()
    }
  }, [loadRecord, open, triggerRef])

  useEffect(() => {
    const updateViewport = () => setIsMobile(window.innerWidth < 768)
    updateViewport()
    window.addEventListener("resize", updateViewport)
    return () => window.removeEventListener("resize", updateViewport)
  }, [])

  useEffect(() => {
    if (!open) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", closeOnEscape)
    return () => window.removeEventListener("keydown", closeOnEscape)
  }, [onClose, open])

  async function inspectRows() {
    if (!runId || !claim) return
    setLoadingRows(true)
    try {
      const next = await getSourceRows(
        runId,
        claim.query_id ?? 1,
        50,
        claimIndex ?? undefined,
        claim.row_index ?? undefined
      )
      setRowsResult(next)
    } catch {
      setRowsResult({
        rewritable: false,
        message: "These results cannot be expanded into individual rows.",
      })
    } finally {
      setLoadingRows(false)
      setShowRows(true)
    }
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      setError("Could not copy the query.")
    }
  }

  const origin = originFor(claim, record)
  const OriginIcon = origin.icon
  const explanation = explainSource(claim, record)
  const queryId = claim?.query_id ?? record?.query_id ?? 1
  const upstream = record?.upstream_queries?.[0]
  const query = record?.sql || upstream?.sql
  const isPython = claim?.source === "python" || record?.origin_type === "python"
  const isRemoved = record?.dataset_removed || record?.dataset_status === "removed"
  const headingNumber = explanation?.displayClaim || claim?.claim || "this number"

  return (
    <Sheet open={open} onOpenChange={(value) => !value && onClose()}>
      <SheetContent
        side={isMobile ? "bottom" : "right"}
        showCloseButton={false}
        className={`w-full overflow-y-auto border-border bg-card p-0 font-mono text-foreground ${
          isMobile ? "max-h-[88vh]" : "sm:max-w-lg"
        }`}
      >
        <SheetHeader className="sticky top-0 z-10 border-b border-border bg-card p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <OriginIcon className="h-3.5 w-3.5" />
                <span>{explanation?.eyebrow ?? origin.label}</span>
              </div>
              <SheetTitle className="text-base font-medium">
                Where did {headingNumber} come from?
              </SheetTitle>
              <SheetDescription className="max-w-md text-sm leading-relaxed text-foreground">
                {isRemoved
                  ? "The dataset was removed, but this saved source is still shown."
                  : explanation?.detail || origin.detail}
              </SheetDescription>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close source panel"
              className="shrink-0 p-1 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </SheetHeader>

        <div className="space-y-5 p-5">
          {loading ? (
            <div className="space-y-3 animate-pulse" aria-label="Loading source">
              <div className="h-16 bg-muted" />
              <div className="h-24 bg-muted/60" />
            </div>
          ) : null}

          {error ? (
            <div role="alert" className="space-y-2 border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
              <p>{error}</p>
              <button
                type="button"
                onClick={() => void loadRecord(true)}
                className="inline-flex items-center gap-1 font-medium underline underline-offset-2"
              >
                <RefreshCw className="h-3 w-3" />
                Retry
              </button>
            </div>
          ) : null}

          {!loading && !error && explanation && (explanation.equation || explanation.figures.length > 0) ? (
            <ExplanationBody explanation={explanation} />
          ) : null}

          {!loading && !error && record ? (
            <>
              {query || record.code ? (
                <div className="border-t border-border pt-4">
                  <button
                    type="button"
                    onClick={() => setShowDetails((value) => !value)}
                    className="text-xs font-medium text-foreground underline underline-offset-4"
                  >
                    {showDetails ? "Hide the query" : "Show the query"}
                  </button>
                  {showDetails ? (
                    <div className="mt-3 space-y-3">
                      {record.code ? (
                        <TechnicalBlock label="Python code" value={record.code} onCopy={copy} copied={copied} />
                      ) : null}
                      {query ? (
                        <TechnicalBlock label="SQL query" value={query} onCopy={copy} copied={copied} />
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {query && !isPython ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={loadingRows}
                    onClick={() => void inspectRows()}
                    className="border border-border px-3 py-1.5 text-xs hover:bg-accent disabled:opacity-50"
                  >
                    {loadingRows ? "Loading rows…" : showRows ? "Refresh rows" : "View rows behind this"}
                  </button>
                  <a
                    href={getSourceRowsExportUrl(
                      runId!,
                      queryId,
                      claimIndex ?? undefined,
                      claim?.row_index ?? undefined
                    )}
                    className="inline-flex items-center gap-1.5 border border-border px-3 py-1.5 text-xs hover:bg-accent"
                    download
                  >
                    <Download className="h-3 w-3" />
                    Download CSV
                  </a>
                </div>
              ) : null}

              {showRows && rowsResult ? <RowsPreview result={rowsResult} /> : null}
            </>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function ExplanationBody({ explanation }: { explanation: SourceExplanation }) {
  return (
    <>
      {explanation.equation ? (
        <p className="text-sm leading-relaxed">{explanation.equation}</p>
      ) : null}
      {explanation.numbers ? (
        <p className="text-sm leading-relaxed tabular-nums">{explanation.numbers}</p>
      ) : null}
      {explanation.figures.length ? (
        <section className="border border-border">
          <p className="border-b border-border px-4 py-3 text-[10px] uppercase tracking-wider text-muted-foreground">
            {explanation.dataset ? `From ${explanation.dataset}` : "From your data"}
            {explanation.scope ? <span className="normal-case tracking-normal"> · {explanation.scope}</span> : null}
          </p>
          <div className="space-y-2 px-4 py-3 text-xs">
            {explanation.figures.map((figure) => (
              <div key={`${figure.label}-${figure.value}`} className="flex items-baseline justify-between gap-4">
                <span>
                  <span className="font-medium">{figure.label}</span>
                  {figure.note ? <span className="text-muted-foreground"> · {figure.note}</span> : null}
                </span>
                <span className="shrink-0 text-right tabular-nums">{figure.value}</span>
              </div>
            ))}
          </div>
          {explanation.caveat ? (
            <p className="border-t border-border px-4 py-3 text-[11px] leading-relaxed text-muted-foreground">
              {explanation.caveat}
            </p>
          ) : null}
        </section>
      ) : null}
    </>
  )
}

function TechnicalBlock({
  label,
  value,
  onCopy,
  copied,
}: {
  label: string
  value: string
  onCopy: (value: string) => void
  copied: boolean
}) {
  return (
    <div className="border border-border bg-muted/20">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
        <button type="button" onClick={() => onCopy(value)} className="text-muted-foreground hover:text-foreground" aria-label={`Copy ${label}`}>
          {copied ? <Check className="h-3 w-3 text-ok" /> : <Copy className="h-3 w-3" />}
        </button>
      </div>
      <pre className="max-h-48 overflow-auto p-3 text-[11px] leading-relaxed">{value}</pre>
    </div>
  )
}

function RowsPreview({ result }: { result: SourceRowsResult }) {
  if (!result.rewritable) {
    return <p className="text-xs text-muted-foreground">{result.message || "These results cannot be expanded into rows."}</p>
  }

  const rows = result.rows || []
  const headers = rows[0] ? Object.keys(rows[0]) : []
  return (
    <section className="space-y-2">
      <p className="text-[11px] text-muted-foreground">
        Showing {rows.length.toLocaleString()} of {(result.total_rows ?? 0).toLocaleString()} rows.
      </p>
      <div className="max-h-56 overflow-auto border border-border">
        <table className="w-full text-left text-[11px] tabular-nums">
          <thead className="sticky top-0 border-b border-border bg-muted">
            <tr>
              {headers.map((header) => <th key={header} className="whitespace-nowrap p-2 font-medium">{header === "source_row" ? "Row in your file" : header}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {rows.map((row, index) => (
              <tr key={index}>
                {headers.map((header) => <td key={header} className="whitespace-nowrap p-2">{formatValue(row[header])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
