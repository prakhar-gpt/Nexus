"use client"

import { useState } from "react"
import dynamic from "next/dynamic"
import { Check, Copy, FileText, ChevronDown, ChevronUp, Terminal } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { TraceStep } from "@/lib/api"

// Recharts is lazy-loaded ONLY when the query panel is mounted
const AnswerChart = dynamic(
  () => import("@/components/answer-chart").then((mod) => mod.AnswerChart),
  { ssr: false, loading: () => <div className="h-[220px] animate-pulse bg-muted/40" /> }
)

interface QueryPanelProps {
  sql?: string | null
  rows?: Record<string, string | number>[]
  steps?: TraceStep[]
  sources?: { document: string; page?: number | string }[]
  runId?: number | null
  onToast?: (message: string) => void
}

const SQL_KEYWORDS = new Set([
  "SELECT",
  "FROM",
  "WHERE",
  "GROUP",
  "BY",
  "ORDER",
  "HAVING",
  "LIMIT",
  "JOIN",
  "LEFT",
  "RIGHT",
  "INNER",
  "OUTER",
  "ON",
  "AS",
  "AND",
  "OR",
  "NOT",
  "IN",
  "BETWEEN",
  "LIKE",
  "IS",
  "NULL",
  "SUM",
  "COUNT",
  "AVG",
  "MIN",
  "MAX",
  "ROUND",
  "DESC",
  "ASC",
  "DISTINCT",
  "CASE",
  "WHEN",
  "THEN",
  "ELSE",
  "END",
  "CAST",
])

function HighlightedSql({ sql }: { sql: string }) {
  const tokens = sql.split(/(\s+|[(),;])/g)

  return (
    <code>
      {tokens.map((token, i) => {
        const upper = token.toUpperCase()
        if (SQL_KEYWORDS.has(upper)) {
          return (
            <span key={i} className="font-medium text-foreground">
              {token}
            </span>
          )
        }
        if (/^'[^']*'$/.test(token) || /^\d+(\.\d+)?$/.test(token)) {
          return (
            <span key={i} className="text-muted-foreground">
              {token}
            </span>
          )
        }
        return <span key={i}>{token}</span>
      })}
    </code>
  )
}

function toolMeta(toolName: string): { label: string; description: string } {
  switch (toolName) {
    case "run_sql":
      return { label: "run_sql", description: "Read-only SQL Query" }
    case "run_python":
      return { label: "run_python", description: "Subprocess Math Sandbox" }
    case "get_schema":
      return { label: "get_schema", description: "Data Room Schema & Capabilities" }
    case "read_kb":
      return { label: "read_kb", description: "Diligence Knowledge Base" }
    default:
      return { label: toolName || "tool", description: "Tool Execution" }
  }
}

function parseToolInput(step: TraceStep, fallbackSql?: string | null): { text: string; isSql: boolean } {
  if (step.tool === "run_sql" || step.query) {
    let q = ""
    if (typeof step.input === "object" && step.input !== null && "sql" in step.input) {
      q = String((step.input as { sql?: unknown }).sql || "")
    } else if (step.query) {
      q = step.query
    } else if (typeof step.input === "string") {
      q = step.input
    } else if (fallbackSql) {
      q = fallbackSql
    }
    return { text: q || "(No SQL provided)", isSql: Boolean(q) }
  }

  if (step.tool === "run_python") {
    if (typeof step.input === "object" && step.input !== null) {
      const code = String((step.input as { code?: unknown }).code || "")
      const inputs = (step.input as { inputs?: unknown }).inputs
      let output = code
      if (Array.isArray(inputs) && inputs.length > 0) {
        output += `\n\n# Referenced inputs: ${JSON.stringify(inputs)}`
      }
      return { text: output || "(No Python code provided)", isSql: false }
    }
    if (typeof step.input === "string") {
      return { text: step.input, isSql: false }
    }
  }

  if (step.tool === "read_kb") {
    if (typeof step.input === "object" && step.input !== null && "path" in step.input) {
      return { text: `path: "${String((step.input as { path?: unknown }).path || "")}"`, isSql: false }
    }
  }

  if (step.input !== undefined && step.input !== null) {
    if (typeof step.input === "object") {
      if (Object.keys(step.input).length === 0) {
        return { text: "(No parameters)", isSql: false }
      }
      return { text: JSON.stringify(step.input, null, 2), isSql: false }
    }
    return { text: String(step.input), isSql: false }
  }

  if (step.tool === "get_schema") {
    return { text: "(Inspects canonical columns, table capabilities, and attributes)", isSql: false }
  }

  return { text: "(No input parameters)", isSql: false }
}

