"use client"

/**
 * schema-architect-card.tsx
 *
 * Schema Architect in-chat message. Renders through the same MessageItem layout as Nexus:
 * - Small "Nexus" label
 * - Live step list (AgentSteps) while profiling
 * - Collapsible summary once proposal arrives
 * - Compact, editable inline proposal card adhering strictly to Nexus Design Language:
 *   - JetBrains Mono, hairline 1px borders, --radius: 0, warm stone palette
 *   - Shadcn DropdownMenu for Type and Role selection
 *   - Shadcn ScrollArea with hairline scrollbars
 *   - Shadcn Table, TableHeader, TableRow, TableHead, TableBody, TableCell
 *   - Markdown rendering for table grain (with hairline code badges and clean prose)
 * - Approval / rejection / regeneration controls
 * - Load-progress line during COPY streaming
 * - Immediate transition to Success state on approval with quarantine download link
 * - Deterministic handoff message with clickable question chips
 */

import React, { useCallback, useEffect, useRef, useState } from "react"
import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Download,
  Edit2,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkBreaks from "remark-breaks"
import remarkGfm from "remark-gfm"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { AgentSteps } from "@/components/agent-steps"
import {
  API_URL,
  apiFetch,
  type ColumnProposal,
  type HandoffData,
  type SchemaProposal,
  type UploadMessageData,
  type ValidationResult,
} from "@/lib/api"

// ─────────────────────────────────────────────
// Props
// ─────────────────────────────────────────────

interface SchemaArchitectCardProps {
  data: UploadMessageData
  /** Called when user clicks Approve; parent updates message state */
  onApprove?: (uploadId: string) => Promise<any>
  /** Called when user clicks Reject; parent updates message state */
  onReject?: (uploadId: string) => Promise<void>
  /** Called when a suggestion chip is clicked */
  onAsk?: (question: string) => void
  /** True when a chat turn is in progress (composer note) */
  chatBusy?: boolean
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

function useDebounce<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return debounced
}

function safeText(v: unknown, maxLen = 80): string {
  if (v === null || v === undefined) return ""
  const s = String(v)
  return s.length > maxLen ? s.slice(0, maxLen) + "…" : s
}

function cleanGrainText(raw: string): string {
  if (!raw) return ""
  return raw
    .replace(/^[\s*#_-]*(?:grain|table grain|one row represents)[\s*#_:-]*/i, "")
    .trim()
}

// Build collapsed summary from steps
function buildStepSummary(steps: { tool: string; status: string }[]): string {
  const done = steps.filter((s) => s.status === "done" || s.status === "running")
  const cols = done.filter((s) => s.tool === "profile_column" || s.tool === "profile_columns").length
  const checks = done.length
  if (cols > 0) return `Inspected ${cols} column${cols !== 1 ? "s" : ""} · ${checks} check${checks !== 1 ? "s" : ""}`
  return `${checks} check${checks !== 1 ? "s" : ""} complete`
}

// ─────────────────────────────────────────────
// Grain Markdown Section (Readable & Editable)
// ─────────────────────────────────────────────

interface GrainSectionProps {
  grain: string
  onChange: (val: string) => void
}

function GrainSection({ grain, onChange }: GrainSectionProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [draft, setDraft] = useState(grain)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setDraft(grain)
  }, [grain])

  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus()
    }
  }, [isEditing])

  const handleCommit = () => {
    setIsEditing(false)
    if (draft.trim() !== grain.trim()) {
      onChange(draft.trim())
    }
  }

  const cleaned = cleanGrainText(grain)

  return (
    <div className="space-y-1.5 border border-border bg-background/50 p-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground select-none">
          One row represents
        </span>
        <button
          type="button"
          onClick={() => {
            if (isEditing) handleCommit()
            else setIsEditing(true)
          }}
          className="inline-flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        >
          {isEditing ? (
            <>
              <Check className="h-3 w-3 text-ok" />
              <span>Done</span>
            </>
          ) : (
            <>
              <Edit2 className="h-2.5 w-2.5" />
              <span>Edit</span>
            </>
          )}
        </button>
      </div>

      {isEditing ? (
        <input
          ref={inputRef}
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleCommit()
            if (e.key === "Escape") {
              setDraft(grain)
              setIsEditing(false)
            }
          }}
          onBlur={handleCommit}
          className="w-full border border-border bg-background px-2.5 py-1.5 text-[13px] font-mono text-foreground focus:outline-none focus:border-foreground"
          placeholder="e.g. One row per store sale transaction"
        />
      ) : (
        <div
          onClick={() => setIsEditing(true)}
          className="cursor-pointer text-[13px] leading-relaxed text-foreground"
          title="Click to edit grain description"
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkBreaks]}
            components={{
              code: ({ children }) => (
                <code className="font-mono text-[11px] bg-muted px-1.5 py-0.5 border border-border font-medium text-foreground">
                  {children}
                </code>
              ),
              p: ({ children }) => <p className="m-0 text-foreground">{children}</p>,
              strong: ({ children }) => (
                <strong className="font-semibold text-foreground">{children}</strong>
              ),
            }}
          >
            {cleaned || "One row per transaction record"}
          </ReactMarkdown>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────
