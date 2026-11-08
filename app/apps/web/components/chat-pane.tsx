"use client"

import dynamic from "next/dynamic"
import { useEffect, useRef, useState } from "react"
import { ArrowUp, ThumbsDown, ThumbsUp } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkBreaks from "remark-breaks"
import remarkGfm from "remark-gfm"

import { SUGGESTIONS } from "@/components/suggestions"
import { API_URL, type TraceStep } from "@/lib/api"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const AnswerChart = dynamic(
  () => import("@/components/answer-chart").then((mod) => mod.AnswerChart),
  { ssr: false },
)

export type AnswerBadge = "waiting" | "verified" | "caveat" | "refused" | "unanswered"

export type ChatMessage = {
  id: string
  role: "user" | "assistant"
  text: string
  badge?: AnswerBadge
  sql?: string | null
  rowCount?: number | null
  runId?: number | null
  rows?: Record<string, string>[]
  activity?: TraceStep[]
  feedback?: "up" | "down"
}

const NOTE: Partial<Record<AnswerBadge, string>> = {
  caveat: "A figure in this answer is not in the query result.",
  refused: "This question was refused.",
}

export function ChatPane({
  draft,
  messages,
  busy,
  onDraft,
  onAsk,
  onFeedback,
}: {
  draft: string
  messages: ChatMessage[]
  busy: boolean
  onDraft: (value: string) => void
  onAsk: (question: string) => void
  onFeedback: (runId: number, rating: "up" | "down") => void
}) {
  const threadEnd = useRef<HTMLDivElement>(null)
  useEffect(() => {
    threadEnd.current?.scrollIntoView({ block: "nearest" })
  }, [messages])

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="mx-auto flex h-full w-full max-w-2xl flex-col justify-center px-6">
            <h1 className="text-4xl tracking-tight text-foreground/90">
              What should we look at?
            </h1>
            <div className="mt-8 flex flex-col">
              {SUGGESTIONS.map((question) => (
                <button
                  key={question}
                  type="button"
                  className="border-b border-border py-3 text-left text-[15px] text-muted-foreground transition-colors hover:text-foreground"
                  onClick={() => onAsk(question)}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto flex w-full max-w-2xl flex-col gap-8 px-6 py-10">
            {messages.map((message) =>
              message.role === "user" ? (
                <p
                  key={message.id}
                  className="ml-auto max-w-[34rem] bg-muted px-4 py-2.5 text-[15px] leading-relaxed"
                >
                  {message.text}
                </p>
              ) : (
                <AssistantMessage
                  key={message.id}
                  message={message}
                  onFeedback={onFeedback}
                />
              ),
            )}
            <div ref={threadEnd} />
          </div>
        )}
      </div>
      <form
        className="mx-auto w-full max-w-2xl px-4 pb-5"
        onSubmit={(event) => {
          event.preventDefault()
          if (!busy) {
            onAsk(draft)
          }
        }}
      >
        <div className="flex items-end gap-2 border border-border bg-card px-3 py-2">
          <textarea
            value={draft}
            rows={1}
            placeholder="Ask about this data room"
            aria-label="Question"
            className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-[15px] leading-relaxed outline-none placeholder:text-muted-foreground"
            onChange={(event) => onDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault()
                if (!busy) {
                  onAsk(draft)
                }
              }
            }}
          />
          <Button
            type="submit"
            size="icon"
            className="mb-1"
            disabled={busy || draft.trim().length === 0}
            aria-label="Send"
          >
            <ArrowUp />
          </Button>
        </div>
      </form>
    </section>
  )
}

