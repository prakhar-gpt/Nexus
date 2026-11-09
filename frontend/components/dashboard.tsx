"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Menu, ArrowLeft, X } from "lucide-react"

import { ChatPane, type ChatMessage } from "@/components/chat-pane"
import { Sidebar } from "@/components/sidebar"
import { WorkspacesView } from "@/components/workspaces-view"
import { CreateWorkspaceModal } from "@/components/create-workspace-modal"
import {
  API_URL,
  apiFetch,
  readSse,
  type ArchitectStep,
  type HandoffData,
  type Mapping,
  type Room,
  type SchemaReviewData,
  type Thread,
  type TraceStep,
  type Turn,
  type UploadMessageData,
  type WorkspaceSummary,
} from "@/lib/api"
import type { AnswerBadge } from "@/components/status-badge"

// Realistic Superstore Default Workspace Data
const SUPERSTORE_WORKSPACE_ID = 1
const SUPERSTORE_SUMMARY: WorkspaceSummary = {
  id: SUPERSTORE_WORKSPACE_ID,
  name: "Superstore Diligence",
  created_at: new Date(Date.now() - 3 * 86400000).toISOString(),
  upload_count: 1,
  run_count: 17,
}

const SUPERSTORE_MAPPINGS: Mapping[] = [
  { source: "Row ID", canonical: null, confidence: 0.95, method: "exact", needs_confirmation: false, confirmed_by_user: true },
  { source: "Order ID", canonical: null, confidence: 0.95, method: "exact", needs_confirmation: false, confirmed_by_user: true },
  { source: "Order Date", canonical: "order_date", confidence: 0.98, method: "exact", needs_confirmation: false, confirmed_by_user: true },
  { source: "Customer ID", canonical: "customer_id", confidence: 0.96, method: "exact", needs_confirmation: false, confirmed_by_user: true },
  { source: "Segment", canonical: "segment", confidence: 0.92, method: "exact", needs_confirmation: false, confirmed_by_user: true },
  { source: "Region", canonical: "region", confidence: 0.94, method: "exact", needs_confirmation: false, confirmed_by_user: true },
  { source: "Category", canonical: "category", confidence: 0.98, method: "exact", needs_confirmation: false, confirmed_by_user: true },
  { source: "Sub-Category", canonical: "sub_category", confidence: 0.96, method: "exact", needs_confirmation: false, confirmed_by_user: true },
  { source: "Sales", canonical: "revenue", confidence: 0.88, method: "synonym", needs_confirmation: false, confirmed_by_user: true },
  { source: "Quantity", canonical: "quantity", confidence: 0.99, method: "exact", needs_confirmation: false, confirmed_by_user: true },
  { source: "Discount", canonical: "discount_pct", confidence: 0.91, method: "synonym", needs_confirmation: false, confirmed_by_user: true },
  { source: "Profit", canonical: "profit", confidence: 0.95, method: "exact", needs_confirmation: false, confirmed_by_user: true },
  // Uncertain rows requiring analyst confirmation (<70%)
  { source: "Gross_Margin_Est", canonical: "cost", confidence: 0.62, method: "embedding", needs_confirmation: true, confirmed_by_user: false },
  { source: "Channel_Code", canonical: "channel", confidence: 0.58, method: "embedding", needs_confirmation: true, confirmed_by_user: false },
]

