"use client"

import { useState } from "react"
import dynamic from "next/dynamic"
import { Check, Copy, FileText, ChevronDown, ChevronUp } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

// Recharts is lazy-loaded ONLY when the query panel is mounted
const AnswerChart = dynamic(
  () => import("@/components/answer-chart").then((mod) => mod.AnswerChart),
  { ssr: false, loading: () => <div className="h-[220px] animate-pulse bg-muted/40" /> }
)

interface QueryPanelProps {
  sql?: string | null
  rows?: Record<string, string | number>[]
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

export function QueryPanel({
  sql,
  rows = [],
  sources = [],
  runId,
  onToast,
}: QueryPanelProps) {
  const [copiedSql, setCopiedSql] = useState(false)
  const [copiedTsv, setCopiedTsv] = useState(false)
  const [showAllRows, setShowAllRows] = useState(false)

  const columns = rows.length > 0 ? Object.keys(rows[0]) : []
  const visibleRows = showAllRows ? rows : rows.slice(0, 10)
  const hasMoreRows = rows.length > 10

  async function handleCopySql() {
    if (!sql) return
    try {
      await navigator.clipboard.writeText(sql)
      setCopiedSql(true)
      setTimeout(() => setCopiedSql(false), 2000)
    } catch {
      onToast?.("Couldn't copy SQL to clipboard")
    }
  }

  async function handleCopyTsv() {
    if (rows.length === 0) return
    try {
      const headers = columns.join("\t")
      const body = rows.map((r) => columns.map((col) => String(r[col] ?? "")).join("\t")).join("\n")
      const tsv = `${headers}\n${body}`
      await navigator.clipboard.writeText(tsv)
      setCopiedTsv(true)
      setTimeout(() => setCopiedTsv(false), 2000)
    } catch {
      onToast?.("Couldn't copy table data")
    }
  }

  const hasChartableData = rows.length >= 2

  return (
    <div className="mt-3 flex flex-col gap-4 border border-border bg-card p-4 text-xs transition-all">
      {/* 1. Read-only SQL */}
      {sql ? (
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              Generated SQL
            </span>
            <button
              type="button"
              onClick={handleCopySql}
              aria-label="Copy SQL"
              className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            >
              {copiedSql ? (
                <>
                  <Check className="h-3 w-3 text-ok" />
                  <span className="text-ok">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" />
                  <span>Copy SQL</span>
                </>
              )}
            </button>
          </div>
          <pre className="overflow-x-auto border border-border bg-muted/30 p-3 font-mono text-[12px] leading-relaxed text-foreground/90 whitespace-pre-wrap select-all">
            <HighlightedSql sql={sql} />
          </pre>
        </div>
      ) : null}

      {/* 2. Result Table */}
      {rows.length > 0 ? (
        <div className="flex flex-col gap-1.5">
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
                    const isNum = sample !== undefined && !Number.isNaN(Number(sample))
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
                  <TableRow key={index} className="border-b border-border/60 hover:bg-muted/20">
                    {columns.map((col) => {
                      const val = row[col]
                      const num = Number(val)
                      const isNum = val !== undefined && val !== "" && !Number.isNaN(num)
                      const display =
                        isNum && typeof val === "number"
                          ? num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                          : String(val ?? "")
                      return (
                        <TableCell
                          key={col}
                          className={`px-3 py-1.5 text-[12px] tabular-nums ${
                            isNum ? "text-right font-mono" : "text-left text-foreground/90"
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
        </div>
      ) : null}

      {/* 3. Lazy Recharts Bar Chart (when 2+ rows with numeric data) */}
      {hasChartableData ? (
        <div className="flex flex-col gap-1.5 border-t border-border/60 pt-3">
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
            Distribution
          </span>
          <AnswerChart rows={rows} />
        </div>
      ) : null}

      {/* 4. Document Source Chips (if source events exist) */}
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

