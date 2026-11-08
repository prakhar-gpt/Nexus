"use client"

import { Badge } from "@/components/ui/badge"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const EVAL_ROWS = [
  "SQL correctness",
  "Numeric faithfulness",
  "Refusal accuracy",
  "Latency",
] as const

export function TracePane({ hasQuestion }: { hasQuestion: boolean }) {
  return (
    <section className="flex min-h-[28rem] min-w-0 flex-col xl:min-h-0">
      <header className="flex h-12 shrink-0 items-center px-4">
        <h2 className="text-sm font-medium">Trace & Eval</h2>
      </header>
      <Tabs defaultValue="trace" className="min-h-0 flex-1 px-4 pb-4">
        <TabsList>
          <TabsTrigger value="trace">Trace</TabsTrigger>
          <TabsTrigger value="eval">Eval</TabsTrigger>
        </TabsList>
        <TabsContent value="trace" className="min-h-0">
          <ScrollArea className="h-full">
            {hasQuestion ? (
              <ol className="flex flex-col gap-3 pt-3">
                <li className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
                  <span className="text-sm">Plan</span>
                  <span className="flex items-center gap-2">
                    <Badge variant="outline">Waiting</Badge>
                    <span className="text-xs text-muted-foreground">—</span>
                  </span>
                </li>
              </ol>
            ) : (
              <Empty className="mt-3 border">
                <EmptyHeader>
                  <EmptyTitle>No steps yet</EmptyTitle>
                  <EmptyDescription>
                    Schema, SQL, and the checker show up here while a question runs.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            )}
          </ScrollArea>
        </TabsContent>
        <TabsContent value="eval">
          <ul className="flex flex-col gap-2 pt-3">
            {EVAL_ROWS.map((label) => (
              <li
                key={label}
                className="flex items-center justify-between gap-3 text-sm"
              >
                <span className="text-muted-foreground">{label}</span>
                <span>Not run</span>
              </li>
            ))}
          </ul>
        </TabsContent>
      </Tabs>
    </section>
  )
}
