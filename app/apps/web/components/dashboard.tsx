"use client"

import { useState } from "react"
import { PanelRightClose, PanelRightOpen } from "lucide-react"

import { ChatPane, type ChatMessage } from "@/components/chat-pane"
import { DataPane, type LocalFile } from "@/components/data-pane"
import { TracePane } from "@/components/trace-pane"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

const WAITING_ANSWER =
  "This screen cannot answer yet. The chat stream, SQL, and the checker connect in the next step."

function acceptedFile(file: File) {
  const name = file.name.toLowerCase()
  return name.endsWith(".csv") || name.endsWith(".xlsx")
}

export function Dashboard() {
  const [file, setFile] = useState<LocalFile | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [traceOpen, setTraceOpen] = useState(true)

  function chooseFile(next: File) {
    if (!acceptedFile(next)) {
      setFileError("Only csv and xlsx files can be selected.")
      return
    }
    setFileError(null)
    setFile({ name: next.name, size: next.size })
  }

  function ask(question: string) {
    const text = question.trim()
    if (!text) {
      return
    }
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text },
      { id: crypto.randomUUID(), role: "assistant", text: WAITING_ANSWER },
    ])
    setDraft("")
    setTraceOpen(true)
  }

  return (
    <div className="flex h-svh flex-col bg-background">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b px-4">
        <span className="text-sm font-medium">Nexus</span>
        <Separator orientation="vertical" className="h-4" />
        <span className="text-sm text-muted-foreground">Data room</span>
        <Button
          className="ml-auto"
          variant="outline"
          size="sm"
          aria-expanded={traceOpen}
          onClick={() => setTraceOpen((open) => !open)}
        >
          {traceOpen ? <PanelRightClose /> : <PanelRightOpen />}
          {traceOpen ? "Hide trace" : "Show trace"}
        </Button>
      </header>
      <div
        className={cn(
          "grid min-h-0 flex-1 grid-cols-1 overflow-y-auto xl:overflow-hidden",
          traceOpen
            ? "xl:grid-cols-[20rem_minmax(0,1fr)_22rem]"
            : "xl:grid-cols-[20rem_minmax(0,1fr)]",
        )}
      >
        <DataPane file={file} error={fileError} onFile={chooseFile} />
        <ChatPane draft={draft} messages={messages} onDraft={setDraft} onAsk={ask} />
        {traceOpen ? <TracePane hasQuestion={messages.length > 0} /> : null}
      </div>
    </div>
  )
}
