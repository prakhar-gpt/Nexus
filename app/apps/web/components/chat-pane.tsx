"use client"

import { useEffect, useRef, useState } from "react"
import { ThumbsDown, ThumbsUp } from "lucide-react"

import { AnswerChart } from "@/components/answer-chart"
import { SUGGESTIONS } from "@/components/suggestions"
import { API_URL } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
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
import { Textarea } from "@/components/ui/textarea"

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
  feedback?: "up" | "down"
}

const BADGE_LABEL: Record<AnswerBadge, string> = {
  waiting: "Running",
  verified: "Verified",
  caveat: "Caveat",
  refused: "Refused",
  unanswered: "Not answered",
}

export function ChatPane({
  draft,
  messages,
  onDraft,
  onAsk,
  onFeedback,
}: {
  draft: string
  messages: ChatMessage[]
  onDraft: (value: string) => void
  onAsk: (question: string) => void
  onFeedback: (runId: number, rating: "up" | "down") => void
}) {
  const threadEnd = useRef<HTMLDivElement>(null)
  useEffect(() => {
    threadEnd.current?.scrollIntoView({ block: "nearest" })
  }, [messages])
  return (
    <section className="flex min-h-[36rem] min-w-0 flex-col overflow-hidden border-b xl:h-full xl:min-h-0 xl:border-r xl:border-b-0">
      <header className="flex h-12 shrink-0 items-center px-4">
        <h2 className="text-sm font-medium">Chat</h2>
      </header>
      <ScrollArea className="min-h-0 flex-1 basis-0 overflow-hidden">
        <div className="flex flex-col gap-4 px-4 pb-4">
          {messages.length === 0 ? (
            <Empty className="min-h-48 border">
              <EmptyHeader>
                <EmptyTitle>Ask a question about this data room</EmptyTitle>
                <EmptyDescription>
                  A verified answer shows its SQL and row count. A question the table cannot support is refused.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            messages.map((message) =>
              message.role === "user" ? (
                <p
                  key={message.id}
                  className="ml-auto max-w-[36rem] rounded-xl bg-muted px-3 py-2 text-sm"
                >
                  {message.text}
                </p>
              ) : (
                <AnswerCard key={message.id} message={message} onFeedback={onFeedback} />
              ),
            )
          )}
          <div ref={threadEnd} />
        </div>
      </ScrollArea>
      <form
        className="flex shrink-0 flex-col gap-3 border-t p-4"
        onSubmit={(event) => {
          event.preventDefault()
          onAsk(draft)
        }}
      >
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((question) => (
            <Button
              key={question}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onDraft(question)}
            >
              {question}
            </Button>
          ))}
        </div>
        <Textarea
          value={draft}
          placeholder="Ask about revenue, region, category, or a missing measure"
          aria-label="Question"
          onChange={(event) => onDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault()
              onAsk(draft)
            }
          }}
        />
        <div className="flex justify-end">
          <Button type="submit" disabled={draft.trim().length === 0}>
            Ask
          </Button>
        </div>
      </form>
    </section>
  )
}

function AnswerCard({
  message,
  onFeedback,
}: {
  message: ChatMessage
  onFeedback: (runId: number, rating: "up" | "down") => void
}) {
  const [showSql, setShowSql] = useState(false)
  const badge = message.badge ?? "waiting"
  const rows = message.rows ?? []
  const columns = Object.keys(rows[0] ?? {})
  return (
    <Card className="max-w-[40rem]">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          Answer
          <Badge variant={badge === "refused" || badge === "caveat" ? "destructive" : "outline"}>
            {BADGE_LABEL[badge]}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="whitespace-pre-wrap">{message.text || "Running the query."}</p>
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
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!message.sql}
            onClick={() => setShowSql((open) => !open)}
          >
            SQL
          </Button>
          <Badge variant="secondary">
            {message.rowCount == null ? "Row count" : `${message.rowCount} rows`}
          </Badge>
          <Badge variant="secondary">Doc passage</Badge>
        </div>
        {showSql && message.sql ? (
          <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">{message.sql}</pre>
        ) : null}
      </CardContent>
      <CardFooter className="gap-2">
        <Button
          variant="ghost"
          size="icon-sm"
          disabled={message.runId == null || message.feedback != null}
          aria-label="Thumbs up"
          onClick={() => message.runId != null && onFeedback(message.runId, "up")}
        >
          <ThumbsUp />
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          disabled={message.runId == null || message.feedback != null}
          aria-label="Thumbs down"
          onClick={() => message.runId != null && onFeedback(message.runId, "down")}
        >
          <ThumbsDown />
        </Button>
        {message.runId != null ? (
          <Button
            variant="outline"
            size="sm"
            className="ml-auto"
            render={<a href={`${API_URL}/results/${message.runId}/export`} />}
          >
            Export CSV
          </Button>
        ) : (
          <Button variant="outline" size="sm" className="ml-auto" disabled>
            Export CSV
          </Button>
        )}
      </CardFooter>
    </Card>
  )
}
