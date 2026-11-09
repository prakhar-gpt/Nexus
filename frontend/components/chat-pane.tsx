"use client"

import React, {
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
  memo,
} from "react"
import dynamic from "next/dynamic"
import { ArrowDown, ArrowUpRight, AlertCircle, RefreshCw, X } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkBreaks from "remark-breaks"
import remarkGfm from "remark-gfm"

import { ToolLine } from "@/components/tool-line"
import { AuditBar } from "@/components/audit-bar"
import { Composer, type ComposerHandle } from "@/components/composer"
import { HandoffMessage } from "@/components/schema-architect-card"

const SchemaArchitectCard = dynamic(
  () => import("@/components/schema-architect-card").then((m) => m.SchemaArchitectCard),
  { ssr: false }
)
const SourcePanel = dynamic(
  () => import("@/components/source-panel").then((m) => m.SourcePanel),
  { ssr: false }
)
import type { AnswerBadge } from "@/components/status-badge"
import type { ClaimProvenanceItem, HandoffData, TraceStep, UploadMessageData } from "@/lib/api"

export type { AnswerBadge }

export type ChatMessage = {
  id: string
  role: "user" | "assistant"
  text: string
  uploadData?: UploadMessageData
  /** Set on handoff messages (kind = "handoff") */
  handoffData?: HandoffData
  badge?: AnswerBadge
  sql?: string | null
  rowCount?: number | null
  runId?: string | number | null
  rows?: Record<string, string | number>[]
  activity?: TraceStep[]
  steps?: TraceStep[]
  untraced?: string[]
  provenance?: ClaimProvenanceItem[]
  queries?: any[]
  missingMeasure?: string
  sources?: { document: string; page?: number | string }[]
  feedback?: "up" | "down"
  feedbackReason?: string
  error?: string | null
  streamDropped?: boolean
  isFirstInRun?: boolean
}

export const DEFAULT_SUGGESTIONS = [
  "What is total revenue by category?",
  "Top 10 customers by revenue",
  "Which sub-categories generate the highest sales?",
  "Monthly sales trend for 2017",
] as const

interface ChatPaneProps {
  draft: string
  messages: ChatMessage[]
  busy: boolean
  uploadPending?: boolean
  datasetName?: string
  suggestions?: readonly string[]
  onDraft: (value: string) => void
  onAsk: (question: string) => void
  onAbort?: () => void
  onRetry?: (messageId: string) => void
  onFeedback: (runId: string | number, rating: "up" | "down", reason?: string) => Promise<boolean>
  onToast: (message: string) => void
  onUploadFile?: (file: File) => void
  onApproveSchema?: (uploadId: string) => Promise<void>
  onRejectSchema?: (uploadId: string) => Promise<void>
}

