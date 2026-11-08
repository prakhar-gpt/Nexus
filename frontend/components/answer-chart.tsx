"use client"

import { useState } from "react"
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

interface AnswerChartProps {
  rows: Record<string, string | number>[]
}

export function AnswerChart({ rows }: AnswerChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

  if (!rows || rows.length < 2) {
    return null
  }

  const keys = Object.keys(rows[0] ?? {})
  if (keys.length < 2) {
    return null
  }

  // Find label column (first string) and numeric value column
  let labelKey = keys[0]
  let valueKey = keys[1]

  for (const k of keys) {
    const val = Number(rows[0][k])
    if (!Number.isNaN(val)) {
      valueKey = k
      break
    }
  }

  if (labelKey === valueKey) {
    labelKey = keys.find((k) => k !== valueKey) || keys[0]
  }

  const data = rows.slice(0, 15).map((row) => ({
    label: String(row[labelKey] ?? ""),
    value: Number(row[valueKey] ?? 0),
  }))

  if (data.some((item) => Number.isNaN(item.value))) {
    return null
  }

  return (
    <div className="h-[220px] w-full pt-3">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 8, right: 12, left: 0, bottom: 20 }}
          onMouseLeave={() => setHoveredIndex(null)}
        >
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            axisLine={{ stroke: "var(--border)", strokeWidth: 1 }}
            tickLine={{ stroke: "var(--border)" }}
            interval={0}
            tickFormatter={(val: string) =>
              val.length > 14 ? `${val.slice(0, 12)}…` : val
            }
          />
          <YAxis
            tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            axisLine={{ stroke: "var(--border)", strokeWidth: 1 }}
            tickLine={{ stroke: "var(--border)" }}
            width={70}
            tickFormatter={(val: number) => {
              if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`
              if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(0)}k`
              return String(val)
            }}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload || !payload.length) return null
              const item = payload[0].payload
              return (
                <div className="border border-border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground">
                  <p className="font-medium">{item.label}</p>
                  <p className="font-mono tabular-nums text-muted-foreground mt-0.5">
                    {typeof item.value === "number"
                      ? `$${item.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                      : item.value}
                  </p>
                </div>
              )
            }}
          />
          <Bar
            dataKey="value"
            onMouseEnter={(_, index) => setHoveredIndex(index)}
          >
            {data.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={
                  hoveredIndex === index
                    ? "var(--primary)"
                    : "color-mix(in srgb, var(--foreground) 85%, transparent)"
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
