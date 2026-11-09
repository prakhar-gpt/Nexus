import { showToast } from "./toast"

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export type Mapping = {
  source: string
  canonical: string | null
  confidence: number
  method: string
  needs_confirmation: boolean
  confirmed_by_user: boolean
}

export type Dataset = {
  id: string | number
  upload_id?: string | number | null
  table_name: string
  table_label: string
  grain: string
  row_count: number
  quarantine_count: number
  created_at: string
}

export type Thread = {
  id: string
  title: string
  created_at: string
  turn_count: number
  selected_dataset_ids?: (string | number)[]
}

export type WorkspaceSummary = {
  id: string | number
  name: string
  created_at: string
  upload_count?: string | number
  run_count?: string | number
}

export type Room = {
  id: string | number
  name: string
  uploads: { id: string; original_name: string; status: string }[]
  datasets?: Dataset[]
  health: {
    rows: string
    first_order: string
    last_order: string
    revenue: string
    quarantine: string
  }
  quarantine: { row_number: string; reason: string; raw_value?: string }[]
  mappings: Mapping[]
  threads?: Thread[]
  turns?: Turn[]
}

export type Turn = {
  run_id: string | number
  question: string
  answer: string
  sql: string | null
  kind: string | null
  verified: boolean | null
  rows: Record<string, string>[]
  thread_id?: string
  steps?: TraceStep[]
  tools_used?: string[]
  python_results?: Array<{ label: string; value: unknown }>
  checker_result?: {
    untraced?: string[]
    missing_measure?: string
    [key: string]: unknown
  }
}

export type TraceStep = {
  id?: string
  tool: string
  status: string
  ms?: number
  detail?: string
  query?: string | null
  row_count?: number
  input?: Record<string, unknown> | string | null
  output?: string | null
}

// Registry for 401 unauthenticated cleanup (cache, chat-store, etc.)
const unauthorizedCleanups = new Set<() => void>()

export function registerUnauthorizedCleanup(fn: () => void): () => void {
  unauthorizedCleanups.add(fn)
  return () => unauthorizedCleanups.delete(fn)
}

/**
 * Universal fetch wrapper that handles 401 Unauthorized by clearing session,
 * caches, and chat store, showing a toast, and redirecting to /login?next=...
 * Automatically ensures credentials: "include" and custom state-changing headers.
 */
export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const token = typeof window !== "undefined" ? localStorage.getItem("nexus_token") : null

  const mergedHeaders: Record<string, string> = {
    "X-Requested-With": "XMLHttpRequest",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((init?.headers as Record<string, string>) || {}),
  }

  const mergedInit: RequestInit = {
    ...init,
    credentials: init?.credentials || "include",
    headers: mergedHeaders,
  }

  const response = await fetch(input, mergedInit)

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      try {
        localStorage.removeItem("nexus_session")
        localStorage.removeItem("nexus_user")
        localStorage.removeItem("nexus_token")
        document.cookie = "nexus_session=; path=/; max-age=0; SameSite=Lax"
      } catch {}

      // Run registered cleanups (cache, chat-store)
      unauthorizedCleanups.forEach((cleanup) => {
        try {
          cleanup()
        } catch {}
      })

      // Only redirect if not already on public auth pages
      if (!window.location.pathname.startsWith("/login") && !window.location.pathname.startsWith("/signup") && window.location.pathname !== "/") {
        showToast("Session expired. Sign in again.")
        const currentPath = window.location.pathname + window.location.search
        const nextParam = encodeURIComponent(currentPath)
        window.location.href = `/login?next=${nextParam}`
      }
    }
  }

  return response
}

export async function readSse(
  response: Response,
  onEvent: (event: string, data: Record<string, unknown>) => void,
) {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error("The response has no stream.")
  }
  const decoder = new TextDecoder()
  let buffer = ""
  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split("\n\n")
    buffer = parts.pop() ?? ""
    for (const part of parts) {
      let event = "message"
      const dataLines: string[] = []
      for (const line of part.split("\n")) {
        if (line.startsWith("event:")) {
          event = line.slice(6).trim()
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trim())
        }
      }
      if (dataLines.length > 0) {
        try {
          onEvent(event, JSON.parse(dataLines.join("\n")) as Record<string, unknown>)
        } catch {
          onEvent("error", {})
        }
      }
    }
  }
}


export type ColumnProposal = {
  source_name: string
  column_name: string
  type: "text" | "integer" | "numeric" | "date" | "boolean"
  role: "identifier" | "date" | "measure" | "dimension" | "other"
  description: string
  unit: string | null
  nullable: boolean
  date_format: string | null
  parse_success_rate: number
  confidence: number
  notes: string | null
  excluded?: boolean
}

export type SchemaProposal = {
  table_label: string
  grain: string
  grain_key_columns: string[]
  columns: ColumnProposal[]
  warnings: string[]
  analysis_hints: string[]
  from_cache?: boolean
}

export type ValidationIssue = {
  level: "error" | "warning"
  field?: string
  column_name?: string
  message: string
}

export type ValidationResult = {
  is_valid: boolean
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
}

export type SchemaReviewData = {
  upload_id: string | number
  workspace_id: string | number
  status: string
  table_name: string
  proposal: SchemaProposal
  validation: ValidationResult
  preview: Record<string, string>[]
}

export type ArchitectStep = {
  id: string
  tool: string
  status: "running" | "done" | "error"
  label: string
  evidence?: string
  ms?: number
}

export type HandoffSuggestedQuestion = {
  question: string
  hint: string
}

export type HandoffData = {
  tableLabel: string
  tableName: string
  grain: string
  rowCount: number
  quarantinedCount: number
  suggestedQuestions: HandoffSuggestedQuestion[]
}

export type UploadMessageData = {
  uploadId: string
  fileName: string
  fileSize?: number
  status: "uploading" | "profiling" | "needs_schema_review" | "loaded" | "rejected"
  stages: { stage: string; status: string; reason?: string }[]
  /** New: normalized live steps list (replaces liveTrace for architect flow) */
  architectSteps?: ArchitectStep[]
  /** Legacy trace lines kept for backwards compat during rehydration */
  liveTrace?: string[]
  proposal?: SchemaProposal
  validation?: ValidationResult
  preview?: Record<string, string>[]
  tableName?: string
  loadedRows?: number
  quarantinedRows?: number
  quarantineUploadId?: string
  loadProgressPct?: number
  error?: string | null
  handoff?: HandoffData
}