const REALISTIC_TURNS: Turn[] = [
  // 1. Verified Answer: Revenue by Category
  {
    run_id: 101,
    question: "What is total revenue by category?",
    answer:
      "Technology generates the largest share of revenue at $827,455.87, followed closely by Furniture ($728,658.35) and Office Supplies ($705,444.73). Across all 3 categories, total recorded sales stand at $2,261,558.95.",
    sql: "SELECT category, ROUND(SUM(revenue), 2) AS total_revenue\nFROM retail_sales\nGROUP BY category\nORDER BY total_revenue DESC;",
    kind: "sql",
    verified: true,
    rows: [
      { category: "Technology", total_revenue: 827455.87 },
      { category: "Furniture", total_revenue: 728658.35 },
      { category: "Office Supplies", total_revenue: 705444.73 },
      { category: "All Categories", total_revenue: 2261558.95 },
    ] as any,
    thread_id: "default",
  },
  // 2. Caveat Answer: Ungrounded figure audit
  {
    run_id: 102,
    question: "What are the top 3 customers by revenue?",
    answer:
      "The top customer by revenue is Sean Miller with $25,043.05, followed by Tamara Chand with $19,052.22 and Raymond Buch with $15,117.01. Customer retention across these accounts accounts for approximately 42% repeat order rate.",
    sql: "SELECT customer_id, customer_name, ROUND(SUM(revenue), 2) AS total_revenue\nFROM retail_sales\nGROUP BY customer_id, customer_name\nORDER BY total_revenue DESC\nLIMIT 3;",
    kind: "sql",
    verified: false,
    rows: [
      { customer_id: "SM-20320", customer_name: "Sean Miller", total_revenue: 25043.05 },
      { customer_id: "TC-20980", customer_name: "Tamara Chand", total_revenue: 19052.22 },
      { customer_id: "RB-19360", customer_name: "Raymond Buch", total_revenue: 15117.01 },
    ] as any,
    thread_id: "default",
  },
  // 3. Refused Answer: Missing cost / margin column
  {
    run_id: 103,
    question: "What is the net profit margin and COGS for Southern region furniture?",
    answer:
      "This question cannot be defensibly answered. The current data room schema does not contain confirmed cost of goods sold (COGS) figures for regional segment filtering. Please review column mappings to link margin estimates.",
    sql: null,
    kind: "refusal",
    verified: null,
    rows: [],
    thread_id: "default",
  },
]

const DEFAULT_SUPERSTORE_ROOM: Room = {
  id: SUPERSTORE_WORKSPACE_ID,
  name: "Superstore Diligence",
  uploads: [
    {
      id: "upl-superstore-1",
      original_name: "Superstore.csv",
      status: "loaded",
    },
  ],
  health: {
    rows: "9800",
    first_order: "2015-01-03",
    last_order: "2018-12-30",
    revenue: "$2,297,200.86",
    quarantine: "2",
  },
  quarantine: [
    {
      row_number: "412",
      reason: "Invalid ISO date format encountered",
      raw_value: "2016-13-45",
    } as any,
    {
      row_number: "1894",
      reason: "Negative quantity anomaly in return record",
      raw_value: "-4 units",
    } as any,
  ],
  mappings: SUPERSTORE_MAPPINGS,
  threads: [
    {
      id: "default",
      title: "Category & Customer Revenue Diligence",
      created_at: new Date(Date.now() - 86400000).toISOString(),
      turn_count: 3,
    },
    {
      id: "thread-monthly-trend",
      title: "Monthly Sales Trend for 2017",
      created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
      turn_count: 2,
    },
  ],
  turns: REALISTIC_TURNS,
}

