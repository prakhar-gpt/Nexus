"use client"

import type { TraceStep } from "@/lib/api"

interface ToolLineProps {
  activity?: TraceStep[]
  isWaiting?: boolean
}

const TOOL_DESCRIPTIONS: Record<string, string> = {
  columns: "Looking at the columns…",
  column_profiler: "Looking at the columns…",
  get_schema: "Looking at the columns…",
  query: "Running a query…",
  sql_runner: "Running a query…",
  sql: "Running a query…",
  run_sql: "Running a query…",
  read_kb: "Reading knowledge base…",
  run_python: "Running Python calculation…",
  python: "Running Python calculation…",
  calculation: "Running Python calculation…",
  checker: "Verifying numbers against results…",
}

export function ToolLine({ activity, isWaiting }: ToolLineProps) {
  const steps = (activity ?? []).filter((s) => s.tool !== "checker")
  const activeStep = steps.length > 0 ? steps[steps.length - 1] : null

  if (!activeStep && !isWaiting) {
    return null
  }

  const isError = activeStep?.status === "error"
  const isRunning = !isError && (isWaiting || (activeStep ? activeStep.status === "running" : true))

  const label = activeStep
    ? activeStep.detail || TOOL_DESCRIPTIONS[activeStep.tool] || (activeStep.tool === "run_python" ? "Running Python calculation…" : activeStep.tool)
    : "Thinking…"

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 text-xs text-muted-foreground my-2.5 select-none"
    >
      {isRunning ? (
        <span className="relative flex h-2 w-2">
          <span className="motion-safe:animate-ping motion-reduce:hidden absolute inline-flex h-full w-full rounded-full bg-primary/40 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
        </span>
      ) : isError ? (
        <span className="relative inline-flex rounded-full h-2 w-2 bg-destructive/80" />
      ) : null}
      <span
        className={
          isRunning
            ? "motion-safe:animate-pulse motion-reduce:animate-none font-medium text-foreground/80"
            : isError
            ? "text-destructive/90"
            : ""
        }
      >
        {label}
      </span>
    </div>
  )
}
