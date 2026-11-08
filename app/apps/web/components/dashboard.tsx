"use client"

import { useState, useEffect } from "react"
import { Menu } from "lucide-react"

import { ChatPane, type AnswerBadge, type ChatMessage } from "@/components/chat-pane"
import { Sidebar } from "@/components/sidebar"
import { CreateWorkspaceModal } from "@/components/create-workspace-modal"
import { AuthModal } from "@/components/auth-modal"
import {
  API_URL,
  readSse,
  type Mapping,
  type Room,
  type Thread,
  type TraceStep,
  type Turn,
  type WorkspaceSummary,
} from "@/lib/api"
import { cn } from "@/lib/utils"

export function Dashboard() {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([])
  const [room, setRoom] = useState<Room | null>(null)
  const [roomError, setRoomError] = useState<string | null>(null)
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string>("default")
  const [draft, setDraft] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  // Dialog Modals
  const [createWorkspaceOpen, setCreateWorkspaceOpen] = useState(false)
  const [authModalOpen, setAuthModalOpen] = useState(false)

  // Ingestion states
  const [liveName, setLiveName] = useState<string | null>(null)
  const [liveStatus, setLiveStatus] = useState<string | null>(null)
  const [liveReason, setLiveReason] = useState<string | null>(null)
  const [liveStages, setLiveStages] = useState<{ stage: string; status: string }[]>([])
  const [liveMappings, setLiveMappings] = useState<Mapping[] | null>(null)
  const [liveUploadId, setLiveUploadId] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)

  // Eval scorecard state
  const [scores, setScores] = useState<Record<string, number> | null>(null)
  const [runningEval, setRunningEval] = useState(false)

  async function loadWorkspaces(preferredId?: number) {
    try {
      const res = await fetch(`${API_URL}/workspaces`)
      if (!res.ok) throw new Error("Could not list data rooms.")
      const list = (await res.json()) as WorkspaceSummary[]
      setWorkspaces(list)
      const chosen =
        list.find((item) => item.id === preferredId) ??
        list.find((item) => item.name === "Superstore") ??
        list[0]
      if (chosen) {
        await selectRoom(chosen.id)
      }
    } catch {
      setRoomError("The API is not running on localhost:8000.")
    }
  }

  async function selectRoom(roomId: number, preferredThreadId?: string) {
    try {
      const res = await fetch(`${API_URL}/workspaces/${roomId}`)
      if (!res.ok) throw new Error("The data room could not be loaded.")
      const loaded = (await res.json()) as Room
      setRoom(loaded)
      const roomThreads = loaded.threads ?? []
      setThreads(roomThreads)

      const targetThread =
        preferredThreadId ??
        (roomThreads.length > 0 ? roomThreads[0].id : "default")
      setActiveThreadId(targetThread)

      await loadThreadTurns(roomId, targetThread, loaded.turns ?? [])
      setRoomError(null)
    } catch (e: any) {
      setRoomError(e.message || "Could not read data room.")
    }
  }

  async function loadThreadTurns(roomId: number, threadId: string, preloadedTurns?: Turn[]) {
    try {
      let turnsToUse = preloadedTurns
      if (!turnsToUse) {
        const res = await fetch(`${API_URL}/workspaces/${roomId}/threads/${threadId}/turns`)
        if (res.ok) {
          turnsToUse = (await res.json()) as Turn[]
        }
      }
      const filtered = (turnsToUse ?? []).filter(
        (turn) => (turn.thread_id || "default") === threadId
      )
      setMessages(turnsToMessages(filtered))
    } catch {
      setMessages([])
    }
  }

  useEffect(() => {
    loadWorkspaces()
    fetch(`${API_URL}/eval/runs`)
      .then((res) => (res.ok ? res.json() : null))
      .then((body: { scores?: { scores?: Record<string, number> } | null } | null) => {
        const stored = body?.scores?.scores
        if (stored) setScores(stored)
      })
      .catch(() => undefined)
  }, [])

  function updateAssistant(id: string, patch: Partial<ChatMessage>) {
    setMessages((current) =>
      current.map((msg) => (msg.id === id ? { ...msg, ...patch } : msg)),
    )
  }

  async function handleCreateWorkspace(name: string) {
    try {
      const res = await fetch(`${API_URL}/workspaces`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      })
      if (res.ok) {
        const created = (await res.json()) as { id: number; name: string }
        await loadWorkspaces(created.id)
      }
    } catch {
      setRoomError("Could not create data room.")
    }
  }

  async function handleDeleteWorkspace(workspaceId: number) {
    try {
      const res = await fetch(`${API_URL}/workspaces/${workspaceId}`, {
        method: "DELETE",
      })
      if (res.ok) {
        const remaining = workspaces.filter((w) => w.id !== workspaceId)
        setWorkspaces(remaining)
        if (room?.id === workspaceId && remaining.length > 0) {
          await selectRoom(remaining[0].id)
        }
      }
    } catch {
      setRoomError("Could not delete data room.")
    }
  }

  function handleNewThread() {
    const newId = `thread-${Date.now().toString(36)}`
    setActiveThreadId(newId)
    setMessages([])
    setThreads((prev) => [
      { id: newId, title: "New Conversation", created_at: new Date().toISOString(), turn_count: 0 },
      ...prev,
    ])
  }

  async function handleSelectThread(threadId: string) {
    if (!room) return
    setActiveThreadId(threadId)
    await loadThreadTurns(room.id, threadId)
  }

  async function handleDeleteThread(threadId: string) {
    if (!room) return
    try {
      const res = await fetch(`${API_URL}/workspaces/${room.id}/threads/${threadId}`, {
        method: "DELETE",
      })
      if (res.ok) {
        const remaining = threads.filter((th) => th.id !== threadId)
        setThreads(remaining)
        if (activeThreadId === threadId) {
          const nextThread = remaining.length > 0 ? remaining[0].id : "default"
          setActiveThreadId(nextThread)
          await loadThreadTurns(room.id, nextThread)
        }
      }
    } catch {
      setRoomError("Could not delete conversation.")
    }
  }

  async function ask(question: string) {
    const text = question.trim()
    if (!text || !room) return

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
        body: JSON.stringify({ question: text, thread_id: activeThreadId }),
      })
      if (!response.ok) {
        updateAssistant(assistantId, {
          text: "The question could not be sent.",
          badge: "refused",
        })
        return
      }

      await readSse(response, (event, data) => {
        if (event === "token") {
          const chunk = String(data.text ?? "")
          if (chunk) {
            updateAssistant(assistantId, {
              text: `${latestText(messages, assistantId)}${chunk}`,
              activity: [],
            })
          }
        } else if (event === "step") {
          const step = data as unknown as TraceStep
          updateAssistant(assistantId, { activity: [step] })
        } else if (event === "sql") {
          updateAssistant(assistantId, {
            sql: (data.query as string) || null,
            rowCount: Number(data.row_count ?? 0),
          })
        } else if (event === "check") {
          updateAssistant(assistantId, { badge: badgeFor(data) })
        } else if (event === "done") {
          finished = true
          updateAssistant(assistantId, {
            text: (data.answer as string) || latestText(messages, assistantId),
            runId: Number(data.run_id ?? 0),
            rows: (data.rows as Record<string, string>[]) ?? [],
            activity: [],
          })
          setThreads((prev) =>
            prev.map((th) =>
              th.id === activeThreadId
                ? {
                    ...th,
                    title: th.title === "New Conversation" ? (text.length > 35 ? text.slice(0, 32) + "..." : text) : th.title,
                    turn_count: th.turn_count + 1,
                  }
                : th
            )
          )
        } else if (event === "error") {
          updateAssistant(assistantId, {
            text: "The model could not be reached.",
            badge: "refused",
            activity: [],
          })
        }
      })
    } catch {
      updateAssistant(assistantId, {
        text: "The stream could not be read.",
        badge: "refused",
        activity: [],
      })
    } finally {
      if (!finished) {
        updateAssistant(assistantId, { activity: [] })
      }
    }
  }

  function latestText(list: ChatMessage[], id: string) {
    return list.find((m) => m.id === id)?.text ?? ""
  }

  async function feedback(runId: number, rating: "up" | "down") {
    try {
      await fetch(`${API_URL}/runs/${runId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating }),
      })
      setMessages((current) =>
        current.map((msg) => (msg.runId === runId ? { ...msg, feedback: rating } : msg)),
      )
    } catch {
      // Ignored
    }
  }

  async function chooseFile(file: File) {
    if (!room) return
    setLiveName(file.name)
    setLiveStatus("uploading")
    setLiveReason(null)
    setLiveStages([])
    setLiveMappings(null)
    setLiveUploadId(null)

    const form = new FormData()
    form.append("file", file)
    try {
      const res = await fetch(`${API_URL}/workspaces/${room.id}/uploads`, {
        method: "POST",
        body: form,
      })
      if (!res.ok) {
        setLiveStatus("rejected")
        setLiveReason("The file was rejected.")
        return
      }
      const body = (await res.json()) as { upload_id: number; status: string }
      setLiveUploadId(String(body.upload_id))
      setLiveStatus(body.status)
      listenToUpload(body.upload_id)
    } catch {
      setLiveStatus("rejected")
      setLiveReason("The upload failed.")
    }
  }

  function listenToUpload(uploadId: number) {
    const source = new EventSource(`${API_URL}/uploads/${uploadId}/events`)
    source.onmessage = (event) => {
      const payload = readEvent<{
        stage?: string
        status?: string
        reason?: string
        final?: string
      }>(event)
      if (!payload) return
      if (payload.stage && payload.status) {
        setLiveStages((curr) => [
          ...curr.filter((item) => item.stage !== payload.stage),
          { stage: payload.stage!, status: payload.status! },
        ])
      }
      if (payload.reason) setLiveReason(payload.reason)
      if (payload.final) {
        setLiveStatus(payload.final)
        source.close()
        loadMappings(uploadId)
        if (room) selectRoom(room.id, activeThreadId)
      }
    }
    source.onerror = () => source.close()
  }

  async function loadMappings(uploadId: number) {
    try {
      const res = await fetch(`${API_URL}/uploads/${uploadId}/mapping`)
      if (!res.ok) return
      const body = (await res.json()) as { mappings: Mapping[] }
      setLiveMappings(body.mappings)
    } catch {
      // Ignored
    }
  }

  async function confirm(decisions: Record<string, string>) {
    const id = liveUploadId ?? room?.uploads[0]?.id
    if (!id || !room) return
    setConfirming(true)
    try {
      const res = await fetch(`${API_URL}/uploads/${id}/mapping`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decisions }),
      })
      if (!res.ok) return
      setLiveMappings(null)
      await selectRoom(room.id, activeThreadId)
    } finally {
      setConfirming(false)
    }
  }

  async function runEval() {
    setRunningEval(true)
    try {
      const res = await fetch(`${API_URL}/eval/runs`, { method: "POST" })
      if (!res.ok) return
      const body = (await res.json()) as { scores: Record<string, number> }
      setScores(body.scores)
    } catch {
      setRoomError("The eval could not be run.")
    } finally {
      setRunningEval(false)
    }
  }

  const latest = room?.uploads[0]
  const mappings = liveMappings ?? room?.mappings ?? []
  const pending = mappings.some((item) => item.needs_confirmation)
  const busy = messages.some((msg) => msg.badge === "waiting")

  return (
    <div className="flex h-svh flex-col bg-background text-foreground md:flex-row">
      {/* Clean, De-cluttered Left Sidebar */}
      <aside
        className={cn(
          "shrink-0 bg-sidebar md:block md:h-svh md:max-h-none md:w-64 md:border-r md:border-sidebar-border shadow-[1px_0_0_0_rgba(0,0,0,0.03)]",
          mobileMenuOpen || pending ? "max-h-96 overflow-y-auto border-b border-sidebar-border" : "hidden",
        )}
      >
        <Sidebar
          roomName={room?.name ?? "Data room"}
          workspaces={workspaces}
          currentRoomId={room?.id ?? null}
          onSelectWorkspace={(id) => selectRoom(id)}
          onOpenCreateWorkspace={() => setCreateWorkspaceOpen(true)}
          onDeleteWorkspace={handleDeleteWorkspace}
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={handleSelectThread}
          onNewThread={handleNewThread}
          onDeleteThread={handleDeleteThread}
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
          onOpenAuthModal={() => setAuthModalOpen(true)}
        />
      </aside>

      {/* Main Canvas / Chat Experience */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Mobile Header */}
        <div className="flex h-12 items-center justify-between px-4 border-b border-border md:hidden">
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-primary text-[10px] font-bold text-primary-foreground">
              N
            </span>
            <span className="font-semibold text-sm">Nexus</span>
          </div>
          <button
            type="button"
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setMobileMenuOpen((open) => !open)}
          >
            <Menu className="h-4 w-4" />
            <span>{room?.name ?? "Data Room"}</span>
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

      {/* Shadcn Dialog: Create Workspace */}
      <CreateWorkspaceModal
        isOpen={createWorkspaceOpen}
        onClose={() => setCreateWorkspaceOpen(false)}
        onCreate={handleCreateWorkspace}
      />

      {/* Shadcn Dialog: Auth Modal (Sign In / Register) */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
      />
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
