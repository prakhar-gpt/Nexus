"use client"

import { useState } from "react"
import { ChevronDown, ChevronUp, AlertCircle, Check, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { Mapping } from "@/lib/api"

export const CANONICAL_FIELDS = [
  "order_date",
  "customer_id",
  "product_id",
  "quantity",
  "revenue",
  "unit_price",
  "discount_pct",
  "cost",
  "profit",
  "segment",
  "region",
  "category",
  "sub_category",
  "channel",
] as const

interface MappingTableProps {
  mappings: Mapping[]
  confirming?: boolean
  onConfirm: (decisions: Record<string, string>) => Promise<boolean>
}

export function MappingTable({
  mappings,
  confirming = false,
  onConfirm,
}: MappingTableProps) {
  // Split into uncertain (<0.7 or needs_confirmation) and auto-matched (>=0.7)
  const uncertainRows = mappings.filter(
    (m) => m.needs_confirmation || (m.confidence < 0.7 && !m.confirmed_by_user)
  )
  const autoRows = mappings.filter(
    (m) => !m.needs_confirmation && (m.confidence >= 0.7 || m.confirmed_by_user)
  )

  const [expandedAuto, setExpandedAuto] = useState(false)
  const [decisions, setDecisions] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {}
    for (const m of mappings) {
      initial[m.source] = m.canonical ?? ""
    }
    return initial
  })
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  if (mappings.length === 0) {
    return null
  }

  function handleSelectChange(source: string, val: string) {
    setDecisions((prev) => ({ ...prev, [source]: val }))
    setSaveError(null)
    setSaveSuccess(false)
  }

  // Confirm mapping is disabled until every uncertain row is assigned (or explicitly chosen to skip/map)
  const allUncertainResolved = uncertainRows.every(
    (row) => decisions[row.source] !== undefined && decisions[row.source] !== ""
  )

  async function handleConfirm() {
    setSaveError(null)
    setSaveSuccess(false)
    const success = await onConfirm(decisions)
    if (success) {
      setSaveSuccess(true)
    } else {
      setSaveError("Couldn't save mapping. Try again.")
    }
  }

  return (
    <div className="flex flex-col gap-3 py-2">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
          Column Mapping
        </span>
        <span className="text-[11px] text-muted-foreground">
          Your column → Nexus canonical field
        </span>
      </div>

      {/* Uncertain rows (<70%) shown first, warn-tinted */}
      {uncertainRows.length > 0 ? (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-1.5 text-xs text-warn font-medium">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span>
              {uncertainRows.length}{" "}
              {uncertainRows.length === 1 ? "column needs" : "columns need"} confirmation
            </span>
          </div>

          <div className="flex flex-col gap-1.5">
            {uncertainRows.map((row) => {
              const currentVal = decisions[row.source] ?? row.canonical ?? ""
              const confPct = Math.round(row.confidence * 100)

              return (
                <div
                  key={row.source}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2.5 bg-warn/5 border border-warn/20 text-xs"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-mono text-[12px] font-medium text-foreground truncate">
                      {row.source}
                    </span>
                    <span className="font-mono text-[10px] tabular-nums text-muted-foreground bg-muted/60 px-1 py-0.5">
                      {confPct}% confidence
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground hidden sm:inline">→</span>
                    <select
                      value={currentVal}
                      onChange={(e) => handleSelectChange(row.source, e.target.value)}
                      className="h-8 border border-input bg-card px-2 text-xs text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                    >
                      <option value="">Select field…</option>
                      <option value="__skip__">Ignore this column</option>
                      {CANONICAL_FIELDS.map((f) => (
                        <option key={f} value={f}>
                          {f}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Confirm mapping button */}
          <div className="flex items-center justify-between pt-1">
            <Button
              type="button"
              size="sm"
              disabled={confirming || !allUncertainResolved}
              onClick={handleConfirm}
              className="text-xs"
            >
              {confirming ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                  Saving mapping…
                </>
              ) : (
                "Confirm mapping"
              )}
            </Button>

            {saveSuccess ? (
              <span className="flex items-center gap-1 text-xs text-ok">
                <Check className="h-3.5 w-3.5" />
                <span>Mapping saved</span>
              </span>
            ) : null}
          </div>

          {saveError ? (
            <div
              role="alert"
              className="flex items-center justify-between p-2 bg-destructive/10 border border-destructive/20 text-destructive text-xs"
            >
              <div className="flex items-center gap-1.5">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                <span>{saveError}</span>
              </div>
              <button
                type="button"
                onClick={handleConfirm}
                disabled={confirming}
                className="font-medium underline underline-offset-2 hover:opacity-80 disabled:opacity-50"
              >
                Retry
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Auto-mapped rows (>=70%) collapsed under expander */}
      {autoRows.length > 0 ? (
        <div className="flex flex-col border border-border bg-card">
          <button
            type="button"
            onClick={() => setExpandedAuto((prev) => !prev)}
            aria-expanded={expandedAuto}
            className="flex items-center justify-between p-2.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <div className="flex items-center gap-1.5">
              <Check className="h-3.5 w-3.5 text-ok" />
              <span>
                {autoRows.length} {autoRows.length === 1 ? "column" : "columns"} matched automatically
              </span>
            </div>
            {expandedAuto ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>

          {expandedAuto ? (
            <div className="border-t border-border divide-y divide-border/60">
              {autoRows.map((row) => (
                <div
                  key={row.source}
                  className="flex items-center justify-between px-3 py-1.5 text-xs text-muted-foreground"
                >
                  <span className="font-mono text-foreground">{row.source}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground/60">→</span>
                    <span className="font-mono text-foreground">{row.canonical}</span>
                    <span className="font-mono text-[10px] tabular-nums text-muted-foreground/60">
                      {Math.round(row.confidence * 100)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

