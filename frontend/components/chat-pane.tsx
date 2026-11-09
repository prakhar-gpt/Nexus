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
import type { AnswerBadge } from "@/components/status-badge"
import type { HandoffData, TraceStep, UploadMessageData } from "@/lib/api"

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
  runId?: number | null
  rows?: Record<string, string | number>[]
  activity?: TraceStep[]
  steps?: TraceStep[]
  untraced?: string[]
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
  onFeedback: (runId: number, rating: "up" | "down", reason?: string) => Promise<boolean>
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
  onFeedback: (runId: number, rating: "up" | "down", reason?: string) => Promise<boolean>
  onToast: (message: string) => void
  onApproveSchema?: (uploadId: string) => Promise<void>
  onRejectSchema?: (uploadId: string) => Promise<void>
  onAsk?: (question: string) => void
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
          <RenderedMarkdown text={message.text} />
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

const RenderedMarkdown = memo(function RenderedMarkdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      components={{
        p: ({ children }) => <p className="mb-3.5 last:mb-0">{children}</p>,
        ul: ({ children }) => (
          <ul className="mb-3.5 list-disc pl-5 space-y-1 last:mb-0">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="mb-3.5 list-decimal pl-5 space-y-1 last:mb-0">{children}</ol>
        ),
        li: ({ children }) => <li className="my-0.5">{children}</li>,
        strong: ({ children }) => (
          <strong className="font-medium text-foreground">{children}</strong>
        ),
        em: ({ children }) => <em className="italic">{children}</em>,
        h1: ({ children }) => (
          <h2 className="mb-2 text-lg font-medium text-foreground tracking-tight">
            {children}
          </h2>
        ),
        h2: ({ children }) => (
          <h3 className="mb-2 text-base font-medium text-foreground tracking-tight">
            {children}
          </h3>
        ),
        h3: ({ children }) => (
          <h4 className="mb-1.5 text-sm font-medium text-foreground">{children}</h4>
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
                {children}
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
              className={`border-b border-border/60 px-3 py-1.5 align-top ${
                isNumeric ? "text-right font-mono" : "text-left"
              }`}
            >
              {children}
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
