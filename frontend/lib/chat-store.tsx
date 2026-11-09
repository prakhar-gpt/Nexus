"use client"

import React, { createContext, useContext, useSyncExternalStore, useCallback } from "react"
import { mutateResource } from "./use-resource"
import {
  API_URL,
  apiFetch,
  readSse,
  registerUnauthorizedCleanup,
  type TraceStep,
  type Turn,
} from "./api"
import type { ChatMessage, AnswerBadge } from "@/components/chat-pane"

export interface ThreadState {
  messages: ChatMessage[]
  busy: boolean
  draft: string
}

const DEFAULT_THREAD_STATE: ThreadState = {
  messages: [],
  busy: false,
  draft: "",
}

// Global external store mapping "roomId:threadId" -> ThreadState
const threadStates = new Map<string, ThreadState>()
const keyListeners = new Map<string, Set<() => void>>()
const abortControllers = new Map<string, AbortController>()

function makeKey(roomId: string | number, threadId: string) {
  return `${roomId}:${threadId}`
}

function notifyKey(key: string) {
  const subs = keyListeners.get(key)
  if (subs) {
    subs.forEach((cb) => cb())
  }
}

export function subscribeThreadKey(key: string, callback: () => void): () => void {
  if (!keyListeners.has(key)) {
    keyListeners.set(key, new Set())
  }
  const set = keyListeners.get(key)!
  set.add(callback)
  return () => {
    set.delete(callback)
    if (set.size === 0) {
      keyListeners.delete(key)
    }
  }
}

export function getThreadStateDirect(roomId: string | number, threadId: string): ThreadState {
  const key = makeKey(roomId, threadId)
  return threadStates.get(key) || DEFAULT_THREAD_STATE
}

export function useThreadState(roomId: string | number, threadId: string): ThreadState {
  const key = makeKey(roomId, threadId)
  return useSyncExternalStore(
    (onStoreChange) => subscribeThreadKey(key, onStoreChange),
    () => threadStates.get(key) || DEFAULT_THREAD_STATE,
    () => DEFAULT_THREAD_STATE
  )
}

export function clearChatStore() {
  abortControllers.forEach((ctrl) => ctrl.abort())
  abortControllers.clear()
  threadStates.clear()
  keyListeners.forEach((subs) => {
    subs.forEach((cb) => cb())
  })
}

// Auto-register with apiFetch 401 handler
registerUnauthorizedCleanup(clearChatStore)

interface ChatStoreContextType {
  getThreadState: (roomId: string | number, threadId: string) => ThreadState
  useThread: (roomId: string | number, threadId: string) => ThreadState
  setDraft: (roomId: string | number, threadId: string, draft: string) => void
  setMessages: (roomId: string | number, threadId: string, messages: ChatMessage[]) => void
  initThreadTurns: (roomId: string | number, threadId: string, turns: Turn[]) => void
  ask: (
    roomId: string | number,
    threadId: string,
    question: string,
    onFirstToken?: (targetThreadId: string) => void
  ) => Promise<void>
  uploadFile: (
    roomId: string | number,
    threadId: string,
    file: File,
    onNavigate?: (targetThreadId: string) => void
  ) => Promise<void>
  approveSchema: (
    roomId: string | number,
    threadId: string,
    uploadId: string
  ) => Promise<void>
  rejectSchema: (
    roomId: string | number,
    threadId: string,
    uploadId: string
  ) => Promise<void>
  rehydrateUpload: (
    roomId: string | number,
    threadId: string,
    upload: { id: string | number; original_name: string; status: string }
  ) => Promise<void>
  abortStream: (roomId: string | number, threadId: string) => void
  recordFeedback: (
    runId: number,
    rating: "up" | "down",
    reason?: string
  ) => Promise<boolean>
  clearAll: () => void
}

const ChatStoreContext = createContext<ChatStoreContextType | undefined>(undefined)