// Column row (editable with Shadcn DropdownMenu)
// ─────────────────────────────────────────────

interface ColRowProps {
  col: ColumnProposal
  idx: number
  onChange: (idx: number, patch: Partial<ColumnProposal>) => void
}

const TYPE_OPTIONS: ColumnProposal["type"][] = ["text", "integer", "numeric", "date", "boolean"]
const ROLE_OPTIONS: ColumnProposal["role"][] = ["identifier", "measure", "dimension", "date", "other"]

function ColRow({ col, idx, onChange }: ColRowProps) {
  const [expanded, setExpanded] = useState(false)
  const isExcluded = Boolean(col.excluded)

  return (
    <>
      <TableRow
        className={`text-[11px] font-mono border-b border-border transition-colors ${
          isExcluded ? "opacity-35 bg-muted/20" : "hover:bg-muted/10"
        }`}
      >
        {/* Include toggle */}
        <TableCell className="p-2 text-center w-10">
          <input
            type="checkbox"
            checked={!isExcluded}
            onChange={(e) => onChange(idx, { excluded: !e.target.checked })}
            className="cursor-pointer accent-foreground"
            aria-label={`Include ${col.source_name}`}
          />
        </TableCell>

        {/* Target name */}
        <TableCell className="p-2">
          <input
            type="text"
            disabled={isExcluded}
            value={col.column_name}
            onChange={(e) =>
              onChange(idx, {
                column_name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"),
              })
            }
            onKeyDown={(e) => {
              if (e.key === "Escape") (e.target as HTMLInputElement).blur()
            }}
            className="w-32 border border-border bg-background px-2 py-0.5 text-[11px] font-mono text-foreground focus:outline-none focus:border-foreground disabled:opacity-40"
            aria-label="Target column name"
          />
        </TableCell>

        {/* Type with Shadcn DropdownMenu */}
        <TableCell className="p-2">
          <DropdownMenu>
            <DropdownMenuTrigger
              disabled={isExcluded}
              className="inline-flex items-center justify-between h-6 px-2 text-[11px] font-mono border border-border bg-background hover:bg-muted/40 transition-colors focus:outline-none focus:border-foreground disabled:opacity-40 w-24 cursor-pointer"
              aria-label="Column type"
            >
              <span>{col.type}</span>
              <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0 ml-1" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="min-w-28 font-mono text-[11px] bg-popover border border-border p-1 shadow-sm">
              {TYPE_OPTIONS.map((t) => (
                <DropdownMenuItem
                  key={t}
                  onClick={() => onChange(idx, { type: t })}
                  className="flex items-center justify-between cursor-pointer py-1 px-2 text-[11px] hover:bg-accent"
                >
                  <span>{t}</span>
                  {col.type === t && <Check className="h-3 w-3 text-foreground" />}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>

        {/* Role with Shadcn DropdownMenu */}
        <TableCell className="p-2">
          <DropdownMenu>
            <DropdownMenuTrigger
              disabled={isExcluded}
              className="inline-flex items-center justify-between h-6 px-2 text-[11px] font-mono border border-border bg-background hover:bg-muted/40 transition-colors focus:outline-none focus:border-foreground disabled:opacity-40 w-28 cursor-pointer"
              aria-label="Column role"
            >
              <span>{col.role}</span>
              <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0 ml-1" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="min-w-32 font-mono text-[11px] bg-popover border border-border p-1 shadow-sm">
              {ROLE_OPTIONS.map((r) => (
                <DropdownMenuItem
                  key={r}
                  onClick={() => onChange(idx, { role: r })}
                  className="flex items-center justify-between cursor-pointer py-1 px-2 text-[11px] hover:bg-accent"
                >
                  <span>{r}</span>
                  {col.role === r && <Check className="h-3 w-3 text-foreground" />}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>

        {/* Parse rate */}
        <TableCell className="p-2 text-right tabular-nums">
          <Badge
            variant={col.parse_success_rate < 0.95 ? "destructive" : "outline"}
            className="text-[10px] font-mono tabular-nums px-1.5 py-0 h-4 border-border font-normal"
          >
            {Math.round(col.parse_success_rate * 100)}%
          </Badge>
        </TableCell>

        {/* Expand details toggle */}
        <TableCell className="p-2 text-center w-8">
          <button
            type="button"
            onClick={() => setExpanded((p) => !p)}
            className="text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            aria-expanded={expanded}
            aria-label="Show column details"
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        </TableCell>
      </TableRow>

      {/* Expanded details row */}
      {expanded && (
        <TableRow className={`bg-muted/10 border-b border-border ${isExcluded ? "opacity-35" : ""}`}>
          <TableCell colSpan={6} className="px-3 py-2 text-[11px] font-mono text-muted-foreground space-y-1">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span>
                <span className="text-foreground/60 mr-1">source:</span>
                <span className="text-foreground font-medium">{col.source_name}</span>
              </span>
              <span>
                <span className="text-foreground/60 mr-1">nulls:</span>
                {col.nullable ? "nullable" : "not null"}
              </span>
              <span>
                <span className="text-foreground/60 mr-1">confidence:</span>
                <span className="tabular-nums">{Math.round(col.confidence * 100)}%</span>
              </span>
              {col.date_format && (
                <span>
                  <span className="text-foreground/60 mr-1">format:</span>
                  <code className="text-foreground bg-muted px-1 border border-border">{col.date_format}</code>
                </span>
              )}
            </div>
            {col.description && (
              <div>
                <span className="text-foreground/60 mr-1">desc:</span>
                <span>{safeText(col.description, 120)}</span>
              </div>
            )}
            {col.notes && (
              <div className="text-muted-foreground/70 italic">
                {safeText(col.notes, 120)}
              </div>
            )}
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

// ─────────────────────────────────────────────
// Handoff Message
// ─────────────────────────────────────────────

function HandoffMessage({ handoff, onAsk }: { handoff: HandoffData; onAsk?: (q: string) => void }) {
  const cleanGrain = cleanGrainText(handoff.grain)
  let displayLabel = handoff.tableLabel || handoff.tableName
  if (/^[0-9a-fA-F]{12,}$/.test(displayLabel) || /^ds_\d+$/i.test(displayLabel)) {
    displayLabel = handoff.tableLabel && !/^[0-9a-fA-F]{12,}$/.test(handoff.tableLabel) ? handoff.tableLabel : "Dataset"
  }

  return (
    <div className="mt-6 w-full text-[15px] leading-relaxed text-foreground">
      <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground block mb-2 select-none">
        Nexus
      </span>
      <p className="mb-3">
        I&apos;ve loaded{" "}
        <strong className="font-medium text-foreground">{displayLabel}</strong>{" "}
        (one row = {cleanGrain || "transaction record"},{" "}
        <span className="tabular-nums font-mono">{Number(handoff.rowCount).toLocaleString()}</span> rows
        {handoff.quarantinedCount > 0
          ? `, ${Number(handoff.quarantinedCount).toLocaleString()} quarantined`
          : ""}
        ). Here&apos;s what you can ask:
      </p>
      {handoff.suggestedQuestions.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-3">
          {handoff.suggestedQuestions.map((sq) => (
            <button
              key={sq.question}
              type="button"
              onClick={() => onAsk?.(sq.question)}
              className="border border-border bg-card px-3 py-1.5 text-[13px] text-foreground hover:bg-muted/40 hover:border-foreground/40 transition-colors text-left focus:outline-none focus-visible:ring-1 focus-visible:ring-foreground cursor-pointer"
            >
              {sq.question}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────
// Main SchemaArchitectCard
// ─────────────────────────────────────────────

export function SchemaArchitectCard({
  data,
  onApprove,
  onReject,
  onAsk,
  chatBusy,
}: SchemaArchitectCardProps) {
  const [proposal, setProposal] = useState<SchemaProposal | undefined>(data.proposal)
  const [validation, setValidation] = useState<ValidationResult | undefined>(data.validation)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [hintOpen, setHintOpen] = useState(false)
  const [hint, setHint] = useState("")
  const [regenCount, setRegenCount] = useState(0)
  const [isApproving, setIsApproving] = useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [loadPct, setLoadPct] = useState<number | null>(data.loadProgressPct ?? null)

  // Local immediate state transition on approval
  const [localStatus, setLocalStatus] = useState<string | null>(null)
  const [loadedInfo, setLoadedInfo] = useState<{
    tableName?: string
    loadedRows?: number
    quarantinedRows?: number
  } | null>(null)

  // Debounced proposal for server sync
  const debouncedProposal = useDebounce(proposal, 500)
  const uploadId = data.uploadId

  // Sync when incoming data updates
  useEffect(() => {
    if (data.proposal) setProposal(data.proposal)
    if (data.validation) setValidation(data.validation)
    if (data.loadProgressPct != null) setLoadPct(data.loadProgressPct)
  }, [data.proposal, data.validation, data.loadProgressPct])

  // Server sync on proposal edits
  const isMounted = useRef(true)
  useEffect(() => {
    return () => {
      isMounted.current = false
    }
  }, [])

  useEffect(() => {
    if (!debouncedProposal || !uploadId) return
    fetch(`${API_URL}/uploads/${uploadId}/schema`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(debouncedProposal),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((body) => {
        if (body?.validation && isMounted.current) setValidation(body.validation)
      })
      .catch(() => {})
  }, [debouncedProposal, uploadId])

  // Derived state with local override
  const status = localStatus || data.status
  const isLoaded = status === "loaded"
  const isRejected = status === "rejected"
  const isReview = !isLoaded && (status === "needs_schema_review" || Boolean(proposal))
  const isWorking = !isLoaded && (status === "uploading" || status === "profiling")

  const loadedRows = loadedInfo?.loadedRows ?? data.loadedRows ?? 0
  const quarantinedRows = loadedInfo?.quarantinedRows ?? data.quarantinedRows ?? 0

  const hasErrors = Boolean(validation?.errors?.length)
  const architectSteps = data.architectSteps ?? []
  const stepsCollapsed = !isWorking && architectSteps.length > 0 && (isReview || isLoaded || isRejected)
  const stepSummary = stepsCollapsed ? buildStepSummary(architectSteps) : undefined

  const handleColumnChange = useCallback((idx: number, patch: Partial<ColumnProposal>) => {
    setProposal((prev) => {
      if (!prev) return prev
      const cols = [...prev.columns]
      cols[idx] = { ...cols[idx], ...patch }
      return { ...prev, columns: cols }
    })
  }, [])

  const handleGrainChange = useCallback((val: string) => {
    setProposal((prev) => (prev ? { ...prev, grain: val } : prev))
  }, [])

  async function handleApproveClick() {
    if (!uploadId) return
    setIsApproving(true)
    setActionError(null)
    try {
      let resData: any = null
      if (onApprove) {
        resData = await onApprove(uploadId)
      } else {
        const res = await apiFetch(`${API_URL}/uploads/${uploadId}/schema/approve`, { method: "POST" })
        if (!res.ok) {
          const e = await res.json().catch(() => ({}))
          throw new Error(e?.detail?.message || e?.detail || "Approval failed.")
        }
        resData = await res.json()
      }

      setLocalStatus("loaded")
      if (resData) {
        setLoadedInfo({
          tableName: resData.table_name,
          loadedRows: resData.loaded_rows,
          quarantinedRows: resData.quarantined_rows,
        })
      }
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Error creating table.")
    } finally {
      setIsApproving(false)
    }
  }

  async function handleRejectClick() {
    if (!uploadId) return
    setActionError(null)
    try {
      if (onReject) {
        await onReject(uploadId)
      } else {
        await apiFetch(`${API_URL}/uploads/${uploadId}/schema/reject`, { method: "POST" })
      }
      setLocalStatus("rejected")
    } catch {
      /* offline */
    }
  }

  async function handleRegenerateClick() {
    if (!uploadId || regenCount >= 3) return
    setIsRegenerating(true)
    setActionError(null)
    try {
      const res = await apiFetch(`${API_URL}/uploads/${uploadId}/schema/regenerate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hint: hint.trim() || null }),
      })
      if (!res.ok) {
        const e = await res.json().catch(() => ({}))
        throw new Error(e?.detail || "Could not regenerate schema.")
      }
      const body = await res.json()
      if (body.proposal) setProposal(body.proposal)
      setRegenCount((c) => c + 1)
      setHint("")
      setHintOpen(false)

      const fresh = await apiFetch(`${API_URL}/uploads/${uploadId}/schema`)
      if (fresh.ok) {
        const fd = await fresh.json()
        if (fd.validation) setValidation(fd.validation)
        if (fd.proposal) setProposal(fd.proposal)
      }
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Error regenerating schema.")
    } finally {
      setIsRegenerating(false)
    }
  }

  // ─── Render ───────────────────────────────

  return (
    <div className="w-full">
      {/* Author label */}
      <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground block mb-1.5 select-none">
        Nexus
      </span>

      {/* ── Live Steps / Summary (Nexus Agent Pattern) ── */}
      {architectSteps.length > 0 && (
        <div className="mb-2">
          <AgentSteps
            steps={architectSteps}
            isStreaming={isWorking}
            collapsedSummary={stepSummary}
          />
        </div>
      )}

      {/* Loading spinner */}
      {isWorking && architectSteps.length === 0 && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground my-2" role="status" aria-live="polite">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
          <span className="motion-safe:animate-pulse">Profiling columns…</span>
        </div>
      )}

      {/* Load progress line */}
      {isApproving && loadPct != null && (
        <div className="text-[12px] font-mono text-muted-foreground my-2 flex items-center gap-2">
          <Loader2 className="h-3 w-3 animate-spin shrink-0" />
          Loading rows… {loadPct}%
        </div>
      )}

      {/* Safety rejection */}
      {isRejected && !proposal && (
        <div role="alert" className="flex items-start gap-2 text-[13px] text-destructive my-2">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{data.error ?? "File rejected."}</span>
        </div>
      )}

      {/* ── Review Card ── */}
      {isReview && proposal && (
        <div className="mt-2 space-y-3 border border-border bg-card p-4">
          {/* Action Error */}
          {actionError && (
            <div role="alert" className="flex items-center gap-2 border border-destructive/40 bg-destructive/10 p-2.5 text-destructive font-mono text-[11px]">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{actionError}</span>
            </div>
          )}

          {/* Schema Memory notice */}
          {proposal.from_cache && (
            <div className="text-[11px] font-mono text-muted-foreground flex items-center gap-1.5 border-b border-border pb-2">
              <Check className="h-3 w-3 text-ok" />
              <span>Matches a previous schema</span>
            </div>
          )}

          {/* Chat-busy note */}
          {chatBusy && (
            <div className="text-[11px] text-muted-foreground font-mono border-b border-border pb-2">
              Approve the schema first so Nexus can answer from it.
            </div>
          )}

          {/* Validation Warnings */}
          {validation?.warnings && validation.warnings.length > 0 && (
            <div className="space-y-1">
              {validation.warnings.map((w, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[12px] font-mono text-warn">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                  <span>{w.message}</span>
                </div>
              ))}
            </div>
          )}

          {/* Validation Errors */}
          {validation?.errors && validation.errors.length > 0 && (
            <div className="space-y-1">
              {validation.errors.map((e, i) => (
                <div key={i} role="alert" className="flex items-center gap-1.5 text-[12px] font-mono text-destructive">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                  <span>{e.message}</span>
                </div>
              ))}
            </div>
          )}

          {/* ─ Grain (Markdown Rendered & Editable) ─ */}
          <GrainSection grain={proposal.grain} onChange={handleGrainChange} />

          {/* ─ Column Table with Shadcn ScrollArea & Table ─ */}
          <div className="border border-border overflow-hidden">
            <ScrollArea className="h-[280px] w-full">
              <Table containerClassName="contents" className="w-full text-left border-collapse text-[11px] font-mono min-w-[500px]">
                <TableHeader className="bg-muted text-muted-foreground sticky top-0 z-10 border-b border-border">
                  <TableRow className="border-b border-border hover:bg-transparent">
                    <TableHead className="p-2 w-10 text-center font-medium" title="Include">Inc</TableHead>
                    <TableHead className="p-2 font-medium">Target name</TableHead>
                    <TableHead className="p-2 font-medium">Type</TableHead>
                    <TableHead className="p-2 font-medium">Role</TableHead>
                    <TableHead className="p-2 text-right font-medium">Parse</TableHead>
                    <TableHead className="p-2 w-8" aria-label="Details"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className="divide-y divide-border bg-card">
                  {proposal.columns.map((col, idx) => (
                    <ColRow key={col.source_name} col={col} idx={idx} onChange={handleColumnChange} />
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          </div>

          {/* ─ Preview 10 rows ─ */}
          {data.preview && data.preview.length > 0 && (
            <div className="border border-border">
              <button
                type="button"
                onClick={() => setPreviewOpen((p) => !p)}
                className="w-full flex items-center justify-between p-2 text-[11px] font-mono text-muted-foreground hover:text-foreground bg-muted/10 transition-colors cursor-pointer"
              >
                <span>Preview 10 rows</span>
                {previewOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </button>
              {previewOpen && (
                <ScrollArea className="h-[140px] w-full border-t border-border bg-background">
                  <Table containerClassName="contents" className="w-full text-left border-collapse text-[10px] font-mono">
                    <TableHeader className="border-b border-border text-muted-foreground bg-muted/30">
                      <TableRow className="border-b border-border hover:bg-transparent">
                        {Object.keys(data.preview[0]).map((h) => (
                          <TableHead key={h} className="p-1 font-medium whitespace-nowrap">{h}</TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody className="divide-y divide-border/60">
                      {data.preview.map((row, i) => (
                        <TableRow key={i} className="hover:bg-muted/10">
                          {Object.values(row).map((v, j) => (
                            <TableCell key={j} className="p-1 whitespace-nowrap text-foreground max-w-[140px] truncate" title={safeText(v, 200)}>
                              {safeText(v)}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollArea>
              )}
            </div>
          )}

          {/* ─ Regenerate with hint ─ */}
          <div className="space-y-1.5">
            <button
              type="button"
              onClick={() => setHintOpen((p) => !p)}
              disabled={regenCount >= 3}
              className="text-[12px] font-mono text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40 outline-none focus-visible:underline cursor-pointer"
            >
              Regenerate with a hint {regenCount < 3 ? `(${3 - regenCount} remaining)` : "(limit reached)"}
            </button>
            {hintOpen && regenCount < 3 && (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={hint}
                  maxLength={200}
                  onChange={(e) => setHint(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleRegenerateClick() }}
                  placeholder="e.g. grain is store-month, revenue column is sales"
                  className="flex-1 border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:border-foreground"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={isRegenerating}
                  onClick={handleRegenerateClick}
                  className="h-7 text-xs gap-1 font-mono cursor-pointer"
                >
                  {isRegenerating ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                  <span>Regenerate</span>
                </Button>
              </div>
            )}
          </div>

          {/* ─ Approve / Reject Controls ─ */}
          <div className="flex items-center justify-between pt-2 border-t border-border gap-3">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleRejectClick}
              disabled={isApproving}
              className="text-destructive hover:bg-destructive/10 text-xs gap-1 h-8 cursor-pointer"
            >
              <X className="h-3.5 w-3.5" />
              <span>Reject</span>
            </Button>

            <div className="flex items-center gap-2">
              {hasErrors && (
                <span className="text-[11px] font-mono text-destructive" role="alert">
                  Fix {validation!.errors.length} error{validation!.errors.length !== 1 ? "s" : ""} to approve
                </span>
              )}
              <Button
                type="button"
                size="sm"
                disabled={isApproving || hasErrors}
                onClick={handleApproveClick}
                aria-disabled={hasErrors}
                aria-describedby={hasErrors ? "approve-blocked-reason" : undefined}
                className="h-8 px-4 text-xs font-semibold gap-1.5 bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 cursor-pointer"
              >
                {isApproving ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Creating table…</span>
                  </>
                ) : (
                  <>
                    <Check className="h-3.5 w-3.5 stroke-[2.5]" />
                    <span>Approve &amp; create table</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Success State ── */}
      {isLoaded && (
        <div className="mt-3 flex items-center justify-between gap-3 text-[13px] text-muted-foreground font-mono border-t border-border pt-3">
          <span className="flex items-center gap-2 text-ok">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            <span className="text-foreground font-medium">
              Table created · {Number(loadedRows).toLocaleString()} rows loaded
              {quarantinedRows > 0 ? ` · ${Number(quarantinedRows).toLocaleString()} quarantined` : ""}
            </span>
          </span>
          {quarantinedRows > 0 && uploadId && (
            <a
              href={`${API_URL}/uploads/${uploadId}/health?download=1`}
              className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors underline underline-offset-2"
              target="_blank"
              rel="noreferrer"
            >
              <Download className="h-3 w-3" />
              Download quarantine
            </a>
          )}
        </div>
      )}

      {/* ── Rejected State ── */}
      {isRejected && proposal && (
        <div className="mt-2 text-[13px] font-mono text-muted-foreground">
          Rejected · no table created
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────
// Export HandoffMessage
// ─────────────────────────────────────────────

export { HandoffMessage }
