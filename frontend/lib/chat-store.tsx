"use client"

import React, { createContext, useContext, useSyncExternalStore, useCallback } from "react"
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
      steps: turn.steps ?? [],
      missingMeasure: (turn.checker_result?.missing_measure as string) || undefined,
      untraced: (turn.checker_result?.untraced as string[]) || undefined,
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
  if (kind === "sql" || data.verified === true) {
    return "verified"
  }
  return "unanswered"
}