export function ChatStoreProvider({ children }: { children: React.ReactNode }) {
  const getThreadState = useCallback((roomId: string | number, threadId: string): ThreadState => {
    return getThreadStateDirect(roomId, threadId)
  }, [])

  const setDraft = useCallback((roomId: string | number, threadId: string, draft: string) => {
    const key = makeKey(roomId, threadId)
    const prev = threadStates.get(key) || DEFAULT_THREAD_STATE
    threadStates.set(key, { ...prev, draft })
    notifyKey(key)
  }, [])

  const setMessages = useCallback(
    (roomId: string | number, threadId: string, messages: ChatMessage[]) => {
      const key = makeKey(roomId, threadId)
      const prev = threadStates.get(key) || DEFAULT_THREAD_STATE
      threadStates.set(key, { ...prev, messages })
      notifyKey(key)
    },
    []
  )

  const initThreadTurns = useCallback(
    (roomId: string | number, threadId: string, turns: Turn[]) => {
      const key = makeKey(roomId, threadId)
      const prev = threadStates.get(key)
      if (prev && prev.messages.length > 0) return
      threadStates.set(key, {
        draft: prev?.draft || "",
        busy: false,
        messages: turnsToMessages(turns),
      })
      notifyKey(key)
    },
    []
  )

  const abortStream = useCallback((roomId: string | number, threadId: string) => {
    const key = makeKey(roomId, threadId)
    const ctrl = abortControllers.get(key)
    if (ctrl) {
      ctrl.abort()
      abortControllers.delete(key)
    }
    const curr = threadStates.get(key)
    if (!curr) return
    const updatedMessages = curr.messages.map((m, idx) =>
      idx === curr.messages.length - 1 && m.role === "assistant" && m.badge === "waiting"
        ? { ...m, badge: "stopped" as AnswerBadge, streamDropped: false, activity: [] }
        : m
    )
    threadStates.set(key, {
      ...curr,
      busy: false,
      messages: updatedMessages,
    })
    notifyKey(key)
  }, [])

  const ask = useCallback(
    async (
      roomId: string | number,
      threadId: string,
      question: string,
      onFirstToken?: (targetThreadId: string) => void
    ) => {
      const text = question.trim()
      if (!text) return

      const key = makeKey(roomId, threadId)
      const assistantId = crypto.randomUUID()

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        text,
      }
      const pendingAssistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        text: "",
        badge: "waiting",
        sql: null,
        rowCount: null,
        runId: null,
        rows: [],
      }

      const prev = threadStates.get(key) || DEFAULT_THREAD_STATE
      threadStates.set(key, {
        ...prev,
        draft: "",
        busy: true,
        messages: [...prev.messages, userMsg, pendingAssistantMsg],
      })
      notifyKey(key)

      const controller = new AbortController()
      abortControllers.set(key, controller)

      let finished = false
      let streamText = ""
      let notifiedFirstToken = false

      const updateAssistant = (patch: Partial<ChatMessage>) => {
        const curr = threadStates.get(key)
        if (!curr) return
        threadStates.set(key, {
          ...curr,
          messages: curr.messages.map((m) =>
            m.id === assistantId ? { ...m, ...patch } : m
          ),
        })
        notifyKey(key)
      }

      try {
        const response = await apiFetch(`${API_URL}/workspaces/${roomId}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: text, thread_id: threadId }),
          signal: controller.signal,
        })

        if (!response.ok) {
          let errorMsg = "The request failed on the server."
          try {
            const errorBody = await response.json()
            if (errorBody?.detail) {
              errorMsg =
                typeof errorBody.detail === "string"
                  ? errorBody.detail
                  : JSON.stringify(errorBody.detail)
            } else if (errorBody?.message) {
              errorMsg = errorBody.message
            }
          } catch {
            try {
              const textBody = await response.text()
              if (textBody) errorMsg = textBody
            } catch {}
          }
          throw new Error(errorMsg)
        }

        await readSse(response, (event, data) => {
          if (event === "token") {
            const chunk = String(data.text ?? "")
            if (chunk) {
              streamText += chunk
              updateAssistant({ text: streamText, activity: [] })
              if (!notifiedFirstToken) {
                notifiedFirstToken = true
                onFirstToken?.(threadId)
              }
            }
          } else if (event === "step") {
            const step = data as unknown as TraceStep
            updateAssistant({ activity: [step] })
          } else if (event === "sql") {
            updateAssistant({
              sql: (data.query as string) || null,
              rowCount: Number(data.row_count ?? 0),
            })
          } else if (event === "source") {
            updateAssistant({
              sources: [
                {
                  document: String(data.document || "Document"),
                  page: (data.page as number | string) || undefined,
                },
              ],
            })
          } else if (event === "check") {
            updateAssistant({
              badge: badgeFor(data),
              untraced: (data.untraced as string[]) || undefined,
              missingMeasure: (data.missing_measure as string) || undefined,
            })
          } else if (event === "done") {
            finished = true
            updateAssistant({
              text: (data.answer as string) || streamText,
              runId: data.run_id != null ? Number(data.run_id) : null,
              rows: (data.rows as Record<string, string>[]) ?? [],
              steps: (data.steps as TraceStep[]) ?? [],
              activity: [],
            })
            if (!notifiedFirstToken) {
              onFirstToken?.(threadId)
            }
          } else if (event === "error") {
            const serverMsg =
              (data?.error as string) ||
              (data?.message as string) ||
              (data?.detail as string) ||
              "The model could not answer this query."
            updateAssistant({
              error: serverMsg,
              badge: "refused",
              activity: [],
            })
          }
        })
      } catch (err: any) {
        if (err.name === "AbortError") {
          updateAssistant({
            badge: "stopped",
            activity: [],
          })
        } else {
          updateAssistant({
            streamDropped: true,
            error: err?.message || "Connection lost while streaming.",
            badge: "refused",
            activity: [],
          })
        }
      } finally {
        abortControllers.delete(key)
        const curr = threadStates.get(key)
        if (curr) {
          threadStates.set(key, {
            ...curr,
            busy: false,
            messages: curr.messages.map((m) =>
              m.id === assistantId && !finished ? { ...m, activity: [] } : m
            ),
          })
          notifyKey(key)
        }
      }
    },
    []
  )

  const uploadFile = useCallback(
    async (
      roomId: string | number,
      threadId: string,
      file: File,
      onNavigate?: (targetThreadId: string) => void
    ) => {
      const key = makeKey(roomId, threadId)
      const userMsgId = crypto.randomUUID()
      const assistantMsgId = crypto.randomUUID()

      // Format file size nicely
      const sizeStr = file.size > 1024 * 1024
        ? `${(file.size / (1024 * 1024)).toFixed(1)} MB`
        : `${Math.round(file.size / 1024)} KB`

      // 1. Instantly display user file message & assistant Schema Architect step
      const userMsg: ChatMessage = {
        id: userMsgId,
        role: "user",
        text: `Uploaded dataset: ${file.name} (${sizeStr})`,
      }

      const architectMsg: ChatMessage = {
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
              id: "step_received",
              tool: "check_file",
              status: "running",
              label: `Reading ${file.name}…`,
            },
          ],
        },
      }

      const prev = threadStates.get(key) || DEFAULT_THREAD_STATE
      threadStates.set(key, {
        ...prev,
        busy: true,
        messages: [...prev.messages, userMsg, architectMsg],
      })
      notifyKey(key)

      if (onNavigate) {
        onNavigate(threadId)
      }

      const updateUploadData = (updater: (prevData: any) => any) => {
        const curr = threadStates.get(key)
        if (!curr) return
        threadStates.set(key, {
          ...curr,
          messages: curr.messages.map((m) =>
            m.id === assistantMsgId && m.uploadData
              ? { ...m, uploadData: updater(m.uploadData) }
              : m
          ),
        })
        notifyKey(key)
      }

      try {
        const form = new FormData()
        form.append("file", file)

        const res = await apiFetch(`${API_URL}/workspaces/${roomId}/uploads`, {
          method: "POST",
          body: form,
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          const msg = err?.detail || err?.message || "File rejected by server."
          updateUploadData((u) => ({
            ...u,
            status: "rejected",
            error: msg,
            architectSteps: [
              { id: "err", tool: "check_file", status: "error", label: msg },
            ],
          }))
          return
        }

        const body = (await res.json()) as { upload_id: number; status: string }
        const uploadId = body.upload_id

        updateUploadData((u) => ({
          ...u,
          uploadId: String(uploadId),
          status: body.status === "needs_schema_review" ? "needs_schema_review" : "profiling",
        }))

        // Listen to live SSE upload events
        const source = new EventSource(`${API_URL}/uploads/${uploadId}/events`)

        const handleSseMessage = async (evt: MessageEvent) => {
          if (!evt.data) return
          let payload: any = {}
          try {
            payload = JSON.parse(evt.data)
          } catch {
            return
          }

          const evtName = payload.event || (evt as any).type

          // Normal architect / Nexus tool steps
          if (payload.tool || evtName === "step") {
            updateUploadData((u) => {
              const prevSteps = u.architectSteps || []
              const stepId = payload.id || `step_${payload.tool || payload.seq || Math.random()}`
              const idx = prevSteps.findIndex((s: any) => s.id === stepId || s.tool === payload.tool)
              const newStep = {
                id: stepId,
                tool: payload.tool || "check_file",
                status: payload.status || "done",
                label: payload.label || payload.tool || "Processed step",
                evidence: payload.evidence,
                ms: payload.ms,
              }
              const nextSteps = idx >= 0
                ? prevSteps.map((s: any, i: number) => (i === idx ? newStep : s))
                : [...prevSteps, newStep]
              return { ...u, architectSteps: nextSteps, status: "profiling" }
            })
          }

          // Handoff event
          if (evtName === "handoff" || payload.event === "handoff") {
            const curr = threadStates.get(key)
            const uploadMsg = curr?.messages.find((m: any) => m.uploadData)
            const rawFileName = uploadMsg?.uploadData?.fileName?.replace(/\.[^/.]+$/, "") || ""
            const cleanFileLabel = rawFileName
              ? rawFileName.replace(/[_-]/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())
              : ""

            let tblLabel = payload.table_label || ""
            if (cleanFileLabel && (!tblLabel || /^[0-9a-fA-F]{12,}$/.test(tblLabel) || /^ds_\d+$/i.test(tblLabel) || tblLabel.toLowerCase() === "custom dataset")) {
              tblLabel = cleanFileLabel
            }

            const handoffData = {
              tableLabel: tblLabel || cleanFileLabel || "Dataset",
              tableName: payload.table_name || "",
              grain: payload.grain || "",
              rowCount: payload.row_count || 0,
              quarantinedCount: payload.quarantined_count || 0,
              suggestedQuestions: payload.suggested_questions || [],
            }
            if (curr) {
              threadStates.set(key, {
                ...curr,
                messages: [
                  ...curr.messages,
                  {
                    id: crypto.randomUUID(),
                    role: "assistant",
                    text: "",
                    handoffData,
                  },
                ],
              })
              notifyKey(key)
            }
            return
          }

          // Terminal events or proposal ready
          if (payload.final || evtName === "done" || evtName === "architect_proposed" || payload.status === "needs_schema_review") {
            const finalState = payload.final || payload.status
            if (finalState === "needs_schema_review" || evtName === "architect_proposed" || payload.proposal) {
              try {
                const schemaRes = await apiFetch(`${API_URL}/uploads/${uploadId}/schema`)
                if (schemaRes.ok) {
                  const sData = await schemaRes.json()
                  updateUploadData((u) => ({
                    ...u,
                    status: "needs_schema_review",
                    proposal: sData.proposal || payload.proposal,
                    validation: sData.validation || payload.validation,
                    preview: sData.preview || payload.preview,
                  }))
                }
              } catch {}
            } else if (finalState === "loaded") {
              source.close()
              updateUploadData((u) => ({
                ...u,
                status: "loaded",
                tableName: payload.table_name,
                loadedRows: payload.loaded_rows,
                quarantinedRows: payload.quarantined_rows,
                quarantineUploadId: String(uploadId),
              }))
            } else if (finalState === "rejected") {
              source.close()
              updateUploadData((u) => ({
                ...u,
                status: "rejected",
                error: payload.reason || "File rejected.",
              }))
            }
          }
        }

        source.onmessage = handleSseMessage
        source.addEventListener("step", handleSseMessage)
        source.addEventListener("done", handleSseMessage)
        source.addEventListener("error", handleSseMessage)
        source.addEventListener("handoff", handleSseMessage)
        source.addEventListener("architect_proposed", handleSseMessage)
        source.addEventListener("architect_started", handleSseMessage)
        source.addEventListener("progress", handleSseMessage)

        source.onerror = () => source.close()
      } catch (err: any) {
        updateUploadData((u) => ({
          ...u,
          status: "rejected",
          error: err?.message || "Failed to upload file.",
        }))
      } finally {
        const curr = threadStates.get(key)
        if (curr) {
          threadStates.set(key, { ...curr, busy: false })
          notifyKey(key)
        }
      }
    },
    []
  )

  const approveSchema = useCallback(
    async (roomId: string | number, threadId: string, uploadId: string) => {
      const key = makeKey(roomId, threadId)
      const res = await apiFetch(
        `${API_URL}/uploads/${uploadId}/schema/approve?thread_id=${encodeURIComponent(threadId)}`,
        { method: "POST" }
      )
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.detail?.message || err?.detail || "Could not approve table creation.")
      }
      const data = await res.json()

      // Instantly update room datasets and upload status optimistically with zero network delay
      mutateResource(`room:${roomId}`, (curr: any) => {
        if (!curr) return curr
        const newDataset = {
          id: data.dataset_id || Number(uploadId),
          upload_id: Number(uploadId),
          table_name: data.table_name,
          table_label: data.table_label,
          grain: data.grain,
          row_count: data.loaded_rows,
          quarantine_count: data.quarantined_rows || 0,
          created_at: new Date().toISOString(),
        }
        const prevDatasets = (curr.datasets || []).filter((d: any) => d.table_name !== data.table_name)
        const updatedUploads = (curr.uploads || []).map((u: any) =>
          String(u.id) === String(uploadId) ? { ...u, status: "loaded" } : u
        )
        return {
          ...curr,
          uploads: updatedUploads,
          datasets: [...prevDatasets, newDataset],
          threads: (curr.threads || []).map((t: any) =>
            t.id === threadId
              ? {
                  ...t,
                  selected_dataset_ids: Array.from(
                    new Set([...(t.selected_dataset_ids || []), newDataset.id])
                  ),
                }
              : t
          ),
        }
      })

      // Immediately transition in-chat message to loaded state
      const curr = threadStates.get(key)
      if (curr) {
        const updatedMessages = curr.messages.map((m) => {
          if (m.uploadData && (m.uploadData.uploadId === uploadId || !m.uploadData.uploadId)) {
            return {
              ...m,
              uploadData: {
                ...m.uploadData,
                status: "loaded" as const,
                tableName: data.table_name,
                loadedRows: data.loaded_rows,
                quarantinedRows: data.quarantined_rows || 0,
                quarantineUploadId: uploadId,
              },
            }
          }
          return m
        })

        // Derive friendly dataset label and grain from proposal / file name
        const uploadMsg = curr.messages.find((m) => m.uploadData)
        const rawFileName = uploadMsg?.uploadData?.fileName?.replace(/\.[^/.]+$/, "") || ""
        const cleanFileLabel = rawFileName
          ? rawFileName.replace(/[_-]/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())
          : ""

        let friendlyLabel =
          data.table_label ||
          uploadMsg?.uploadData?.proposal?.table_label ||
          cleanFileLabel ||
          "Dataset"

        if (cleanFileLabel && (/^[0-9a-fA-F]{12,}$/.test(friendlyLabel) || /^ds_\d+$/i.test(friendlyLabel) || friendlyLabel.toLowerCase() === "custom dataset")) {
          friendlyLabel = cleanFileLabel
        }

        const rawGrain = data.grain || uploadMsg?.uploadData?.proposal?.grain || "transaction record"
        const cleanGrain = rawGrain
          .replace(/^[\s*#_-]*(?:grain|table grain|one row represents)[\s*#_:-]*/i, "")
          .trim()

        // Use backend-provided suggestions if available, or generate retail-prioritized suggestions
        let suggested = data.suggested_questions || []
        if (!suggested || suggested.length === 0) {
          const cols = uploadMsg?.uploadData?.proposal?.columns || []
          const nonMeasures = ["postal", "zip", "code", "phone", "fax", "ssn", "ein", "id", "nbr", "num"]
          const rawMeasures = cols
            .filter((c: any) => c.role === "measure" && !c.excluded && !nonMeasures.some((k) => c.column_name.toLowerCase().includes(k)))
            .map((c: any) => c.column_name)

          const rawDims = cols
            .filter((c: any) => c.role === "dimension" && !c.excluded)
            .map((c: any) => c.column_name)

          const rawDates = cols
            .filter((c: any) => c.role === "date" && !c.excluded)
            .map((c: any) => c.column_name)

          const PRIORITY_MEASURES = ["revenue", "sales", "profit", "amount", "spend", "cost", "total", "margin", "quantity", "units", "discount"]
          const PRIORITY_DIMS = ["category", "sub_category", "segment", "region", "channel", "department", "state", "brand", "country"]

          const sortPriority = (items: string[], priorities: string[]) => {
            return [...items].sort((a, b) => {
              const aIdx = priorities.findIndex((p) => a.toLowerCase().includes(p))
              const bIdx = priorities.findIndex((p) => b.toLowerCase().includes(p))
              if (aIdx >= 0 && bIdx >= 0) return aIdx - bIdx
              if (aIdx >= 0) return -1
              if (bIdx >= 0) return 1
              return a.localeCompare(b)
            })
          }

          const measureCols = sortPriority(rawMeasures, PRIORITY_MEASURES)
          const dimCols = sortPriority(rawDims, PRIORITY_DIMS)

          suggested = []
          if (measureCols.length > 0 && dimCols.length > 0) {
            const m = measureCols[0].replace(/_/g, " ")
            const d = dimCols[0].replace(/_/g, " ")
            suggested.push({
              question: `What is total ${m} by ${d}?`,
              hint: `Break down ${m} by ${d}`,
            })
          }
          if (measureCols.length > 0 && rawDates.length > 0) {
            const m = measureCols[0].replace(/_/g, " ")
            const dt = rawDates[0].replace(/_/g, " ")
            suggested.push({
              question: `Show ${m} over time by ${dt}`,
              hint: `${m} over time`,
            })
          } else if (measureCols.length > 0) {
            const m = measureCols[0].replace(/_/g, " ")
            suggested.push({
              question: `What is the overall sum and average of ${m}?`,
              hint: `Summary statistics for ${m}`,
            })
          }
          suggested.push({
            question: `How many rows are in ${friendlyLabel}?`,
            hint: `Count rows in ${friendlyLabel}`,
          })
        }

        const handoffMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          text: "",
          handoffData: {
            tableName: data.table_name,
            tableLabel: friendlyLabel,
            grain: cleanGrain,
            rowCount: data.loaded_rows,
            quarantinedCount: data.quarantined_rows || 0,
            suggestedQuestions: suggested,
          },
        }

        threadStates.set(key, {
          ...curr,
          messages: [...updatedMessages, handoffMessage],
        })
        notifyKey(key)
      }
      return data
    },
    []
  )

  const rejectSchema = useCallback(
    async (roomId: string | number, threadId: string, uploadId: string) => {
      await apiFetch(`${API_URL}/uploads/${uploadId}/schema/reject`, {
        method: "POST",
      })
    },
    []
  )

  const rehydrateUpload = useCallback(
    async (
      roomId: string | number,
      threadId: string,
      upload: { id: string | number; original_name: string; status: string }
    ) => {
      const key = makeKey(roomId, threadId)
      const curr = threadStates.get(key)
      if (curr?.messages.some((m) => m.uploadData?.uploadId === String(upload.id))) {
        return
      }

      const userMsgId = `upload-user-${upload.id}`
      const assistantMsgId = `upload-asst-${upload.id}`
      const userMsg: ChatMessage = {
        id: userMsgId,
        role: "user",
        text: `Uploaded dataset: ${upload.original_name}`,
      }

      let proposal = undefined
      let validation = undefined
      let preview = undefined

      if (upload.status === "needs_schema_review") {
        try {
          const res = await apiFetch(`${API_URL}/uploads/${upload.id}/schema`)
          if (res.ok) {
            const data = await res.json()
            proposal = data.proposal
            validation = data.validation
            preview = data.preview
          }
        } catch {}
      }

      const architectMsg: ChatMessage = {
        id: assistantMsgId,
        role: "assistant",
        text: "",
        uploadData: {
          uploadId: String(upload.id),
          fileName: upload.original_name,
          fileSize: 0,
          status: (upload.status === "needs_schema_review" ? "needs_schema_review" : "profiling") as any,
          stages: [],
          proposal,
          validation,
          preview,
          architectSteps: [
            { id: "s1", tool: "check_file", status: "done", label: `Checked ${upload.original_name}` },
            { id: "s2", tool: "read_types", status: "done", label: "Read column types and null rates" },
            { id: "s3", tool: "table_grain", status: "done", label: "Determined table grain" },
          ],
        },
      }

      const prev = threadStates.get(key) || DEFAULT_THREAD_STATE
      threadStates.set(key, {
        ...prev,
        busy: upload.status !== "needs_schema_review",
        messages: [userMsg, architectMsg, ...(prev?.messages || []).filter((m) => !m.uploadData)],
      })
      notifyKey(key)

      if (upload.status !== "needs_schema_review" && upload.status !== "loaded" && upload.status !== "rejected") {
        const source = new EventSource(`${API_URL}/uploads/${upload.id}/events`)
        source.onmessage = async (evt: MessageEvent) => {
          if (!evt.data) return
          let payload: any = {}
          try {
            payload = JSON.parse(evt.data)
          } catch {
            return
          }
          if (
            payload.status === "needs_schema_review" ||
            payload.event === "architect_proposed" ||
            payload.final === "needs_schema_review"
          ) {
            source.close()
            try {
              const res = await apiFetch(`${API_URL}/uploads/${upload.id}/schema`)
              if (res.ok) {
                const sData = await res.json()
                const cState = threadStates.get(key)
                if (cState) {
                  threadStates.set(key, {
                    ...cState,
                    busy: false,
                    messages: cState.messages.map((m) =>
                      m.id === assistantMsgId && m.uploadData
                        ? {
                            ...m,
                            uploadData: {
                              ...m.uploadData,
                              status: "needs_schema_review",
                              proposal: sData.proposal,
                              validation: sData.validation,
                              preview: sData.preview,
                            },
                          }
                        : m
                    ),
                  })
                  notifyKey(key)
                }
              }
            } catch {}
          }
        }
        source.onerror = () => source.close()
      }
    },
    []
  )

  const recordFeedback = useCallback(
    async (runId: number, rating: "up" | "down", reason?: string): Promise<boolean> => {
      try {
        const res = await apiFetch(`${API_URL}/runs/${runId}/feedback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rating, reason }),
        })
        if (!res.ok) throw new Error()
        return true
      } catch {
        return false
      }
    },
    []
  )

  const clearAll = useCallback(() => {
    clearChatStore()
  }, [])

  return (
    <ChatStoreContext.Provider
      value={{
        getThreadState,
        useThread: useThreadState,
        setDraft,
        setMessages,
        initThreadTurns,
        ask,
        uploadFile,
        approveSchema,
        rejectSchema,
        rehydrateUpload,
        abortStream,
        recordFeedback,
        clearAll,
      }}
    >
      {children}
    </ChatStoreContext.Provider>
  )
}

