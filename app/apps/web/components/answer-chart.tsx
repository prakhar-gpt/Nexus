"use client"

import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

export function AnswerChart({ rows }: { rows: Record<string, string>[] }) {
  if (rows.length < 2 || rows.length > 12) {
    return null
  }
  const keys = Object.keys(rows[0] ?? {})
  if (keys.length < 2) {
    return null
  }
  const [labelKey, valueKey] = keys
  const data = rows.map((row) => ({
    label: row[labelKey],
    value: Number(row[valueKey]),
  }))
  if (data.some((item) => Number.isNaN(item.value))) {
    return null
  }
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} />
          <YAxis tick={{ fontSize: 11 }} width={72} />
          <Tooltip />
          <Bar dataKey="value" fill="var(--foreground)" radius={4} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