function parseToolOutput(step: TraceStep): string {
  if (step.output !== undefined && step.output !== null) {
    if (typeof step.output === "object") {
      return JSON.stringify(step.output, null, 2)
    }
    return String(step.output)
  }
  if (step.detail) {
    return step.detail
  }
  return "(Completed with no direct output text)"
}

export function QueryPanel({
  sql,
  rows = [],
  steps = [],
  sources = [],
  runId: _runId,
  onToast,
}: QueryPanelProps) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [copiedTsv, setCopiedTsv] = useState(false)
  const [showAllRows, setShowAllRows] = useState(false)

  // Filter out any internal checker steps
  const activeSteps = steps.filter((s) => s.tool !== "checker")

  // Fallback to synthesizing a run_sql step if steps was not provided but sql exists
  const executionSteps: TraceStep[] =
    activeSteps.length > 0
      ? activeSteps
      : sql
      ? [
          {
            id: "legacy-sql",
            tool: "run_sql",
            status: "ok",
            query: sql,
            input: { sql },
            output: rows.length > 0 ? `${rows.length} rows returned` : undefined,
          },
        ]
      : []

  const columns = rows.length > 0 ? Object.keys(rows[0]) : []
  const visibleRows = showAllRows ? rows : rows.slice(0, 10)
  const hasMoreRows = rows.length > 10
  const hasChartableData = rows.length >= 2

  async function handleCopy(key: string, text: string, toastMessage: string) {
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
      setCopiedKey(key)
      setTimeout(() => setCopiedKey(null), 2000)
    } catch {
      onToast?.(toastMessage)
    }
  }

  async function handleCopyTsv() {
    if (rows.length === 0) return
    try {
      const headers = columns.join("\t")
      const body = rows
        .map((r) => columns.map((col) => String(r[col] ?? "")).join("\t"))
        .join("\n")
      const tsv = `${headers}\n${body}`
      await navigator.clipboard.writeText(tsv)
      setCopiedTsv(true)
      setTimeout(() => setCopiedTsv(false), 2000)
    } catch {
      onToast?.("Couldn't copy table data")
    }
  }

  // Determine if result table was rendered inside a run_sql step
  const hasRunSqlStep = executionSteps.some((s) => s.tool === "run_sql" || s.query)

  return (
    <div className="mt-3 flex flex-col gap-4 border border-border bg-card p-4 text-xs transition-all">
      {/* Header Bar */}
      <div className="flex items-center justify-between border-b border-border/40 pb-2">
        <div className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Tool Execution
          </span>
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground bg-muted/50 px-1.5 py-0.2 border border-border/40">
            {executionSteps.length} {executionSteps.length === 1 ? "call" : "calls"}
          </span>
        </div>
      </div>

      {/* Render every tool call */}
      {executionSteps.map((step, idx) => {
        const meta = toolMeta(step.tool)
        const inputData = parseToolInput(step, sql)
        const outputText = parseToolOutput(step)
        const isSqlStep = step.tool === "run_sql" || Boolean(step.query)

        return (
          <div
            key={step.id || idx}
            className="flex flex-col gap-3 border border-border/80 bg-background/50 p-3.5"
          >
            {/* Step Meta Header */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/40 pb-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[11px] font-semibold text-foreground">
                  Step {idx + 1}
                </span>
                <span className="font-mono text-[11px] text-muted-foreground">·</span>
                <span className="font-mono text-[11px] font-medium text-foreground bg-muted/60 px-1.5 py-0.5 border border-border/60">
                  {meta.label}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {meta.description}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {step.ms != null ? (
                  <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                    {step.ms}ms
                  </span>
                ) : null}
                <span
                  className={`px-1.5 py-0.2 font-mono text-[10px] uppercase border ${
                    step.status === "ok"
                      ? "bg-ok/10 text-ok border-ok/20"
                      : "bg-destructive/10 text-destructive border-destructive/20"
                  }`}
                >
                  {step.status || "ok"}
                </span>
              </div>
            </div>

            {/* Input Section */}
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  Input
                </span>
                <button
                  type="button"
                  onClick={() =>
                    handleCopy(`input-${idx}`, inputData.text, "Couldn't copy input")
                  }
                  aria-label={`Copy input for step ${idx + 1}`}
                  className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                >
                  {copiedKey === `input-${idx}` ? (
                    <>
                      <Check className="h-3 w-3 text-ok" />
                      <span className="text-ok">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      <span>Copy Input</span>
                    </>
                  )}
                </button>
              </div>
              <pre className="overflow-x-auto border border-border bg-muted/30 p-2.5 font-mono text-[11px] leading-relaxed text-foreground/90 whitespace-pre-wrap select-all">
                {inputData.isSql ? (
                  <HighlightedSql sql={inputData.text} />
                ) : (
                  <code>{inputData.text}</code>
                )}
              </pre>
            </div>

            {/* Output Section */}
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  Output
                </span>
                <button
                  type="button"
                  onClick={() =>
                    handleCopy(`output-${idx}`, outputText, "Couldn't copy output")
                  }
                  aria-label={`Copy output for step ${idx + 1}`}
                  className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                >
                  {copiedKey === `output-${idx}` ? (
                    <>
                      <Check className="h-3 w-3 text-ok" />
                      <span className="text-ok">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      <span>Copy Output</span>
                    </>
                  )}
                </button>
              </div>
              <pre className="max-h-64 overflow-y-auto overflow-x-auto border border-border bg-muted/30 p-2.5 font-mono text-[11px] leading-relaxed text-foreground/90 whitespace-pre-wrap select-all">
                <code>{outputText}</code>
              </pre>
            </div>

            {/* If this is a run_sql step and we have structured rows, render table and chart */}
            {isSqlStep && rows.length > 0 ? (
              <div className="mt-2 flex flex-col gap-3 border-t border-border/40 pt-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    Query Result ({rows.length} {rows.length === 1 ? "row" : "rows"})
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyTsv}
                    aria-label="Copy table as TSV"
                    className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {copiedTsv ? (
                      <>
                        <Check className="h-3 w-3 text-ok" />
                        <span className="text-ok">Copied TSV</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" />
                        <span>Copy TSV</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="overflow-x-auto border border-border">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-b border-border bg-muted/40">
                        {columns.map((col) => {
                          const sample = rows[0]?.[col]
                          const isNum =
                            sample !== undefined && !Number.isNaN(Number(sample))
                          return (
                            <TableHead
                              key={col}
                              className={`h-7 px-3 py-1 text-[11px] font-medium text-foreground ${
                                isNum ? "text-right" : "text-left"
                              }`}
                            >
                              {col}
                            </TableHead>
                          )
                        })}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {visibleRows.map((row, rIdx) => (
                        <TableRow
                          key={rIdx}
                          className="border-b border-border/60 hover:bg-muted/20"
                        >
                          {columns.map((col) => {
                            const val = row[col]
                            const num = Number(val)
                            const isNum =
                              val !== undefined && val !== "" && !Number.isNaN(num)
                            const display =
                              isNum && typeof val === "number"
                                ? num.toLocaleString(undefined, {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2,
                                  })
                                : String(val ?? "")
                            return (
                              <TableCell
                                key={col}
                                className={`px-3 py-1.5 text-[12px] tabular-nums ${
                                  isNum
                                    ? "text-right font-mono"
                                    : "text-left text-foreground/90"
                                }`}
                              >
                                {display}
                              </TableCell>
                            )
                          })}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                {hasMoreRows ? (
                  <button
                    type="button"
                    onClick={() => setShowAllRows((prev) => !prev)}
                    className="self-start inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground pt-1 transition-colors"
                  >
                    {showAllRows ? (
                      <>
                        <ChevronUp className="h-3 w-3" />
                        <span>Show fewer rows</span>
                      </>
                    ) : (
                      <>
                        <ChevronDown className="h-3 w-3" />
                        <span>Show all {rows.length} rows</span>
                      </>
                    )}
                  </button>
                ) : null}

                {hasChartableData ? (
                  <div className="flex flex-col gap-1.5 border-t border-border/40 pt-3">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      Distribution
                    </span>
                    <AnswerChart rows={rows} />
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        )
      })}

      {/* Fallback Result Table if rows exist and weren't attached to a run_sql step */}
      {!hasRunSqlStep && rows.length > 0 ? (
        <div className="flex flex-col gap-1.5 border-t border-border/60 pt-3">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              Query Result ({rows.length} {rows.length === 1 ? "row" : "rows"})
            </span>
            <button
              type="button"
              onClick={handleCopyTsv}
              aria-label="Copy table as TSV"
              className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            >
              {copiedTsv ? (
                <>
                  <Check className="h-3 w-3 text-ok" />
                  <span className="text-ok">Copied TSV</span>
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" />
                  <span>Copy TSV</span>
                </>
              )}
            </button>
          </div>

          <div className="overflow-x-auto border border-border">
            <Table>
              <TableHeader>
                <TableRow className="border-b border-border bg-muted/40">
                  {columns.map((col) => {
                    const sample = rows[0]?.[col]
                    const isNum =
                      sample !== undefined && !Number.isNaN(Number(sample))
                    return (
                      <TableHead
                        key={col}
                        className={`h-7 px-3 py-1 text-[11px] font-medium text-foreground ${
                          isNum ? "text-right" : "text-left"
                        }`}
                      >
                        {col}
                      </TableHead>
                    )
                  })}
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleRows.map((row, index) => (
                  <TableRow
                    key={index}
                    className="border-b border-border/60 hover:bg-muted/20"
                  >
                    {columns.map((col) => {
                      const val = row[col]
                      const num = Number(val)
                      const isNum =
                        val !== undefined && val !== "" && !Number.isNaN(num)
                      const display =
                        isNum && typeof val === "number"
                          ? num.toLocaleString(undefined, {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })
                          : String(val ?? "")
                      return (
                        <TableCell
                          key={col}
                          className={`px-3 py-1.5 text-[12px] tabular-nums ${
                            isNum
                              ? "text-right font-mono"
                              : "text-left text-foreground/90"
                          }`}
                        >
                          {display}
                        </TableCell>
                      )
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {hasMoreRows ? (
            <button
              type="button"
              onClick={() => setShowAllRows((prev) => !prev)}
              className="self-start inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground pt-1 transition-colors"
            >
              {showAllRows ? (
                <>
                  <ChevronUp className="h-3 w-3" />
                  <span>Show fewer rows</span>
                </>
              ) : (
                <>
                  <ChevronDown className="h-3 w-3" />
                  <span>Show all {rows.length} rows</span>
                </>
              )}
            </button>
          ) : null}

          {hasChartableData ? (
            <div className="flex flex-col gap-1.5 border-t border-border/60 pt-3">
              <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                Distribution
              </span>
              <AnswerChart rows={rows} />
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Document Source Chips (if source events exist) */}
      {sources && sources.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
          <span className="text-[11px] text-muted-foreground">Sources:</span>
          {sources.map((src, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 border border-border bg-muted/40 px-2 py-0.5 text-[11px] text-foreground/90"
            >
              <FileText className="h-3 w-3 text-muted-foreground" />
              <span>
                {src.document}
                {src.page ? `, p. ${src.page}` : ""}
              </span>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}