export function useChatStore() {
  const ctx = useContext(ChatStoreContext)
  if (!ctx) {
    throw new Error("useChatStore must be used within a ChatStoreProvider")
  }
  return ctx
}

function turnsToMessages(turns: Turn[]): ChatMessage[] {
  return turns.flatMap((turn) => {
    const cr = (turn.checker_result as any) || {}
    const isUploadHandoff =
      turn.kind === "upload" ||
      turn.question.startsWith("Uploaded dataset:") ||
      Boolean(cr.handoff_data)

    if (isUploadHandoff) {
      const handoff = cr.handoff_data || {
        tableLabel: cr.table_label || "Dataset",
        tableName: cr.table_name || "",
        grain: cr.grain || "",
        rowCount: Number(cr.row_count || 0),
        quarantinedCount: Number(cr.quarantined_count || 0),
        suggestedQuestions: cr.suggested_questions || [],
      }

      return [
        { id: `q-${turn.run_id}`, role: "user" as const, text: turn.question },
        {
          id: `a-${turn.run_id}`,
          role: "assistant" as const,
          text: turn.answer,
          handoffData: handoff,
        },
      ]
    }

    return [
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
        steps: turn.steps ?? [],
        missingMeasure: (turn.checker_result?.missing_measure as string) || undefined,
        untraced: (turn.checker_result?.untraced as string[]) || undefined,
      },
    ]
  })
}

function badgeFor(data: Record<string, unknown>): AnswerBadge {
  if (data.verified === false) {
    return "caveat"
  }
  const kind = String(data.kind ?? "")
  if (kind === "refusal") {
    return "refused"
  }
  if (kind === "sql" || data.verified === true) {
    return "verified"
  }
  return "unanswered"
}
