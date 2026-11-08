"use client"

import { Check, Loader2, X } from "lucide-react"

export interface PipelineStage {
  id: string
  label: string
}

const STAGES: PipelineStage[] = [
  { id: "safety", label: "Checking file" },
  { id: "structure", label: "Reading sheet" },
  { id: "mapping", label: "Matching columns" },
  { id: "load", label: "Loading rows" },
]

interface PipelineStepperProps {
  stages: { stage: string; status: string; reason?: string }[]
  overallStatus?: string | null
  overallReason?: string | null
}

export function PipelineStepper({
  stages,
  overallStatus,
  overallReason,
}: PipelineStepperProps) {
  if (stages.length === 0 && !overallStatus) {
    return null
  }

  // Determine each stage's status: pending | active | done | failed
  function getStageState(stageId: string, index: number) {
    const found = stages.find((s) => s.stage === stageId)
    if (found) {
      if (found.status === "failed" || found.status === "error") {
        return { status: "failed", reason: found.reason || overallReason }
      }
      if (found.status === "done" || found.status === "success") {
        return { status: "done" }
      }
      return { status: "active" }
    }

    if (overallStatus === "rejected" || overallStatus === "failed") {
      const activeIdx = stages.length
      if (index === activeIdx) {
        return { status: "failed", reason: overallReason }
      }
    }

    if (index < stages.length) {
      return { status: "done" }
    }

    if (index === stages.length && overallStatus !== "loaded" && overallStatus !== "done") {
      return { status: "active" }
    }

    return { status: "pending" }
  }

  return (
    <div className="flex flex-col gap-2 py-2">
      <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
        Ingestion Pipeline
      </span>

      {/* Horizontal on md+, vertical on mobile */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 bg-muted/30 border border-border">
        {STAGES.map((st, i) => {
          const state = getStageState(st.id, i)

          return (
            <div key={st.id} className="flex items-center gap-2 text-xs flex-1">
              {state.status === "done" && (
                <div className="flex h-5 w-5 shrink-0 items-center justify-center bg-ok/10 text-ok border border-ok/20">
                  <Check className="h-3 w-3 stroke-[2.5]" />
                </div>
              )}

              {state.status === "active" && (
                <div className="flex h-5 w-5 shrink-0 items-center justify-center bg-accent text-foreground border border-border">
                  <Loader2 className="h-3 w-3 animate-spin" />
                </div>
              )}

              {state.status === "failed" && (
                <div className="flex h-5 w-5 shrink-0 items-center justify-center bg-destructive/10 text-destructive border border-destructive/20">
                  <X className="h-3 w-3 stroke-[2.5]" />
                </div>
              )}

              {state.status === "pending" && (
                <div className="flex h-5 w-5 shrink-0 items-center justify-center border border-border text-muted-foreground/50">
                  <span className="font-mono text-[10px]">{i + 1}</span>
                </div>
              )}

              <div className="flex flex-col min-w-0">
                <span
                  className={`font-medium truncate ${
                    state.status === "active"
                      ? "text-foreground"
                      : state.status === "done"
                      ? "text-foreground/80"
                      : state.status === "failed"
                      ? "text-destructive"
                      : "text-muted-foreground"
                  }`}
                >
                  {st.label}
                </span>
                {state.reason ? (
                  <span className="text-[10px] text-destructive truncate">
                    {state.reason}
                  </span>
                ) : null}
              </div>

              {i < STAGES.length - 1 ? (
                <span className="hidden md:inline text-muted-foreground/40 mx-auto">
                  →
                </span>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}