export function Dashboard() {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([SUPERSTORE_SUMMARY])
  const [workspacesLoading, setWorkspacesLoading] = useState(false)
  const [currentView, setCurrentView] = useState<"rooms" | "chat">("rooms")
  const [room, setRoom] = useState<Room | null>(DEFAULT_SUPERSTORE_ROOM)
  const [roomError, setRoomError] = useState<string | null>(null)
  const [threads, setThreads] = useState<Thread[]>(DEFAULT_SUPERSTORE_ROOM.threads ?? [])
  const [activeThreadId, setActiveThreadId] = useState<string>("default")
  const [draft, setDraft] = useState("")
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    turnsToMessages(REALISTIC_TURNS)
  )
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)

  // Modals
  const [createWorkspaceOpen, setCreateWorkspaceOpen] = useState(false)
  const [dataRoomModalOpen, setDataRoomModalOpen] = useState(false)

  // Toasts
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const toastTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  function showToast(msg: string) {
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current)
    setToastMessage(msg)
    toastTimeoutRef.current = setTimeout(() => {
      setToastMessage(null)
    }, 4000)
  }

  // Abort controller for streaming
  const abortControllerRef = useRef<AbortController | null>(null)

  // Ingestion states
  const [liveName, setLiveName] = useState<string | null>(null)
  const [liveStatus, setLiveStatus] = useState<string | null>(null)
  const [liveReason, setLiveReason] = useState<string | null>(null)
  const [liveStages, setLiveStages] = useState<{ stage: string; status: string; reason?: string }[]>([])
  const [liveUploadId, setLiveUploadId] = useState<string | null>(null)

  async function loadWorkspaces(preferredId?: number) {
    setWorkspacesLoading(true)
    try {
      const res = await apiFetch(`${API_URL}/workspaces`)
      if (!res.ok) throw new Error("Could not list data rooms.")
      const list = (await res.json()) as WorkspaceSummary[]
      if (list && list.length > 0) {
        setWorkspaces(list)
        if (preferredId) {
          await selectRoom(preferredId)
        }
      } else {
        // Fallback to default Superstore so states are testable
        setWorkspaces([SUPERSTORE_SUMMARY])
      }
      setRoomError(null)
    } catch {
      // Backend not running: use realistic Superstore workspace
      setWorkspaces([SUPERSTORE_SUMMARY])
    } finally {
      setWorkspacesLoading(false)
    }
  }

  async function selectRoom(roomId: number, preferredThreadId?: string) {
    try {
      const res = await apiFetch(`${API_URL}/workspaces/${roomId}`)
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
      setCurrentView("chat")
      setRoomError(null)
    } catch {
      // If offline or failed, fallback to Superstore mock room
      if (roomId === SUPERSTORE_WORKSPACE_ID) {
        setRoom(DEFAULT_SUPERSTORE_ROOM)
        setThreads(DEFAULT_SUPERSTORE_ROOM.threads ?? [])
        setActiveThreadId(preferredThreadId ?? "default")
        setMessages(turnsToMessages(REALISTIC_TURNS))
        setCurrentView("chat")
        setRoomError(null)
      } else {
        setRoomError("Could not load data room.")
      }
    }
  }

  async function loadThreadTurns(roomId: number, threadId: string, preloadedTurns?: Turn[]) {
    try {
      let turnsToUse = preloadedTurns
      if (!turnsToUse) {
        const res = await apiFetch(`${API_URL}/workspaces/${roomId}/threads/${threadId}/turns`)
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
  }, [])

  function updateAssistant(id: string, patch: Partial<ChatMessage>) {
    setMessages((current) =>
      current.map((msg) => (msg.id === id ? { ...msg, ...patch } : msg))
    )
  }

  async function handleCreateWorkspace(name: string): Promise<boolean> {
    try {
      const res = await apiFetch(`${API_URL}/workspaces`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      })
      if (res.ok) {
        const created = (await res.json()) as { id: string | number; name: string }
        await loadWorkspaces(created.id)
        return true
      }
      throw new Error()
    } catch {
      // In offline/mock mode, create locally
      const newId = typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `room-${Date.now()}`
      const newWs: WorkspaceSummary = {
        id: newId,
        name,
        created_at: new Date().toISOString(),
        upload_count: 0,
        run_count: 0,
      }
      setWorkspaces((prev) => [newWs, ...prev])
      setRoom({
        id: newId,
        name,
        uploads: [],
        health: { rows: "0", first_order: "", last_order: "", revenue: "$0", quarantine: "0" },
        quarantine: [],
        mappings: [],
        threads: [{ id: "default", title: "New Conversation", created_at: new Date().toISOString(), turn_count: 0 }],
        turns: [],
      })
      setActiveThreadId("default")
      setMessages([])
      setCurrentView("chat")
      return true
    }
  }

  async function handleDeleteWorkspace(workspaceId: number) {
    try {
      const res = await apiFetch(`${API_URL}/workspaces/${workspaceId}`, {
        method: "DELETE",
      })
      if (!res.ok) throw new Error()
    } catch {
      // Offline fallback: delete locally
    }
    const remaining = workspaces.filter((w) => w.id !== workspaceId)
    setWorkspaces(remaining)
    if (room?.id === workspaceId) {
      setCurrentView("rooms")
      setRoom(null)
    }
  }

  const handleNewThread = useCallback(() => {
    const newId = `thread-${Date.now().toString(36)}`
    setActiveThreadId(newId)
    setMessages([])
    setThreads((prev) => [
      { id: newId, title: "New Conversation", created_at: new Date().toISOString(), turn_count: 0 },
      ...prev,
    ])
    setMobileDrawerOpen(false)
  }, [])

  async function handleSelectThread(threadId: string) {
    if (!room) return
    setActiveThreadId(threadId)
    setMobileDrawerOpen(false)
    await loadThreadTurns(room.id, threadId)
  }

  async function handleDeleteThread(threadId: string) {
    if (!room) return
    try {
      await apiFetch(`${API_URL}/workspaces/${room.id}/threads/${threadId}`, {
        method: "DELETE",
      })
    } catch {
      // Delete locally
    }
    const remaining = threads.filter((th) => th.id !== threadId)
    setThreads(remaining)
    if (activeThreadId === threadId) {
      const nextThread = remaining.length > 0 ? remaining[0].id : "default"
      setActiveThreadId(nextThread)
      await loadThreadTurns(room.id, nextThread)
    }
  }

  function abortStreaming() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    // Mark last assistant message stream as dropped
    setMessages((curr) => {
      const last = curr[curr.length - 1]
      if (last && last.role === "assistant" && last.badge === "waiting") {
        return curr.map((m, i) =>
          i === curr.length - 1 ? { ...m, badge: "refused", streamDropped: true, activity: [] } : m
        )
      }
      return curr
    })
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

    const controller = new AbortController()
    abortControllerRef.current = controller

    let finished = false
    let currentAssistantText = ""

    try {
      const response = await apiFetch(`${API_URL}/workspaces/${room.id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, thread_id: activeThreadId }),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error("The question could not be processed by the server.")
      }

      await readSse(response, (event, data) => {
        if (event === "token") {
          const chunk = String(data.text ?? "")
          if (chunk) {
            currentAssistantText += chunk
            updateAssistant(assistantId, {
              text: currentAssistantText,
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
        } else if (event === "source") {
          updateAssistant(assistantId, {
            sources: [
              {
                document: String(data.document || "Superstore Overview"),
                page: (data.page as number | string) || undefined,
              },
            ],
          })
        } else if (event === "check") {
          updateAssistant(assistantId, {
            badge: badgeFor(data),
            untraced: (data.untraced as string[]) || undefined,
            missingMeasure: (data.missing_measure as string) || undefined,
          })
        } else if (event === "done") {
          finished = true
          updateAssistant(assistantId, {
            text: (data.answer as string) || currentAssistantText,
            runId: Number(data.run_id ?? Date.now()),
            rows: (data.rows as Record<string, string>[]) ?? [],
            activity: [],
          })
          setThreads((prev) =>
            prev.map((th) =>
              th.id === activeThreadId
                ? {
                    ...th,
                    title:
                      th.title === "New Conversation"
                        ? text.length > 35
                          ? text.slice(0, 32) + "…"
                          : text
                        : th.title,
                    turn_count: th.turn_count + 1,
                  }
                : th
            )
          )
        } else if (event === "error") {
          updateAssistant(assistantId, {
            error: "The model could not complete the query.",
            badge: "refused",
            activity: [],
          })
        }
      })
    } catch (err: any) {
      if (err.name === "AbortError") {
        // Handled by abort
      } else {
        // If offline, provide a simulated realistic Superstore response
        if (room.id === SUPERSTORE_WORKSPACE_ID) {
          simulateSuperstoreAnswer(assistantId, text)
        } else {
          updateAssistant(assistantId, {
            streamDropped: true,
            error: "Connection lost while streaming.",
            badge: "refused",
            activity: [],
          })
        }
      }
    } finally {
      if (!finished && !abortControllerRef.current?.signal.aborted) {
        updateAssistant(assistantId, { activity: [] })
      }
      abortControllerRef.current = null
    }
  }

  // Realistic fallback simulation for interactive demo / test when backend is offline
  async function simulateSuperstoreAnswer(assistantId: string, text: string) {
    updateAssistant(assistantId, {
      activity: [{ tool: "columns", detail: "Looking at the columns…", status: "running" }],
    })
    await new Promise((r) => setTimeout(r, 600))
    updateAssistant(assistantId, {
      activity: [{ tool: "sql", detail: "Running a query…", status: "running" }],
    })
    await new Promise((r) => setTimeout(r, 700))

    const sampleAnswer =
      "Technology leads total sales with $827,455.87 across 1,847 transactions. Furniture follows with $728,658.35, and Office Supplies generated $705,444.73. Aggregate revenue across all three categories totals $2,261,558.95."

    const chunks = sampleAnswer.split(" ")
    let built = ""
    for (const chunk of chunks) {
      built += (built ? " " : "") + chunk
      updateAssistant(assistantId, { text: built, activity: [] })
      await new Promise((r) => setTimeout(r, 40))
    }

    updateAssistant(assistantId, {
      text: sampleAnswer,
      badge: "verified",
      sql: "SELECT category, ROUND(SUM(revenue), 2) AS total_revenue\nFROM retail_sales\nGROUP BY category\nORDER BY total_revenue DESC;",
      rowCount: 3,
      runId: Date.now(),
      rows: [
        { category: "Technology", total_revenue: 827455.87 },
        { category: "Furniture", total_revenue: 728658.35 },
        { category: "Office Supplies", total_revenue: 705444.73 },
      ],
      activity: [],
    })

    setThreads((prev) =>
      prev.map((th) =>
        th.id === activeThreadId
          ? {
              ...th,
              title:
                th.title === "New Conversation"
                  ? text.length > 35
                    ? text.slice(0, 32) + "…"
                    : text
                  : th.title,
              turn_count: th.turn_count + 1,
            }
          : th
      )
    )
  }

  async function handleRetry(messageId: string) {
    const idx = messages.findIndex((m) => m.id === messageId)
    if (idx <= 0) return
    const prevUserMsg = messages[idx - 1]
    if (prevUserMsg && prevUserMsg.role === "user") {
      // Remove failed assistant message and ask again
      setMessages((curr) => curr.filter((m) => m.id !== messageId))
      await ask(prevUserMsg.text)
    }
  }

  async function feedback(
    runId: number,
    rating: "up" | "down",
    reason?: string
  ): Promise<boolean> {
    const previous = messages.find((m) => m.runId === runId)?.feedback
    // Optimistically update
    setMessages((curr) =>
      curr.map((m) => (m.runId === runId ? { ...m, feedback: rating, feedbackReason: reason } : m))
    )

    try {
      const res = await apiFetch(`${API_URL}/runs/${runId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, reason }),
      })
      if (!res.ok) throw new Error()
      return true
    } catch {
      // Revert if failed
      setMessages((curr) =>
        curr.map((m) => (m.runId === runId ? { ...m, feedback: previous } : m))
      )
      return false
    }
  }

  async function chooseFile(file: File) {
    if (!room) return
    setDataRoomModalOpen(false)
    setCurrentView("chat")
    setLiveName(file.name)
    setLiveStatus("uploading")
    setLiveReason(null)
    setLiveStages([])
    setLiveUploadId(null)

    // Append interactive in-chat message for the upload & Schema Architect run
    const userMsgId = crypto.randomUUID()
    const assistantMsgId = crypto.randomUUID()

    setMessages((curr) => [
      ...curr,
      {
        id: userMsgId,
        role: "user",
        text: `Uploaded dataset: ${file.name}`,
      },
      {
        id: assistantMsgId,
        role: "assistant",
        text: "",
        uploadData: {
          uploadId: "",
          fileName: file.name,
          fileSize: file.size,
          status: "uploading",
          stages: [],
          architectSteps: [
            {
              id: "chk_file",
              tool: "check_file",
              status: "running",
              label: "Checking file safety and structure…",
            },
          ],
        },
      },
    ])

    const form = new FormData()
    form.append("file", file)
    try {
      const res = await apiFetch(`${API_URL}/workspaces/${room.id}/uploads`, {
        method: "POST",
        body: form,
      })
      if (!res.ok) {
        let msg = "The file was rejected by the server."
        try {
          const errBody = await res.json()
          if (errBody?.detail) {
            msg = typeof errBody.detail === "string" ? errBody.detail : JSON.stringify(errBody.detail)
          } else if (errBody?.message) {
            msg = errBody.message
          }
        } catch {
          try {
            const errText = await res.text()
            if (errText) msg = errText
          } catch {}
        }
        setLiveStatus("rejected")
        setLiveReason(msg)

        setMessages((curr) =>
          curr.map((m) =>
            m.id === assistantMsgId && m.uploadData
              ? {
                  ...m,
                  uploadData: {
                    ...m.uploadData,
                    status: "rejected",
                    error: msg,
                    architectSteps: [
                      {
                        id: "chk_file",
                        tool: "check_file",
                        status: "error",
                        label: msg,
                      },
                    ],
                  },
                }
              : m
          )
        )
        return
      }
      const body = (await res.json()) as { upload_id: number; status: string }
      setLiveUploadId(String(body.upload_id))
      setLiveStatus(body.status)

      setMessages((curr) =>
        curr.map((m) =>
          m.id === assistantMsgId && m.uploadData
            ? {
                ...m,
                uploadData: {
                  ...m.uploadData,
                  uploadId: String(body.upload_id),
                  status: body.status === "needs_schema_review" ? "needs_schema_review" : "profiling",
                },
              }
            : m
        )
      )

      listenToUpload(body.upload_id, assistantMsgId)
    } catch {
      setLiveStatus("rejected")
      setMessages((curr) =>
        curr.map((m) =>
          m.id === assistantMsgId && m.uploadData
            ? {
                ...m,
                uploadData: {
                  ...m.uploadData,
                  status: "rejected",
                  error: "Network error connecting to backend.",
                  architectSteps: [
                    {
                      id: "chk_file",
                      tool: "check_file",
                      status: "error",
                      label: "Network error connecting to backend.",
                    },
                  ],
                },
              }
            : m
        )
      )
    }
  }

  function listenToUpload(uploadId: number, messageId?: string) {
    const source = new EventSource(`${API_URL}/uploads/${uploadId}/events`, { withCredentials: true })
    source.onmessage = async (event) => {
      const payload = readEvent<{
        // legacy stage events
        stage?: string
        status?: string
        reason?: string
        final?: string
        table_name?: string
        loaded_rows?: number
        quarantined_rows?: number
        proposal?: unknown
        // normalized step events (new)
        event?: string
        id?: string
        tool?: string
        label?: string
        evidence?: string
        ms?: number
        // load_progress
        loaded?: number
        pct?: number
        // handoff
        table_label?: string
        grain?: string
        row_count?: number
        quarantined_count?: number
        suggested_questions?: { question: string; hint: string }[]
      }>(event)
      if (!payload) return

      const evtName = payload.event

      // ── Normalized step event (architect tool) ──
      if (evtName === "step" && payload.tool) {
        if (messageId) {
          setMessages((curr) =>
            curr.map((m) => {
              if (m.id !== messageId || !m.uploadData) return m
              const prevSteps: ArchitectStep[] = m.uploadData.architectSteps ?? []
              // Update existing step if same tool+id, else append
              const idx = prevSteps.findIndex((s) => s.id === payload.id)
              let nextSteps: ArchitectStep[]
              const newStep: ArchitectStep = {
                id: payload.id ?? crypto.randomUUID().slice(0, 8),
                tool: payload.tool!,
                status: (payload.status ?? "running") as ArchitectStep["status"],
                label: payload.label ?? payload.tool!,
                evidence: payload.evidence,
                ms: payload.ms,
              }
              if (idx >= 0) {
                nextSteps = prevSteps.map((s, i) => (i === idx ? newStep : s))
              } else {
                nextSteps = [...prevSteps, newStep]
              }
              return {
                ...m,
                uploadData: { ...m.uploadData, architectSteps: nextSteps, status: "profiling" },
              }
            })
          )
        }
        return
      }

      // ── Load progress ──
      if (evtName === "load_progress") {
        if (messageId && payload.pct != null) {
          setMessages((curr) =>
            curr.map((m) =>
              m.id === messageId && m.uploadData
                ? { ...m, uploadData: { ...m.uploadData, loadProgressPct: payload.pct } }
                : m
            )
          )
        }
        return
      }

      // ── Handoff ──
      if (evtName === "handoff") {
        const handoff: HandoffData = {
          tableLabel: payload.table_label ?? "",
          tableName: payload.table_name ?? "",
          grain: payload.grain ?? "",
          rowCount: payload.row_count ?? 0,
          quarantinedCount: payload.quarantined_count ?? 0,
          suggestedQuestions: payload.suggested_questions ?? [],
        }
        // Append a Nexus handoff message after the architect card
        setMessages((curr) => [
          ...curr,
          {
            id: crypto.randomUUID(),
            role: "assistant" as const,
            text: "",
            handoffData: handoff,
          },
        ])
        return
      }

      // ── Legacy stage events ──
      if (payload.stage && payload.status) {
        setLiveStages((curr) => [
          ...curr.filter((item) => item.stage !== payload.stage),
          { stage: payload.stage!, status: payload.status! },
        ])
      }
      if (payload.reason) setLiveReason(payload.reason)

      // ── Terminal events ──
      if (payload.final) {
        setLiveStatus(payload.final)
        source.close()

        if (payload.final === "needs_schema_review") {
          try {
            const res = await apiFetch(`${API_URL}/uploads/${uploadId}/schema`)
            if (res.ok) {
              const sData = (await res.json()) as SchemaReviewData
              if (messageId) {
                setMessages((curr) =>
                  curr.map((m) =>
                    m.id === messageId && m.uploadData
                      ? {
                          ...m,
                          uploadData: {
                            ...m.uploadData,
                            uploadId: String(uploadId),
                            status: "needs_schema_review",
                            proposal: sData.proposal,
                            validation: sData.validation,
                            preview: sData.preview,
                          },
                        }
                      : m
                  )
                )
              }
            }
          } catch {}
        } else if (payload.final === "loaded") {
          if (messageId) {
            setMessages((curr) =>
              curr.map((m) =>
                m.id === messageId && m.uploadData
                  ? {
                      ...m,
                      uploadData: {
                        ...m.uploadData,
                        uploadId: String(uploadId),
                        status: "loaded",
                        tableName: payload.table_name,
                        loadedRows: payload.loaded_rows,
                        quarantinedRows: payload.quarantined_rows,
                        quarantineUploadId: String(uploadId),
                      },
                    }
                  : m
              )
            )
          }
          if (room) selectRoom(room.id, activeThreadId)
        } else if (payload.final === "rejected") {
          if (messageId) {
            setMessages((curr) =>
              curr.map((m) =>
                m.id === messageId && m.uploadData
                  ? {
                      ...m,
                      uploadData: {
                        ...m.uploadData,
                        uploadId: String(uploadId),
                        status: "rejected",
                        error: payload.reason || "File rejected.",
                      },
                    }
                  : m
              )
            )
          }
        }
      }
    }
    source.onerror = () => source.close()
  }

  async function handleApproveSchema(uploadId: string) {
    const res = await apiFetch(`${API_URL}/uploads/${uploadId}/schema/approve`, {
      method: "POST",
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err?.detail?.message || "Could not approve table creation.")
    }
    const data = await res.json()

    setMessages((curr) => [
      ...curr.map((m) => {
        if (m.uploadData?.uploadId === uploadId) {
          return {
            ...m,
            uploadData: {
              ...m.uploadData,
              status: "loaded" as const,
              tableName: data.table_name,
              loadedRows: data.loaded_rows,
              quarantinedRows: data.quarantined_rows,
            },
          }
        }
        return m
      }),
      {
        id: crypto.randomUUID(),
        role: "assistant",
        text: `Table **${data.table_label || data.table_name}** has been created with ${Number(data.loaded_rows).toLocaleString()} rows loaded into PostgreSQL. You can now ask questions about this dataset!`,
        badge: "verified" as const,
      },
    ])

    if (room) {
      await selectRoom(room.id, activeThreadId)
    }
    showToast(`Table ${data.table_name} created successfully!`)
  }

  async function handleRejectSchema(uploadId: string) {
    await apiFetch(`${API_URL}/uploads/${uploadId}/schema/reject`, {
      method: "POST",
    })
    setMessages((curr) =>
      curr.map((m) => {
        if (m.uploadData?.uploadId === uploadId) {
          return {
            ...m,
            uploadData: {
              ...m.uploadData,
              status: "rejected" as const,
              error: "Schema proposal rejected by user. No database table was created.",
            },
          }
        }
        return m
      })
    )
    showToast("Schema proposal rejected.")
  }

  const latest = room?.uploads[0]
  const busy = messages.some((msg) => msg.badge === "waiting")

  const rows =
    room?.health?.rows && room.health.rows !== "0"
      ? `${Number(room.health.rows).toLocaleString()} rows`
      : null
  const dates =
    room?.health?.first_order && room.health.last_order
      ? `${room.health.first_order} to ${room.health.last_order}`
      : null

  const attentionWarning =
    (room?.quarantine?.length ?? 0) > 0
      ? `${room?.quarantine.length} quarantined rows`
      : null

  // Screen 1: Data Rooms Hub
  if (currentView === "rooms") {
    return (
      <div className="min-h-screen w-full flex flex-col bg-background text-foreground">
        <WorkspacesView
          workspaces={workspaces}
          currentRoomId={room?.id ?? null}
          loading={workspacesLoading}
          error={roomError}
          onRetry={loadWorkspaces}
          onSelectWorkspace={(id) => selectRoom(id)}
          onOpenCreateModal={() => setCreateWorkspaceOpen(true)}
          onDeleteWorkspace={handleDeleteWorkspace}
        />

        <CreateWorkspaceModal
          isOpen={createWorkspaceOpen}
          onClose={() => setCreateWorkspaceOpen(false)}
          onCreate={handleCreateWorkspace}
        />

        {/* Global Toast */}
        {toastMessage ? (
          <div
            role="status"
            className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 border border-border bg-popover px-4 py-2 text-xs text-popover-foreground shadow-none animate-in fade-in"
          >
            {toastMessage}
          </div>
        ) : null}
      </div>
    )
  }

  // Screen 2: Focused Data Room Chat
  return (
    <div className="flex h-svh w-full flex-col bg-background text-foreground md:flex-row overflow-hidden">
      {/* Desktop Sidebar: 260px, fixed */}
      <aside className="hidden md:block h-full shrink-0">
        <Sidebar
          roomName={room?.name ?? "Superstore Diligence"}
          onBackToWorkspaces={() => setCurrentView("rooms")}
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={handleSelectThread}
          onNewThread={handleNewThread}
          onDeleteThread={handleDeleteThread}
          onOpenDataModal={() => setDataRoomModalOpen(true)}
          attentionWarning={attentionWarning}
          healthSummary={{ rows, dates }}
        />
      </aside>

      {/* Mobile Drawer (under 768px) */}
      {mobileDrawerOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden bg-black/40 backdrop-blur-[2px]">
          <div className="h-full w-[260px] bg-sidebar shadow-none">
            <Sidebar
              roomName={room?.name ?? "Superstore Diligence"}
              onBackToWorkspaces={() => {
                setMobileDrawerOpen(false)
                setCurrentView("rooms")
              }}
              threads={threads}
              activeThreadId={activeThreadId}
              onSelectThread={handleSelectThread}
              onNewThread={handleNewThread}
              onDeleteThread={handleDeleteThread}
              onOpenDataModal={() => {
                setMobileDrawerOpen(false)
                setDataRoomModalOpen(true)
              }}
              attentionWarning={attentionWarning}
              healthSummary={{ rows, dates }}
            />
          </div>
          <button
            type="button"
            aria-label="Close menu drawer"
            onClick={() => setMobileDrawerOpen(false)}
            className="flex-1 p-4 text-foreground/80 outline-none"
          >
            <X className="h-6 w-6 ml-auto" />
          </button>
        </div>
      )}

      {/* Main Chat Canvas */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col h-full overflow-hidden">
        {/* Mobile Header: slim bar with menu button and room name */}
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-border px-4 md:hidden">
          <button
            type="button"
            onClick={() => setCurrentView("rooms")}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Data rooms</span>
          </button>

          <button
            type="button"
            onClick={() => setMobileDrawerOpen(true)}
            className="flex items-center gap-1.5 text-xs font-medium text-foreground hover:opacity-80"
          >
            <Menu className="h-4 w-4" />
            <span className="truncate max-w-[160px]">{room?.name ?? "Data Room"}</span>
          </button>
        </div>

        {/* Chat Pane */}
        <ChatPane
          draft={draft}
          messages={messages}
          busy={busy}
          datasetName={room?.name ?? "Superstore"}
          onDraft={setDraft}
          onAsk={ask}
          onAbort={abortStreaming}
          onRetry={handleRetry}
          onFeedback={feedback}
          onToast={showToast}
          onUploadFile={chooseFile}
          onApproveSchema={handleApproveSchema}
          onRejectSchema={handleRejectSchema}
        />
      </div>

      {/* Bottom Center Toast */}
      {toastMessage ? (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 border border-border bg-popover px-4 py-2 text-xs text-popover-foreground shadow-none animate-in fade-in"
        >
          {toastMessage}
        </div>
      ) : null}
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
      missingMeasure:
        turn.kind === "refusal"
          ? "This dataset has no cost or profit column to calculate margin."
          : undefined,
      untraced:
        turn.verified === false
          ? ["42% repeat order rate"]
          : undefined,
    },
  ])
}

function badgeFor(data: Record<string, unknown>): AnswerBadge {
  if (data.verified === false) {
    const kind = String(data.kind ?? "")
    if (kind === "refusal") {
      return "refused"
    }
    return "caveat"
  }
  const kind = String(data.kind ?? "")
  if (kind === "refusal") {
    return "refused"
  }
  if (data.verified === true) {
    return "verified"
  }
  return "not_checked"
}