export function ChatPane({
  draft,
  messages,
  busy,
  uploadPending,
  datasetName = "Superstore",
  suggestions = DEFAULT_SUGGESTIONS,
  onDraft,
  onAsk,
  onAbort,
  onRetry,
  onFeedback,
  onToast,
  onUploadFile,
  onApproveSchema,
  onRejectSchema,
}: ChatPaneProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const composerRef = useRef<ComposerHandle>(null)
  const [showScrollBottom, setShowScrollBottom] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)
  const isNearBottomRef = useRef(true)

  // Source panel inspection state
  const [selectedClaim, setSelectedClaim] = useState<ClaimProvenanceItem | null>(null)
  const [selectedClaimIndex, setSelectedClaimIndex] = useState<number | null>(null)
  const [selectedRunId, setSelectedRunId] = useState<string | number | null>(null)
  const [sourcePanelOpen, setSourcePanelOpen] = useState(false)
  const lastTriggerRef = useRef<HTMLElement | null>(null)

  const handleSelectClaim = useCallback(
    (claim: ClaimProvenanceItem, runId: string | number | null, e?: React.MouseEvent<HTMLElement>, claimIndex?: number) => {
      if (e?.currentTarget) {
        lastTriggerRef.current = e.currentTarget
      }
      setSelectedClaim(claim)
      setSelectedClaimIndex(claimIndex ?? null)
      setSelectedRunId(runId)
      setSourcePanelOpen(true)
    },
    []
  )

  const lastUserQuestion = useMemo(
    () => [...messages].reverse().find((m) => m.role === "user")?.text,
    [messages]
  )

  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    const isNear = distanceFromBottom <= 80
    isNearBottomRef.current = isNear
    if (isNear && showScrollBottom) {
      setShowScrollBottom(false)
    }
  }, [showScrollBottom])

  const scrollToBottom = useCallback(() => {
    const el = scrollContainerRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
    setShowScrollBottom(false)
  }, [])

  useEffect(() => {
    const el = scrollContainerRef.current
    if (!el) return
    const id = requestAnimationFrame(() => {
      if (isNearBottomRef.current) {
        el.scrollTop = el.scrollHeight
      } else if (busy) {
        setShowScrollBottom(true)
      }
    })
    return () => cancelAnimationFrame(id)
  }, [messages, busy])

  function handleFileDrop(file: File) {
    setFileError(null)
    const name = file.name.toLowerCase()
    if (!name.endsWith(".csv") && !name.endsWith(".xlsx")) {
      setFileError("Only .csv and .xlsx files are accepted.")
      return
    }
    if (onUploadFile) onUploadFile(file)
  }

  return (
    <section className="relative flex h-full min-h-0 min-w-0 flex-1 flex-col bg-background">
      {/* Full-pane drag overlay */}
      {isDragging && (
        <div
          className="absolute inset-0 z-30 flex items-center justify-center bg-background/80 border-2 border-dashed border-foreground/40 pointer-events-none"
          aria-hidden="true"
        >
          <span className="font-mono text-sm text-foreground/60 select-none">Drop to upload</span>
        </div>
      )}

      {/* Scrollable messages area */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
        onDragLeave={(e) => {
          // Only clear if leaving the scroll container itself, not a child
          if (!e.currentTarget.contains(e.relatedTarget as Node)) setIsDragging(false)
        }}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragging(false)
          const f = e.dataTransfer.files?.[0]
          if (f) handleFileDrop(f)
        }}
        className="flex-1 overflow-y-auto px-4 py-8"
      >
        {/* Inline file error */}
        {fileError && (
          <div
            role="alert"
            className="mx-auto mb-4 w-full max-w-[720px] flex items-center gap-2 text-xs text-destructive border border-destructive/30 bg-destructive/10 p-2"
          >
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span>{fileError}</span>
            <button
              type="button"
              onClick={() => setFileError(null)}
              className="ml-auto text-destructive hover:opacity-80"
              aria-label="Dismiss error"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        )}

        {messages.length === 0 ? (
          /* Empty state */
          <div className="mx-auto flex h-full w-full max-w-[720px] flex-col justify-center py-12">
            <h1 className="text-[32px] font-medium tracking-tight text-foreground select-none">
              What should we look at?
            </h1>

            {/* Suggestion prompts */}
            <div className="mt-8 flex flex-col border-y border-border divide-y divide-border">
              {suggestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => onAsk(question)}
                  className="group flex w-full items-center justify-between py-3.5 text-left text-[15px] text-muted-foreground hover:text-foreground transition-colors outline-none focus-visible:bg-accent/40"
                >
                  <span className="font-normal">{question}</span>
                  <ArrowUpRight className="h-4 w-4 text-muted-foreground/60 group-hover:text-foreground transition-colors shrink-0 ml-2" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Message List */
          <div className="mx-auto flex w-full max-w-[720px] flex-col gap-8 pb-4">
            {messages.map((message, index) => {
              const isFirstInRun =
                message.role === "assistant" &&
                (index === 0 || messages[index - 1]?.role === "user")

              return (
                <div key={message.id} className="w-full [content-visibility:auto] [contain-intrinsic-size:auto_100px]">
                  <MessageItem
                    message={message}
                    isFirstInRun={isFirstInRun}
                    isStreaming={busy && index === messages.length - 1}
                    onRetry={onRetry}
                    onFeedback={onFeedback}
                    onToast={onToast}
                    onApproveSchema={onApproveSchema}
                    onRejectSchema={onRejectSchema}
                    onAsk={onAsk}
                    onSelectClaim={handleSelectClaim}
                    chatBusy={busy}
                    uploadPending={uploadPending}
                  />
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Floating "↓ New content" pill */}
      {showScrollBottom && (
        <div className="absolute bottom-24 left-1/2 -translate-x-1/2 z-20">
          <button
            type="button"
            onClick={scrollToBottom}
            className="flex items-center gap-1.5 border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground shadow-xs hover:bg-accent transition-all cursor-pointer"
          >
            <ArrowDown className="h-3 w-3" />
            <span>New content</span>
          </button>
        </div>
      )}

      {/* Source Provenance Panel */}
      <SourcePanel
        open={sourcePanelOpen}
        onClose={() => setSourcePanelOpen(false)}
        runId={selectedRunId}
        claim={selectedClaim}
        claimIndex={selectedClaimIndex}
        triggerRef={lastTriggerRef}
      />

      {/* Pinned Composer */}
      <Composer
        ref={composerRef}
        draft={draft}
        busy={busy}
        lastQuestion={lastUserQuestion}
        placeholder={`Ask a question about ${datasetName}…`}
        onDraft={onDraft}
        onAsk={onAsk}
        onAbort={onAbort}
        onUploadFile={onUploadFile ? handleFileDrop : undefined}
      />
    </section>
  )
}

interface MessageItemProps {
  message: ChatMessage
  isFirstInRun?: boolean
  isStreaming: boolean
  onRetry?: (messageId: string) => void
  onFeedback: (runId: string | number, rating: "up" | "down", reason?: string) => Promise<boolean>
  onToast: (message: string) => void
  onApproveSchema?: (uploadId: string) => Promise<void>
  onRejectSchema?: (uploadId: string) => Promise<void>
  onAsk?: (question: string) => void
  onSelectClaim?: (claim: ClaimProvenanceItem, runId: string | number | null, e?: React.MouseEvent<HTMLElement>, claimIndex?: number) => void
  chatBusy?: boolean
  uploadPending?: boolean
}

const MessageItem = memo(function MessageItem({
  message,
  isFirstInRun,
  isStreaming,
  onRetry,
  onFeedback,
  onToast,
  onApproveSchema,
  onRejectSchema,
  onAsk,
  onSelectClaim,
  chatBusy,
}: MessageItemProps) {
  // Architect message
  if (message.uploadData) {
    return (
      <div className="w-full">
        <SchemaArchitectCard
          data={message.uploadData}
          onApprove={onApproveSchema}
          onReject={onRejectSchema}
          onAsk={onAsk}
          chatBusy={chatBusy}
        />
      </div>
    )
  }

  // Deterministic Nexus handoff message
  if (message.handoffData) {
    return (
      <div className="w-full">
        <HandoffMessage handoff={message.handoffData} onAsk={onAsk} />
      </div>
    )
  }

  // User message
  if (message.role === "user") {
    return (
      <div className="flex justify-end w-full">
        <div className="max-w-[80%] bg-primary text-primary-foreground px-4 py-2.5 text-[15px] leading-relaxed">
          {message.text}
        </div>
      </div>
    )
  }

  // Assistant (Nexus) message
  const hasTokens = Boolean(message.text)
  const isComplete = !isStreaming && Boolean(message.badge && message.badge !== "waiting")

  return (
    <div className="w-full text-[16px] leading-[1.65] text-foreground">
      {isFirstInRun ? (
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground block mb-1.5 select-none">
          Nexus
        </span>
      ) : null}

      {!hasTokens ? (
        <ToolLine
          activity={message.activity}
          isWaiting={message.badge === "waiting" || isStreaming}
        />
      ) : null}

      {hasTokens ? (
        <div className="prose-nexus text-[16px] leading-[1.65] text-foreground">
          <RenderedMarkdown
            text={message.text}
            untraced={message.untraced}
            provenance={message.provenance}
            runId={message.runId}
            onSelectClaim={onSelectClaim}
          />
          {isStreaming ? (
            <span
              className="inline-block w-[2px] h-[1em] bg-foreground align-middle animate-pulse ml-0.5"
              aria-hidden="true"
            />
          ) : null}
        </div>
      ) : null}

      {message.streamDropped ? (
        <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
          <span>Connection lost.</span>
          {onRetry ? (
            <button
              type="button"
              onClick={() => onRetry(message.id)}
              className="font-medium text-foreground underline underline-offset-2 hover:opacity-80"
            >
              Retry
            </button>
          ) : null}
        </div>
      ) : null}

      {message.error ? (
        <div
          role="alert"
          className="mt-3 flex items-center justify-between p-2.5 bg-destructive/10 border border-destructive/20 text-xs text-destructive"
        >
          <div className="flex items-center gap-1.5">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span>{message.error}</span>
          </div>
          {onRetry ? (
            <button
              type="button"
              onClick={() => onRetry(message.id)}
              className="inline-flex items-center gap-1 font-medium underline underline-offset-2"
            >
              <RefreshCw className="h-3 w-3" />
              <span>Retry</span>
            </button>
          ) : null}
        </div>
      ) : null}

      {(isComplete || (!isStreaming && (message.sql || (message.rows && message.rows.length > 0) || (message.steps && message.steps.length > 0)))) && (
        <AuditBar
          badge={message.badge}
          sql={message.sql}
          rowCount={message.rowCount}
          rows={message.rows}
          steps={message.steps}
          untraced={message.untraced}
          provenance={message.provenance}
          missingMeasure={message.missingMeasure}
          sources={message.sources}
          runId={message.runId}
          feedback={message.feedback}
          answerText={message.text}
          onFeedback={onFeedback}
          onToast={onToast}
        />
      )}
    </div>
  )
})

function highlightProvenanceText(
  node: React.ReactNode,
  untracedList?: string[],
  provenance?: ClaimProvenanceItem[],
  runId?: string | number | null,
  onSelectClaim?: (claim: ClaimProvenanceItem, runId: string | number | null, e?: React.MouseEvent<HTMLElement>, claimIndex?: number) => void
): React.ReactNode {
  if (typeof node !== "string") {
    return node
  }

  // 1. Matched claims from provenance
  const matchedClaims = (provenance || []).filter((p) => p.status === "matched")
  const matchedMap = new Map<string, ClaimProvenanceItem>()
  for (const p of matchedClaims) {
    if (p.claim && p.claim.trim()) {
      matchedMap.set(p.claim.trim(), p)
    }
  }

  // 2. Untraced tokens
  const untracedTokens = (untracedList || [])
    .map((item) =>
      item
        .replace(/\s*\(stated in your message.*?\)$/i, "")
        .replace(/\s*\(found in a different dataset.*?\)$/i, "")
        .trim()
    )
    .filter(
      (item) =>
        item.length > 0 &&
        !item.toLowerCase().startsWith("not checked") &&
        !item.toLowerCase().startsWith("method claim") &&
        !item.toLowerCase().startsWith("based on a partial")
    )

  if (matchedMap.size === 0 && untracedTokens.length === 0) {
    return node
  }

  // Build combined tokens array, sorted by length descending so longer phrases match first
  const allTokens = [
    ...Array.from(matchedMap.keys()),
    ...untracedTokens,
  ].sort((a, b) => b.length - a.length)

  const escaped = Array.from(new Set(allTokens))
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|")
  if (!escaped) return node

  const regex = new RegExp(`(${escaped})`, "g")
  const parts = node.split(regex)
  if (parts.length <= 1) return node

  return parts.map((part, idx) => {
    const trimmed = part.trim()
    const matchedClaim = matchedMap.get(trimmed) || matchedMap.get(part)
    if (matchedClaim) {
      const claimIndex = (provenance || []).findIndex((item) =>
        item.claim === matchedClaim.claim &&
        item.column === matchedClaim.column &&
        item.query_id === matchedClaim.query_id &&
        item.row_index === matchedClaim.row_index &&
        item.status === matchedClaim.status
      )
      return (
        <button
          key={idx}
          type="button"
          aria-label={`Source of ${part}`}
          onClick={(e) => onSelectClaim?.(matchedClaim, runId ?? null, e, claimIndex >= 0 ? claimIndex : undefined)}
          className="underline decoration-dotted decoration-muted-foreground/70 underline-offset-4 hover:decoration-foreground hover:text-foreground cursor-pointer transition-colors bg-transparent border-0 p-0 font-inherit inline text-inherit focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring tabular-nums"
        >
          {part}
        </button>
      )
    }

    if (untracedTokens.includes(trimmed) || untracedTokens.includes(part)) {
      return (
        <span
          key={idx}
          className="underline decoration-warn/60 decoration-[1.5px] underline-offset-4 bg-warn/10 rounded-none px-0.5 tabular-nums"
          title="Untraced figure: not found in verified tool output"
        >
          {part}
        </span>
      )
    }

    return part
  })
}

function wrapChildrenWithHighlight(
  children: React.ReactNode,
  untracedList?: string[],
  provenance?: ClaimProvenanceItem[],
  runId?: string | number | null,
  onSelectClaim?: (claim: ClaimProvenanceItem, runId: string | number | null, e?: React.MouseEvent<HTMLElement>, claimIndex?: number) => void
): React.ReactNode {
  if ((!untracedList || untracedList.length === 0) && (!provenance || provenance.length === 0)) {
    return children
  }
  return React.Children.map(children, (child) => {
    if (typeof child === "string") {
      return highlightProvenanceText(child, untracedList, provenance, runId, onSelectClaim)
    }
    return child
  })
}

const RenderedMarkdown = memo(function RenderedMarkdown({
  text,
  untraced,
  provenance,
  runId,
  onSelectClaim,
}: {
  text: string
  untraced?: string[]
  provenance?: ClaimProvenanceItem[]
  runId?: string | number | null
  onSelectClaim?: (claim: ClaimProvenanceItem, runId: string | number | null, e?: React.MouseEvent<HTMLElement>, claimIndex?: number) => void
}) {
  const wrap = (children: React.ReactNode) =>
    wrapChildrenWithHighlight(children, untraced, provenance, runId, onSelectClaim)

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      components={{
        p: ({ children }) => <p className="mb-3.5 last:mb-0">{wrap(children)}</p>,
        ul: ({ children }) => (
          <ul className="mb-3.5 list-disc pl-5 space-y-1 last:mb-0">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="mb-3.5 list-decimal pl-5 space-y-1 last:mb-0">{children}</ol>
        ),
        li: ({ children }) => <li className="my-0.5">{wrap(children)}</li>,
        strong: ({ children }) => (
          <strong className="font-medium text-foreground">{wrap(children)}</strong>
        ),
        em: ({ children }) => <em className="italic">{wrap(children)}</em>,
        h1: ({ children }) => (
          <h2 className="mb-2 text-lg font-medium text-foreground tracking-tight">
            {wrap(children)}
          </h2>
        ),
        h2: ({ children }) => (
          <h3 className="mb-2 text-base font-medium text-foreground tracking-tight">
            {wrap(children)}
          </h3>
        ),
        h3: ({ children }) => (
          <h4 className="mb-1.5 text-sm font-medium text-foreground">{wrap(children)}</h4>
        ),
        pre: ({ children }) => (
          <pre className="my-3 overflow-x-auto border border-border bg-muted/30 p-3 font-mono text-[13px] leading-relaxed last:mb-0">
            {children}
          </pre>
        ),
        code: ({ className, children }) => {
          const isInline = !className
          if (isInline) {
            return (
              <code className="font-mono text-[14px] bg-muted/60 px-1 py-0.5 border border-border/40">
                {wrap(children)}
              </code>
            )
          }
          return <code>{children}</code>
        },
        table: ({ children }) => (
          <div className="my-3 overflow-x-auto border border-border last:mb-0">
            <table className="w-full border-collapse text-xs tabular-nums">
              {children}
            </table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border-b border-border bg-muted/40 px-3 py-1.5 text-left font-medium text-foreground">
            {children}
          </th>
        ),
        td: ({ children }) => {
          const content = String(children ?? "")
          const isNumeric = /^\s*[$€£]?\s*[\d,]+(\.\d+)?%?\s*$/.test(content)
          return (
            <td
              className={`border-b border-border/60 px-3 py-1.5 align-top ${isNumeric ? "text-right font-mono" : "text-left"
                }`}
            >
              {wrap(children)}
            </td>
          )
        },
        a: ({ href, children }) => {
          const safe = href && /^https?:\/\//.test(href) ? href : undefined
          return safe ? (
            <a
              href={safe}
              rel="noreferrer"
              target="_blank"
              className="text-foreground underline underline-offset-4 hover:opacity-80"
            >
              {children}
            </a>
          ) : (
            <span>{children}</span>
          )
        },
        img: () => null,
      }}
    >
      {text}
    </ReactMarkdown>
  )
})