function AssistantMessage({
  message,
  onFeedback,
}: {
  message: ChatMessage
  onFeedback: (runId: number, rating: "up" | "down") => void
}) {
  const [open, setOpen] = useState(false)
  const rows = message.rows ?? []
  const activity = (message.activity ?? []).filter((step) => step.tool !== "checker")
  const activeStep = activity.length > 0 ? activity[activity.length - 1] : null
  const waiting = message.badge === "waiting" && !message.text && !activeStep
  const note = message.badge ? NOTE[message.badge] : undefined
  const hasDetail = Boolean(message.sql) || rows.length > 0
  return (
    <div className="max-w-2xl text-[15px] leading-7">
      {!message.text && activeStep ? (
        <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground animate-pulse">
          <span>{activeStep.detail ?? activeStep.tool}</span>
        </div>
      ) : null}
      {waiting ? (
        <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground animate-pulse">
          <span>Looking at the table…</span>
        </div>
      ) : null}
      {message.text ? <AnswerBody text={message.text} /> : null}
      {note ? <p className="mt-2 text-sm text-destructive">{note}</p> : null}
      {hasDetail ? (
        <button
          type="button"
          className="mt-3 text-sm text-muted-foreground hover:text-foreground"
          onClick={() => setOpen((current) => !current)}
        >
          {open ? "Hide the query" : "Show the query"}
        </button>
      ) : null}
      {open ? <QueryDetail message={message} rows={rows} /> : null}
      {message.runId != null ? (
        <div className="mt-2 flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            disabled={message.feedback != null}
            aria-label="Thumbs up"
            aria-pressed={message.feedback === "up"}
            onClick={() => onFeedback(message.runId as number, "up")}
          >
            <ThumbsUp />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            disabled={message.feedback != null}
            aria-label="Thumbs down"
            aria-pressed={message.feedback === "down"}
            onClick={() => onFeedback(message.runId as number, "down")}
          >
            <ThumbsDown />
          </Button>
        </div>
      ) : null}
    </div>
  )
}

function AnswerBody({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      components={{
        p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="mb-3 list-disc pl-5 last:mb-0">{children}</ul>,
        ol: ({ children }) => <ol className="mb-3 list-decimal pl-5 last:mb-0">{children}</ol>,
        li: ({ children }) => <li className="my-0.5">{children}</li>,
        strong: ({ children }) => <strong className="font-medium">{children}</strong>,
        h1: ({ children }) => <p className="mb-2 font-medium">{children}</p>,
        h2: ({ children }) => <p className="mb-2 font-medium">{children}</p>,
        h3: ({ children }) => <p className="mb-2 font-medium">{children}</p>,
        pre: ({ children }) => (
          <pre className="mb-3 overflow-x-auto bg-muted px-3 py-2 text-[13px] last:mb-0">{children}</pre>
        ),
        code: ({ children }) => <code>{children}</code>,
        table: ({ children }) => (
          <div className="mb-3 overflow-x-auto last:mb-0">
            <table className="w-full border-collapse text-sm">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border-b border-border px-2 py-1 text-left font-medium">{children}</th>
        ),
        td: ({ children }) => <td className="border-b border-border px-2 py-1 align-top">{children}</td>,
        a: ({ href, children }) => {
          const safe = href && /^https?:\/\//.test(href) ? href : undefined
          return safe ? (
            <a href={safe} rel="noreferrer" className="underline underline-offset-4">
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
}

function QueryDetail({
  message,
  rows,
}: {
  message: ChatMessage
  rows: Record<string, string>[]
}) {
  const columns = Object.keys(rows[0] ?? {})
  return (
    <div className="mt-3 flex flex-col gap-3 text-sm">
      {message.sql ? (
        <pre className="overflow-x-auto bg-muted px-4 py-3 text-xs leading-relaxed">
          {message.sql}
        </pre>
      ) : null}
      {message.rowCount != null ? (
        <p className="text-muted-foreground">{message.rowCount} rows</p>
      ) : null}
      {rows.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((column) => (
                <TableHead key={column}>{column}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, index) => (
              <TableRow key={index}>
                {columns.map((column) => (
                  <TableCell key={column}>{row[column]}</TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
      <AnswerChart rows={rows} />
      {message.runId != null ? (
        <a
          className="w-fit text-muted-foreground underline-offset-4 hover:underline"
          href={`${API_URL}/results/${message.runId}/export`}
        >
          Export
        </a>
      ) : null}
    </div>
  )
}
