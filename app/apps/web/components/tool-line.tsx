"use client"

import type { TraceStep } from "@/lib/api"

interface ToolLineProps {
  activity?: TraceStep[]
  isWaiting?: boolean
}

const TOOL_DESCRIPTIONS: Record<string, string> = {
  columns: "Looking at the columns…",
  column_profiler: "Looking at the columns…",
  query: "Running a query…",
  sql_runner: "Running a query…",
  sql: "Running a query…",
  checker: "Verifying numbers against results…",
}

export function ToolLine({ activity, isWaiting }: ToolLineProps) {
  const steps = (activity ?? []).filter((s) => s.tool !== "checker")
  const activeStep = steps.length > 0 ? steps[steps.length - 1] : null

  if (!activeStep && !isWaiting) {
    return null
  }

  const label = activeStep
    ? activeStep.detail || TOOL_DESCRIPTIONS[activeStep.tool] || activeStep.tool
    : "Looking at the columns…"

  return (
    <div
      role="status"
      aria-live="polite"
      className="text-xs text-muted-foreground my-2 select-none"
    >
      <span>{label}</span>
    </div>
  )
}

