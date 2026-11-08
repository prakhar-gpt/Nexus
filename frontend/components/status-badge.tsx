"use client"

import { Check, AlertTriangle, Ban } from "lucide-react"

export type AnswerBadge =
  | "waiting"
  | "verified"
  | "caveat"
  | "refused"
  | "unanswered"
  | "stopped"

interface StatusBadgeProps {
  badge?: AnswerBadge
  tooltip?: string
  untraced?: string[]
  missingMeasure?: string
}

export function StatusBadge({
  badge,
  tooltip,
  untraced,
  missingMeasure,
}: StatusBadgeProps) {
  if (!badge || badge === "waiting" || badge === "unanswered" || badge === "verified") {
    return null
  }

  if (badge === "caveat") {
    const untracedList =
      untraced && untraced.length > 0 ? untraced.join(", ") : null
    const titleText =
      tooltip ||
      (untracedList
        ? `Ungrounded numbers: ${untracedList}`
        : "A figure in this answer was not found in the query result.")

    return (
      <span
        title={titleText}
        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-warn/10 text-warn border border-warn/20 select-none cursor-default"
        aria-label={`Status: Caveat. ${titleText}`}
      >
        <AlertTriangle className="h-3 w-3 stroke-[2.25]" />
        <span>Caveat</span>
      </span>
    )
  }

  if (badge === "refused") {
    const titleText =
      tooltip ||
      missingMeasure ||
      "This dataset has no cost or profit column to answer this question."

    return (
      <span
        title={titleText}
        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-destructive/10 text-destructive border border-destructive/20 select-none cursor-default"
        aria-label={`Status: Refused. ${titleText}`}
      >
        <Ban className="h-3 w-3 stroke-[2.25]" />
        <span>Refused</span>
      </span>
    )
  }

  if (badge === "stopped") {
    return (
      <span
        title="Generation stopped by user"
        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground border border-border select-none cursor-default"
        aria-label="Status: Stopped"
      >
        <span>Stopped</span>
      </span>
    )
  }

  return null
}
