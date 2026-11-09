"use client"

import { useState } from "react"
import dynamic from "next/dynamic"
import {
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react"
import { StatusBadge, type AnswerBadge } from "./status-badge"
import type { TraceStep } from "@/lib/api"

const QueryPanel = dynamic(
  () => import("./query-panel").then((mod) => mod.QueryPanel),
  { ssr: false }
)

interface AuditBarProps {
  badge?: AnswerBadge
  sql?: string | null
  rowCount?: number | null
  rows?: Record<string, string | number>[]
  steps?: TraceStep[]
  untraced?: string[]
  missingMeasure?: string
  sources?: { document: string; page?: number | string }[]
  runId?: number | null
  feedback?: "up" | "down"
  answerText: string
  onFeedback: (runId: number, rating: "up" | "down", reason?: string) => Promise<boolean>
  onToast: (message: string) => void
}

export function AuditBar({
  badge,
  sql,
  rowCount,
  rows = [],
  steps,
  untraced,
  missingMeasure,
  sources,
  runId,
  feedback,
  answerText,
  onFeedback,
  onToast,
}: AuditBarProps) {
  const [open, setOpen] = useState(false)
  const [copiedAnswer, setCopiedAnswer] = useState(false)
  const [downReasonOpen, setDownReasonOpen] = useState(false)
  const [downReason, setDownReason] = useState("")
  const [submittingReason, setSubmittingReason] = useState(false)

  const activeSteps = (steps || []).filter((s) => s.tool !== "checker")
  const hasDetail = activeSteps.length > 0 || Boolean(sql) || rows.length > 0
  const finalRowCount = rowCount ?? (rows.length > 0 ? rows.length : null)

  async function handleCopyAnswer() {
    try {
      await navigator.clipboard.writeText(answerText)
      setCopiedAnswer(true)
      setTimeout(() => setCopiedAnswer(false), 2000)
    } catch {
      onToast("Couldn't copy answer to clipboard")
    }
  }

  async function handleVote(rating: "up" | "down") {
    if (!runId) return
    if (rating === "down") {
      setDownReasonOpen(true)
    }
    const success = await onFeedback(runId, rating)
    if (!success) {
      onToast("Couldn't save rating")
    }
  }

  async function handleReasonSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!runId || !downReason.trim()) return
    setSubmittingReason(true)
    const success = await onFeedback(runId, "down", downReason.trim())
    setSubmittingReason(false)
    if (success) {
      setDownReasonOpen(false)
    } else {
      onToast("Couldn't save rating")
    }
  }

  return (
    <div className="mt-3 flex flex-col gap-1 border-t border-border/40 pt-2.5 text-xs text-muted-foreground">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* Left side: Query toggle + row count chip + status badge */}
        <div className="flex flex-wrap items-center gap-2.5">
          {hasDetail ? (
            <button
              type="button"
              onClick={() => setOpen((prev) => !prev)}
              aria-expanded={open}
              className="inline-flex items-center gap-1 font-medium text-foreground/80 hover:text-foreground transition-colors"
            >
              <span>{open ? "Hide tool execution" : "Show tool execution"}</span>
              {open ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </button>
          ) : null}

          {finalRowCount != null ? (
            <span className="font-mono text-[11px] tabular-nums text-muted-foreground bg-muted/50 px-1.5 py-0.5 border border-border/40">
              {finalRowCount} {finalRowCount === 1 ? "row" : "rows"}
            </span>
          ) : null}

          <StatusBadge
            badge={badge}
            untraced={untraced}
            missingMeasure={missingMeasure}
          />
        </div>

        {/* Right side: Thumbs Up, Thumbs Down, Copy */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleCopyAnswer}
            aria-label="Copy answer to clipboard"
            className="p-1 hover:text-foreground transition-colors rounded"
            title="Copy answer"
          >
            {copiedAnswer ? (
              <Check className="h-3.5 w-3.5 text-ok" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>

          <button
            type="button"
            disabled={runId == null}
            onClick={() => handleVote("up")}
            aria-label="Thumbs up rating"
            aria-pressed={feedback === "up"}
            className={`p-1 transition-colors rounded ${
              runId == null
                ? "opacity-30 cursor-not-allowed"
                : feedback === "up"
                ? "text-foreground font-semibold"
                : "hover:text-foreground"
            }`}
            title={runId == null ? "Feedback unavailable" : "Accurate and helpful"}
          >
            <ThumbsUp
              className={`h-3.5 w-3.5 ${feedback === "up" ? "fill-current" : ""}`}
            />
          </button>

          <button
            type="button"
            disabled={runId == null}
            onClick={() => handleVote("down")}
            aria-label="Thumbs down rating"
            aria-pressed={feedback === "down"}
            className={`p-1 transition-colors rounded ${
              runId == null
                ? "opacity-30 cursor-not-allowed"
                : feedback === "down"
                ? "text-foreground font-semibold"
                : "hover:text-foreground"
            }`}
            title={runId == null ? "Feedback unavailable" : "Inaccurate or issues with query"}
          >
            <ThumbsDown
              className={`h-3.5 w-3.5 ${feedback === "down" ? "fill-current" : ""}`}
            />
          </button>
        </div>
      </div>

      {/* Optional one-line feedback reason input if thumbs down clicked */}
      {downReasonOpen ? (
        <form
          onSubmit={handleReasonSubmit}
          className="mt-2 flex items-center gap-2 border border-border bg-card p-2"
        >
          <input
            type="text"
            value={downReason}
            onChange={(e) => setDownReason(e.target.value)}
            placeholder="Optional: what was inaccurate or ungrounded?"
            className="flex-1 bg-transparent text-xs text-foreground placeholder:text-muted-foreground outline-none"
            autoFocus
          />
          <button
            type="submit"
            disabled={submittingReason || !downReason.trim()}
            className="text-[11px] font-medium text-foreground hover:text-primary disabled:opacity-40 transition-colors"
          >
            {submittingReason ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            onClick={() => setDownReasonOpen(false)}
            className="text-[11px] text-muted-foreground hover:text-foreground"
          >
            Dismiss
          </button>
        </form>
      ) : null}

      {/* Expanded inline query inspection panel */}
      {open ? (
        <QueryPanel
          sql={sql}
          rows={rows}
          steps={activeSteps}
          sources={sources}
          runId={runId}
          onToast={onToast}
        />
      ) : null}
    </div>
  )
}

