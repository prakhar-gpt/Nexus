"use client"

import { ThumbsDown, ThumbsUp } from "lucide-react"

import { SUGGESTIONS } from "@/components/suggestions"
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
import { Textarea } from "@/components/ui/textarea"

export type ChatMessage = {
  id: string
  role: "user" | "assistant"
  text: string
}

const SOURCE_CHIPS = ["SQL", "Row count", "Doc passage"] as const

export function ChatPane({
  draft,
  messages,
  onDraft,
  onAsk,
}: {
  draft: string
  messages: ChatMessage[]
  onDraft: (value: string) => void
  onAsk: (question: string) => void
}) {
  return (
    <section className="flex min-h-[36rem] min-w-0 flex-col border-b xl:min-h-0 xl:border-r xl:border-b-0">
      <header className="flex h-12 shrink-0 items-center px-4">
        <h2 className="text-sm font-medium">Chat</h2>
      </header>
      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-4 px-4 pb-4">
          {messages.length === 0 ? (
            <Empty className="min-h-48 border">
              <EmptyHeader>
                <EmptyTitle>Ask a question about this data room</EmptyTitle>
                <EmptyDescription>
                  Answers, verified badges, and source chips appear here. Nothing is answered on this screen yet.
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
                <Card key={message.id} className="max-w-[40rem]">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      Answer
                      <Badge variant="outline">Not connected</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    <p>{message.text}</p>
                    <div className="flex flex-wrap gap-2">
                      {SOURCE_CHIPS.map((chip) => (
                        <Badge key={chip} variant="secondary">
                          {chip}
                        </Badge>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Source chips stay inactive until an answer has SQL and a row count.
                    </p>
                  </CardContent>
                  <CardFooter className="gap-2">
                    <Button variant="ghost" size="icon-sm" disabled aria-label="Thumbs up">
                      <ThumbsUp />
                    </Button>
                    <Button variant="ghost" size="icon-sm" disabled aria-label="Thumbs down">
                      <ThumbsDown />
                    </Button>
                    <Button variant="outline" size="sm" disabled className="ml-auto">
                      Export CSV
                    </Button>
                  </CardFooter>
                </Card>
              ),
            )
          )}
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
