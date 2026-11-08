"use client"

import { useEffect, useState } from "react"
import { PanelRightClose, PanelRightOpen } from "lucide-react"

import { ChatPane, type AnswerBadge, type ChatMessage } from "@/components/chat-pane"
import { DataPane } from "@/components/data-pane"
import { TracePane } from "@/components/trace-pane"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { API_URL, readSse, type Mapping, type Room, type TraceStep } from "@/lib/api"
import { cn } from "@/lib/utils"

export function Dashboard() {
  const [room, setRoom] = useState<Room | null>(null)
  const [roomError, setRoomError] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [steps, setSteps] = useState<TraceStep[]>([])
  const [traceOpen, setTraceOpen] = useState(true)
  const [liveName, setLiveName] = useState<string | null>(null)
  const [liveStatus, setLiveStatus] = useState<string | null>(null)
  const [liveReason, setLiveReason] = useState<string | null>(null)
  const [liveStages, setLiveStages] = useState<{ stage: string; status: string }[]>([])
  const [liveMappings, setLiveMappings] = useState<Mapping[] | null>(null)
  const [liveUploadId, setLiveUploadId] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [scores, setScores] = useState<Record<string, number> | null>(null)
  const [runningEval, setRunningEval] = useState(false)

  async function loadRoom(preferredId?: number) {
    const listed = await fetch(`${API_URL}/workspaces`)
    if (!listed.ok) {
      throw new Error("The API did not list data rooms.")
    }
    const rooms = (await listed.json()) as { id: number; name: string }[]
    const chosen =
      rooms.find((item) => item.id === preferredId) ??
      rooms.find((item) => item.name === "Superstore") ??
      rooms[0]
    if (!chosen) {
      throw new Error("No data room exists yet.")
    }
    const detail = await fetch(`${API_URL}/workspaces/${chosen.id}`)
    if (!detail.ok) {
      throw new Error("The data room could not be read.")
    }
    setRoom((await detail.json()) as Room)
    setRoomError(null)
  }

  useEffect(() => {
    loadRoom().catch(() => setRoomError("The API is not running on localhost:8000."))
    fetch(`${API_URL}/eval/runs`)
      .then((response) => (response.ok ? response.json() : null))
      .then((body: { scores?: { scores?: Record<string, number> } | null } | null) => {
        const stored = body?.scores?.scores
        if (stored) {
          setScores(stored)
        }
      })
      .catch(() => undefined)
  }, [])

  function updateAssistant(id: string, patch: Partial<ChatMessage>) {
    setMessages((current) =>
      current.map((message) => (message.id === id ? { ...message, ...patch } : message)),
    )
  }

  async function ask(question: string) {
    const text = question.trim()
    if (!text || !room) {
      return
    }
    const assistantId = crypto.randomUUID()
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text },
      {
        id: assistantId,
        role: "assistant",
        text: "",
        badge: "waiting",
        sql: null,
        rowCount: null,
        runId: null,
        rows: [],
      },
    ])
    setDraft("")
    setSteps([])
    setTraceOpen(true)
    try {
      const response = await fetch(`${API_URL}/workspaces/${room.id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text }),
      })
      if (!response.ok) {
        updateAssistant(assistantId, {
          text: "The question could not be sent.",
          badge: "caveat",
        })
        return
      }
      await readSse(response, (event, data) => {
        if (event === "step") {
          setSteps((current) => [...current, data as TraceStep])
        } else if (event === "sql") {
          updateAssistant(assistantId, {
            sql: String(data.query ?? ""),
            rowCount: Number(data.row_count ?? 0),
          })
        } else if (event === "token") {
          updateAssistant(assistantId, { text: String(data.text ?? "") })
        } else if (event === "check") {
          updateAssistant(assistantId, { badge: badgeFor(data) })
        } else if (event === "done") {
          updateAssistant(assistantId, {
            runId: Number(data.run_id),
            rows: (data.rows as Record<string, string>[]) ?? [],
          })
        } else if (event === "error") {
          updateAssistant(assistantId, {
            text: "The question failed.",
            badge: "caveat",
          })
        }
      })
    } catch {
      updateAssistant(assistantId, {
        text: "The API is not running on localhost:8000.",
        badge: "caveat",
      })
    }
  }

  async function chooseFile(file: File) {
    if (!room) {
      return
    }
    const name = file.name.toLowerCase()
    if (!name.endsWith(".csv") && !name.endsWith(".xlsx")) {
      setRoomError("Only csv and xlsx files can be selected.")
      return
    }
    setRoomError(null)
    setLiveName(file.name)
    setLiveStatus("received")
    setLiveReason(null)
    setLiveStages([])
    setLiveMappings(null)
    const body = new FormData()
    body.append("file", file)
    const response = await fetch(`${API_URL}/workspaces/${room.id}/uploads`, {
      method: "POST",
      body,
    })
    if (!response.ok) {
      setRoomError("The file could not be uploaded.")
      return
    }
    const payload = (await response.json()) as { upload_id: number }
    setLiveUploadId(String(payload.upload_id))
    const source = new EventSource(`${API_URL}/uploads/${payload.upload_id}/events`)
    let finished = false
    source.addEventListener("step", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as { stage: string; status: string }
      setLiveStages((current) => [...current, data])
    })
    source.addEventListener("done", (event) => {
      finished = true
      const data = JSON.parse((event as MessageEvent).data) as {
        status: string
        reason: string | null
        mappings: Mapping[]
      }
      setLiveStatus(data.status)
      setLiveReason(data.reason)
      setLiveMappings(data.mappings)
      source.close()
      loadRoom(room.id).catch(() => setRoomError("The data room could not be refreshed."))
    })
    source.addEventListener("error", () => {
      if (finished || source.readyState === EventSource.CLOSED) {
        return
      }
      setRoomError("The upload stream failed.")
      source.close()
    })
  }

  async function confirm(decisions: Record<string, string>) {
    const uploadId = liveUploadId ?? room?.uploads[0]?.id
    if (!uploadId || !room) {
      return
    }
    setConfirming(true)
    try {
      const response = await fetch(`${API_URL}/uploads/${uploadId}/mapping`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decisions }),
      })
      const body = (await response.json()) as { status: string; reason: string | null; mappings: Mapping[] }
      setLiveStatus(body.status)
      setLiveReason(body.reason)
      setLiveMappings(body.mappings)
      await loadRoom(room.id)
    } finally {
      setConfirming(false)
    }
  }

  async function feedback(runId: number, rating: "up" | "down") {
    await fetch(`${API_URL}/runs/${runId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating }),
    })
    setMessages((current) =>
      current.map((message) => (message.runId === runId ? { ...message, feedback: rating } : message)),
    )
  }

  async function runEval() {
    setRunningEval(true)
    try {
      const response = await fetch(`${API_URL}/eval/runs`, { method: "POST" })
      if (response.ok) {
        const body = (await response.json()) as { scores: Record<string, number> }
        setScores(body.scores)
      }
    } finally {
      setRunningEval(false)
    }
  }

  const latest = room?.uploads[0]
  const mappings = liveMappings ?? room?.mappings ?? []

  return (
    <div className="flex h-svh flex-col bg-background">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b px-4">
        <span className="text-sm font-medium">Nexus</span>
        <Separator orientation="vertical" className="h-4" />
        <span className="text-sm text-muted-foreground">{room?.name ?? "Data room"}</span>
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
        <DataPane
          fileName={liveName ?? latest?.original_name ?? null}
          status={liveStatus ?? latest?.status ?? null}
          reason={liveReason}
          stages={liveStages}
          mappings={mappings}
          health={room?.health ?? null}
          quarantine={room?.quarantine ?? []}
          uploadId={liveUploadId ?? latest?.id ?? null}
          error={roomError}
          confirming={confirming}
          onFile={chooseFile}
          onConfirm={confirm}
        />
        <ChatPane
          draft={draft}
          messages={messages}
          onDraft={setDraft}
          onAsk={ask}
          onFeedback={feedback}
        />
        {traceOpen ? (
          <TracePane steps={steps} scores={scores} runningEval={runningEval} onRunEval={runEval} />
        ) : null}
      </div>
    </div>
  )
}

function badgeFor(data: Record<string, unknown>): AnswerBadge {
  const kind = String(data.kind ?? "")
  if (kind === "refusal") {
    return "refused"
  }
  if (kind === "sql") {
    return data.verified ? "verified" : "caveat"
  }
  return "unanswered"
}
