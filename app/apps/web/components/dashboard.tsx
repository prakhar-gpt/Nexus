"use client"

import { useState, useEffect } from "react"

import { ChatPane, type AnswerBadge, type ChatMessage } from "@/components/chat-pane"
import { DataPane } from "@/components/data-pane"
import { API_URL, readSse, type Mapping, type Room, type TraceStep, type Turn } from "@/lib/api"
import { cn } from "@/lib/utils"

export function Dashboard() {
  const [room, setRoom] = useState<Room | null>(null)
  const [roomError, setRoomError] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [roomOpen, setRoomOpen] = useState(false)
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
    const loaded = (await detail.json()) as Room
    setRoom(loaded)
    setMessages((current) =>
      current.length === 0 ? turnsToMessages(loaded.turns ?? []) : current,
    )
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
    let finished = false
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
          const step = data as TraceStep
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId
                ? { ...message, activity: upsertStep(message.activity ?? [], step) }
                : message,
            ),
          )
        } else if (event === "sql") {
          updateAssistant(assistantId, {
            sql: String(data.query ?? ""),
            rowCount: Number(data.row_count ?? 0),
          })
        } else if (event === "token") {
          finished = true
          const delta = String(data.text ?? "")
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId ? { ...message, text: message.text + delta } : message,
            ),
          )
        } else if (event === "check") {
          updateAssistant(assistantId, { badge: badgeFor(data) })
        } else if (event === "done") {
          finished = true
          const patch: Partial<ChatMessage> = {
            runId: Number(data.run_id),
            rows: (data.rows as Record<string, string>[]) ?? [],
          }
          if (typeof data.answer === "string" && data.answer) {
            patch.text = data.answer
          }
          updateAssistant(assistantId, patch)
        } else if (event === "error") {
          finished = true
          updateAssistant(assistantId, {
            text: "The question failed.",
            badge: "caveat",
          })
        }
      })
      if (!finished) {
        updateAssistant(assistantId, {
          text: "The answer did not finish.",
          badge: "caveat",
        })
      }
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
      const data = readEvent<{ stage: string; status: string }>(event)
      if (data) {
        setLiveStages((current) => [...current, data])
      }
    })
    source.addEventListener("done", (event) => {
      finished = true
      const data = readEvent<{
        status: string
        reason: string | null
        mappings: Mapping[]
      }>(event)
      if (!data) {
        setRoomError("The upload stream failed.")
        source.close()
        return
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
      if (!response.ok) {
        setRoomError("The mapping could not be saved.")
        return
      }
      const body = (await response.json()) as { status: string; reason: string | null; mappings: Mapping[] }
      setLiveStatus(body.status)
      setLiveReason(body.reason)
      setLiveMappings(body.mappings)
      await loadRoom(room.id)
    } catch {
      setRoomError("The mapping could not be saved.")
    } finally {
      setConfirming(false)
    }
  }

  async function feedback(runId: number, rating: "up" | "down") {
    try {
      const response = await fetch(`${API_URL}/runs/${runId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating }),
      })
      if (!response.ok) {
        setRoomError("The rating could not be saved.")
        return
      }
      setMessages((current) =>
        current.map((message) =>
          message.runId === runId ? { ...message, feedback: rating } : message,
        ),
      )
    } catch {
      setRoomError("The rating could not be saved.")
    }
  }

  async function runEval() {
    setRunningEval(true)
    try {
      const response = await fetch(`${API_URL}/eval/runs`, { method: "POST" })
      if (!response.ok) {
        setRoomError("The scorecard could not be run.")
        return
      }
      const body = (await response.json()) as { scores: Record<string, number> }
      setScores(body.scores)
    } catch {
      setRoomError("The scorecard could not be run.")
    } finally {
      setRunningEval(false)
    }
  }

  const latest = room?.uploads[0]
  const mappings = liveMappings ?? room?.mappings ?? []

  const pending = mappings.some((item) => item.needs_confirmation)
  const busy = messages.some((message) => message.badge === "waiting")
  const rail = (
    <DataPane
      roomName={room?.name ?? "Data room"}
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
      scores={scores}
      runningEval={runningEval}
      onFile={chooseFile}
      onConfirm={confirm}
      onRunEval={runEval}
    />
  )

  return (
    <div className="flex h-svh flex-col bg-background text-foreground md:flex-row">
      <aside
        className={cn(
          "shrink-0 bg-sidebar md:block md:h-svh md:max-h-none md:w-64 md:border-r md:border-sidebar-border",
          roomOpen || pending
            ? "max-h-80 overflow-y-auto border-b border-sidebar-border"
            : "hidden",
        )}
      >
        {rail}
      </aside>
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="flex h-12 items-center px-4 md:hidden">
          <button
            type="button"
            className="text-sm text-muted-foreground"
            aria-expanded={roomOpen || pending}
            onClick={() => setRoomOpen((open) => !open)}
          >
            {room?.name ?? "Data room"}
          </button>
        </div>
        <ChatPane
          draft={draft}
          messages={messages}
          busy={busy}
          onDraft={setDraft}
          onAsk={ask}
          onFeedback={feedback}
        />
      </div>
    </div>
  )
}

function readEvent<T>(event: Event): T | null {
  try {
    return JSON.parse((event as MessageEvent).data) as T
  } catch {
    return null
  }
}

function turnsToMessages(turns: Turn[]): ChatMessage[] {
  return turns.flatMap((turn) => [
    { id: `q-${turn.run_id}`, role: "user" as const, text: turn.question },
    {
      id: `a-${turn.run_id}`,
      role: "assistant" as const,
      text: turn.answer,
      badge: badgeFor({ kind: turn.kind, verified: turn.verified }),
      sql: turn.sql,
      rowCount: turn.rows?.length ?? 0,
      runId: turn.run_id,
      rows: turn.rows ?? [],
    },
  ])
}

function upsertStep(steps: TraceStep[], step: TraceStep): TraceStep[] {
  if (!step.id) {
    return [...steps, step]
  }
  const index = steps.findIndex((item) => item.id === step.id)
  if (index === -1) {
    return [...steps, step]
  }
  const next = steps.slice()
  next[index] = { ...next[index], ...step }
  return next
}

function badgeFor(data: Record<string, unknown>): AnswerBadge {
  if (data.verified === false) {
    return "caveat"
  }
  const kind = String(data.kind ?? "")
  if (kind === "refusal") {
    return "refused"
  }
  if (kind === "sql") {
    return "verified"
  }
  return "unanswered"
}
