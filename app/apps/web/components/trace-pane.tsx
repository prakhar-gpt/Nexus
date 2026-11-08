"use client"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { TraceStep } from "@/lib/api"

const EVAL_LABELS = [
  ["sql_correctness", "SQL correctness"],
  ["numeric_faithfulness", "Numeric faithfulness"],
  ["refusal_accuracy", "Refusal accuracy"],
] as const

export function TracePane({
  steps,
  scores,
  runningEval,
  onRunEval,
}: {
  steps: TraceStep[]
  scores: Record<string, number> | null
  runningEval: boolean
  onRunEval: () => void
}) {
  return (
    <section className="flex min-h-[28rem] min-w-0 flex-col overflow-hidden xl:h-full xl:min-h-0">
      <header className="flex h-12 shrink-0 items-center px-4">
        <h2 className="text-sm font-medium">Trace & Eval</h2>
      </header>
      <Tabs defaultValue="trace" className="min-h-0 flex-1 px-4 pb-4">
        <TabsList>
          <TabsTrigger value="trace">Trace</TabsTrigger>
          <TabsTrigger value="eval">Eval</TabsTrigger>
        </TabsList>
        <TabsContent value="trace" className="min-h-0">
          <ScrollArea className="min-h-0 flex-1 basis-0 overflow-hidden">
            {steps.length === 0 ? (
              <Empty className="mt-3 border">
                <EmptyHeader>
                  <EmptyTitle>No steps yet</EmptyTitle>
                  <EmptyDescription>
                    Schema, SQL, and the checker show up here while a question runs.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <ol className="flex flex-col gap-3 pt-3">
                {steps.map((step, index) => (
                  <li
                    key={`${step.tool}-${index}`}
                    className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2"
                  >
                    <span className="text-sm">{step.tool}</span>
                    <span className="flex items-center gap-2">
                      <Badge variant="outline">{step.status}</Badge>
                      <span className="text-xs text-muted-foreground">
                        {step.ms == null ? "—" : `${step.ms} ms`}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </ScrollArea>
        </TabsContent>
        <TabsContent value="eval">
          <ul className="flex flex-col gap-2 pt-3">
            {EVAL_LABELS.map(([key, label]) => (
              <li key={key} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-muted-foreground">{label}</span>
                <span>{scores ? `${Math.round(scores[key] * 100)}%` : "Not run"}</span>
              </li>
            ))}
          </ul>
          <Button className="mt-4" size="sm" disabled={runningEval} onClick={onRunEval}>
            {runningEval ? "Running" : "Run eval"}
          </Button>
        </TabsContent>
      </Tabs>
    </section>
  )
}
