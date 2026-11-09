"use client"

/**
 * agent-steps.tsx
 *
 * Live step indicator matching Nexus Agent's ToolLine design pattern:
 * - While running/streaming: displays ONE single quiet pulsating tool label at a time.
 * - Subtle primary ping dot (animate-ping + animate-pulse), zero stacked clutter.
 * - Zero bright green checkmarks (clean, calm, defensible aesthetic).
 * - Once complete: displays a quiet, muted one-line summary with optional disclosure.
 */

import React, { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"

export type AgentStepStatus = "running" | "done" | "error" | "skipped"

export type AgentStep = {
  id: string
  /** Raw tool name from backend */
  tool: string
  status: AgentStepStatus
  /** Human-readable label */
  label: string
  /** Optional short evidence string */
  evidence?: string
  /** Duration in ms (shown when done) */
  ms?: number
}

// Map raw architect tool names to active present-continuous labels
const ACTIVE_TOOL_DESCRIPTIONS: Record<string, string> = {
  check_file:         "Checking file safety…",
  read_sheet:         "Reading file rows…",
  list_columns:       "Inspecting columns…",
  profile_columns:    "Profiling columns and types…",
  profile_column:     "Profiling column data…",
  test_parse:         "Testing data types…",
  detect_date_format: "Checking date formats…",
  check_uniqueness:   "Checking key uniqueness…",
  sample_rows:        "Sampling rows…",
  determine_grain:    "Determining table grain…",
  propose_schema:     "Synthesizing schema proposal…",
  create_table:       "Creating custom table…",
  load_rows:          "Loading dataset rows…",
  get_schema:         "Looking at the columns…",
  run_sql:            "Running a query…",
  read_kb:            "Reading knowledge base…",
  run_python:         "Running Python calculation…",
  checker:            "Verifying numbers…",
}

const PAST_TOOL_LABELS: Record<string, string> = {
  check_file:         "File safety verified",
  read_sheet:         "Extracted file rows",
  list_columns:       "Inspected columns",
  profile_columns:    "Profiled columns and types",
  profile_column:     "Profiled column data",
  test_parse:         "Tested data types",
  detect_date_format: "Checked date formats",
  check_uniqueness:   "Checked key uniqueness",
  sample_rows:        "Sampled rows",
  determine_grain:    "Determined table grain",
  propose_schema:     "Synthesized schema proposal",
  create_table:       "Created custom table",
  load_rows:          "Loaded dataset rows",
  get_schema:         "Looked at the columns",
  run_sql:            "Ran a query",
  read_kb:            "Read knowledge base",
  run_python:         "Ran Python calculation",
  checker:            "Verified numbers",
}

export function toolLabel(tool: string, rawLabel?: string, isRunning?: boolean): string {
  if (isRunning) {
    return ACTIVE_TOOL_DESCRIPTIONS[tool] || rawLabel || "Thinking…"
  }
  return rawLabel || PAST_TOOL_LABELS[tool] || tool
}

// ─────────────────────────────────────────────
// Status Dot (Calm, Neutral, Non-Loud)
// ─────────────────────────────────────────────

function StepIndicatorDot({ status }: { status: AgentStepStatus }) {
  if (status === "error") {
    return <span className="relative inline-flex rounded-full h-1.5 w-1.5 shrink-0 bg-destructive/80" />
  }
  // Neutral calm dot — no red or green dots
  return <span className="relative inline-flex rounded-full h-1.5 w-1.5 shrink-0 bg-muted-foreground/40" />
}

// ─────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────

interface AgentStepsProps {
  steps: AgentStep[]
  /** While true, renders a single active pulsating tool line at a time */
  isStreaming?: boolean
  /** When set, collapses past steps into a quiet one-line summary */
  collapsedSummary?: string
  onCancel?: () => void
  onRetry?: () => void
}

export function AgentSteps({
  steps,
  isStreaming,
  collapsedSummary,
}: AgentStepsProps) {
  const [expanded, setExpanded] = useState(false)

  // When there are no steps yet and we are streaming
  if (!steps || steps.length === 0) {
    if (!isStreaming) return null
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex items-center gap-2 text-xs text-muted-foreground my-2 select-none"
      >
        <span className="motion-safe:animate-pulse motion-reduce:animate-none font-medium text-foreground/80 font-mono text-[12px]">
          Thinking…
        </span>
      </div>
    )
  }

  // 1. Streaming mode: show exactly ONE active tool line pulsating at a time (Nexus style, zero red dot)
  if (isStreaming) {
    const activeStep = steps[steps.length - 1]
    const isError = activeStep.status === "error"
    const isRunning = activeStep.status === "running" || isStreaming
    const label = toolLabel(activeStep.tool, activeStep.label, isRunning)

    return (
      <div
        role="status"
        aria-live="polite"
        className="flex items-center gap-2 text-xs text-muted-foreground my-2 select-none"
      >
        <span
          className={
            isRunning
              ? "motion-safe:animate-pulse motion-reduce:animate-none font-medium text-foreground/80 font-mono text-[12px]"
              : isError
              ? "text-destructive/90 font-mono text-[12px]"
              : "text-muted-foreground font-mono text-[12px]"
          }
        >
          {label}
          {activeStep.evidence ? (
            <span className="ml-1.5 text-muted-foreground/60 font-normal">
              {activeStep.evidence}
            </span>
          ) : null}
        </span>
      </div>
    )
  }

  // 2. Completed collapsed mode: quiet one-line summary without loud green ticks
  if (collapsedSummary && !expanded) {
    return (
      <div className="my-1.5">
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground hover:text-foreground transition-colors outline-none focus-visible:underline cursor-pointer"
        >
          <span>{collapsedSummary}</span>
          <ChevronDown className="h-3 w-3 ml-0.5 opacity-60" />
        </button>
      </div>
    )
  }

  // 3. Expanded inspection mode: calm, neutral list with quiet dots
  return (
    <div
      role="status"
      aria-live="polite"
      className="my-2 space-y-1.5 select-none"
    >
      {collapsedSummary && (
        <button
          type="button"
          onClick={() => setExpanded(false)}
          className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground hover:text-foreground transition-colors mb-2 cursor-pointer"
        >
          <span>{collapsedSummary}</span>
          <ChevronUp className="h-3 w-3 ml-0.5 opacity-60" />
        </button>
      )}

      <div className="pl-1 border-l border-border/40 space-y-1.5 ml-1">
        {steps.map((step) => (
          <div key={step.id} className="flex items-center gap-2 pl-2 text-[11px] font-mono text-muted-foreground">
            <StepIndicatorDot status={step.status} />
            <span className={step.status === "error" ? "text-destructive" : ""}>
              {toolLabel(step.tool, step.label, false)}
              {step.evidence ? (
                <span className="ml-1.5 text-muted-foreground/60">{step.evidence}</span>
              ) : null}
            </span>
            {step.ms != null && (
              <span className="ml-auto text-[10px] text-muted-foreground/40 tabular-nums">{step.ms}ms</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
