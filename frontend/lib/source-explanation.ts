import type { ClaimProvenanceItem, SourceRecord } from "@/lib/api"

export type SourceFigure = {
  label: string
  value: string
  note?: string
}

export type SourceExplanation = {
  displayClaim: string
  eyebrow: string
  detail: string
  equation?: string
  numbers?: string
  dataset?: string
  scope?: string
  figures: SourceFigure[]
  caveat?: string
}

type NamedInput = {
  name: string
  label: string
  value: string
  note?: string
  fromData: boolean
}

function formatNumber(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toLocaleString("en-US", { maximumFractionDigits: 2 })
  }
  const parsed = Number(String(value ?? "").replace(/[$,%\s]/g, ""))
  if (String(value ?? "").trim() !== "" && Number.isFinite(parsed)) {
    return parsed.toLocaleString("en-US", { maximumFractionDigits: 2 })
  }
  return String(value ?? "")
}

function entitiesInCode(code: string): Record<string, string> {
  const map: Record<string, string> = {}
  for (const match of code.matchAll(/(\w+)\s*=[^\n]*==\s*['"]([^'"]+)['"]/g)) {
    map[match[1]] = match[2]
  }
  return map
}

function formulaRhs(code: string, resultKey: string): string | null {
  let symbol = resultKey
  const dict = code.match(/result\s*=\s*\{([^}]+)\}/)
  if (dict) {
    const pair = dict[1].match(new RegExp(`['"]${resultKey}['"]\\s*:\\s*(\\w+)`))
    if (pair) symbol = pair[1]
  }
  const assign = code.match(new RegExp(`(?:^|\\n)\\s*${symbol}\\s*=\\s*([^\\n]+)`))
  if (!assign) return null
  let rhs = assign[1].trim().replace(/;+\s*$/, "")
  const rounded = rhs.match(/^round\((.*),\s*\d+\)$/)
  if (rounded) rhs = rounded[1].trim()
  return rhs
}

function prettify(expr: string): string {
  return expr
    .replace(/\s*\*\s*/g, " × ")
    .replace(/\s*\/\s*/g, " ÷ ")
    .replace(/\s*-\s*/g, " − ")
    .replace(/\s*\+\s*/g, " + ")
    .replace(/\(\s+/g, "(")
    .replace(/\s+\)/g, ")")
    .replace(/\s+/g, " ")
    .trim()
}

function substitute(expr: string, replacements: Record<string, string>): string {
  let next = expr
  for (const name of Object.keys(replacements).sort((a, b) => b.length - a.length)) {
    next = next.replace(new RegExp(`\\b${name}\\b`, "g"), replacements[name])
  }
  return next
}

function measureNote(sql: string | undefined): string | undefined {
  if (!sql) return undefined
  const match = sql.match(
    /(?:round\s*\(\s*)?(sum|avg|min|max|count)\s*\(\s*([^)]+?)\s*\)(?:\s*,\s*\d+\s*\))?/i
  )
  if (!match) return undefined
  const fn = match[1].toLowerCase()
  const inner = match[2].replace(/[_\s]+/g, " ").trim()
  if (fn === "count") return inner === "*" ? "count of rows" : `count of ${inner}`
  if (fn === "sum") return `total ${inner}`
  return `${fn} of ${inner}`
}

function datasetName(record: SourceRecord): string | undefined {
  const upstream = record.upstream_queries?.find((query) => query.dataset_label)
  const label = upstream?.dataset_label || record.dataset_label
  if (!label || /python|your data/i.test(label)) return undefined
  return label
}

function entityFromRows(value: number | string, rows?: Record<string, unknown>[]): string | undefined {
  const target = Number(String(value).replace(/,/g, ""))
  if (!Number.isFinite(target) || !rows?.length) return undefined
  for (const row of rows) {
    const hit = Object.values(row).some((cell) => {
      const numeric = Number(String(cell).replace(/,/g, ""))
      return Number.isFinite(numeric) && Math.abs(numeric - target) < 0.05
    })
    if (!hit) continue
    const text = Object.values(row).find((cell) => {
      if (typeof cell !== "string" || !cell.trim()) return false
      return !Number.isFinite(Number(cell.replace(/,/g, "")))
    })
    if (typeof text === "string") return text
  }
  return undefined
}

function namedInputs(record: SourceRecord, code: string, rhs: string | null): NamedInput[] {
  const entities = entitiesInCode(code)
  const upstream = record.upstream_queries?.[0]
  const measure = measureNote(record.sql || upstream?.sql)
  const resultNames = new Set(Object.keys(record.result ?? {}))
  const seen = new Set<string>()
  const inputs: NamedInput[] = []

  for (const input of record.inputs ?? []) {
    if (!input.name || resultNames.has(input.name) || /^-?\d+(\.\d+)?$/.test(input.name)) continue
    if (rhs && !new RegExp(`\\b${input.name}\\b`).test(rhs)) continue
    const label = input.entity
      || entities[input.name]
      || entityFromRows(input.value, upstream?.rows)
      || input.name.replace(/_/g, " ")
    if (seen.has(input.name)) continue
    seen.add(input.name)
    inputs.push({
      name: input.name,
      label,
      value: formatNumber(input.value),
      note: input.literal_in_code ? "typed in the calculation" : measure,
      fromData: !input.literal_in_code,
    })
  }
  return inputs
}

function percentOperands(rhs: string): [string, string] | null {
  const match = rhs.match(
    /^\(\s*\(\s*(\w+)\s*-\s*(\w+)\s*\)\s*\/\s*\2\s*\)\s*\*\s*100$/
  ) || rhs.match(/^\(\s*(\w+)\s*-\s*(\w+)\s*\)\s*\/\s*\2\s*\*\s*100$/)
  return match ? [match[1], match[2]] : null
}

function differenceOperands(rhs: string): [string, string] | null {
  const match = rhs.match(/^\(?\s*(\w+)\s*-\s*(\w+)\s*\)?$/)
  return match ? [match[1], match[2]] : null
}

function byName(inputs: NamedInput[], name: string): NamedInput | undefined {
  return inputs.find((input) => input.name === name)
}

function resultText(claim: ClaimProvenanceItem, raw: unknown, percent: boolean): string {
  const written = claim.claim?.trim()
  if (written) return percent && !written.includes("%") ? `${written}%` : written
  const formatted = formatNumber(raw)
  return percent ? `${formatted}%` : formatted
}

function explainPython(claim: ClaimProvenanceItem, record: SourceRecord): SourceExplanation {
  const code = record.code || ""
  const key = claim.column || ""
  const rhs = key ? formulaRhs(code, key) : null
  const inputs = namedInputs(record, code, rhs)
  const percent = (!!key && /pct|percent|rate/i.test(key)) || (!!rhs && /\*\s*100\b/.test(rhs))
  const shown = resultText(claim, key ? record.result?.[key] : undefined, percent)
  const dataset = datasetName(record)
  const upstream = record.upstream_queries?.[0]
  const rowCount = upstream?.row_count
  const grouped = upstream?.sql?.match(/\bgroup\s+by\s+([a-z_][a-z0-9_]*)/i)?.[1]?.replace(/_/g, "-")
  const pair = rhs ? percentOperands(rhs) : null
  const left = pair ? byName(inputs, pair[0]) : undefined
  const right = pair ? byName(inputs, pair[1]) : undefined

  let detail = inputs.length
    ? `Calculated from ${inputs.map((input) => input.label).join(" and ")}.`
    : "Calculated from the query result."
  let equation: string | undefined
  let numbers: string | undefined

  if (left && right && pair) {
    const measure = left.note && left.note === right.note && left.fromData ? left.note : undefined
    detail = measure
      ? `Using ${measure}, take ${left.label} minus ${right.label}, divide by ${right.label}, then multiply by 100.`
      : `Take ${left.label} minus ${right.label}, divide by ${right.label}, then multiply by 100.`
    equation = `(${left.label} − ${right.label}) ÷ ${right.label} × 100`
    numbers = `(${left.value} − ${right.value}) ÷ ${right.value} × 100 = ${shown}`
  } else if (rhs) {
    const diff = differenceOperands(rhs)
    const a = diff ? byName(inputs, diff[0]) : undefined
    const b = diff ? byName(inputs, diff[1]) : undefined
    const measure = inputs.find((input) => input.fromData)?.note
    if (a && b) {
      detail = measure
        ? `${measure[0].toUpperCase()}${measure.slice(1)}: ${a.label} minus ${b.label}.`
        : `${a.label} minus ${b.label}.`
      equation = `${a.label} − ${b.label}`
      numbers = `${a.value} − ${b.value} = ${shown}`
    } else {
      const names = Object.fromEntries(inputs.map((input) => [input.name, input.label]))
      const values = Object.fromEntries(inputs.map((input) => [input.name, input.value]))
      equation = prettify(substitute(rhs, names))
      numbers = `${prettify(substitute(rhs, values))} = ${shown}`
    }
  }

  return {
    displayClaim: shown,
    eyebrow: "Calculated from your data",
    detail,
    equation,
    numbers,
    dataset,
    scope: [
      grouped ? `Grouped by ${grouped}` : "",
      rowCount ? `${rowCount.toLocaleString("en-US")} rows` : "",
    ].filter(Boolean).join(" · ") || undefined,
    figures: inputs.map((input) => ({
      label: input.label,
      value: input.value,
      note: input.note,
    })),
    caveat: "This uses the totals from the query, not one cell in the spreadsheet.",
  }
}

function numericValue(raw: unknown): number | null {
  const parsed = Number(String(raw ?? "").replace(/[$£€%,\s]/g, ""))
  return Number.isFinite(parsed) && String(raw ?? "").trim() !== "" ? parsed : null
}

function rowForClaim(
  claim: ClaimProvenanceItem,
  record: SourceRecord
): Record<string, unknown> | null {
  const rows = record.rows ?? []
  const target = numericValue(claim.claim)
  const column = claim.column ?? undefined
  const close = (value: unknown) => {
    const parsed = numericValue(value)
    return target != null && parsed != null && Math.abs(parsed - target) < 0.05
  }
  if (record.matched_row && column && close(record.matched_row[column])) return record.matched_row
  for (const row of rows) {
    const cells = column && column in row ? [row[column]] : Object.values(row)
    if (cells.some(close)) return row
  }
  return record.matched_row ?? null
}

function explainData(claim: ClaimProvenanceItem, record: SourceRecord): SourceExplanation {
  const row = rowForClaim(claim, record)
  const column = claim.column ?? undefined
  const measure = measureNote(record.sql) || column?.replace(/_/g, " ")
  const dataset = datasetName(record) || record.dataset_label || "your data"
  let entity: string | undefined
  if (row) {
    for (const [key, value] of Object.entries(row)) {
      if (key === column || value == null) continue
      const text = String(value).trim()
      if (text && !/^-?[\d,.\s]+%?$/.test(text)) {
        entity = text
        break
      }
    }
  }
  const shown = claim.claim?.trim() || (column && row ? formatNumber(row[column]) : "this number")
  const detail = entity && measure
    ? `${shown} is the ${measure} for ${entity}${dataset !== "your data" ? ` in ${dataset}` : ""}.`
    : measure
      ? `${shown} is the ${measure}${dataset !== "your data" ? ` in ${dataset}` : ""}.`
      : `${shown} came from ${dataset}.`

  const hidden = new Set(["workspace_id", "upload_id", "row_id"])
  const figures: SourceFigure[] = row
    ? Object.entries(row)
        .filter(([key]) => !hidden.has(key))
        .map(([key, value]) => ({
          label: key === "source_row"
            ? "Row in your file"
            : key === column && measure
              ? measure
              : key.replace(/_/g, " "),
          value: formatNumber(value),
        }))
    : []

  return {
    displayClaim: shown,
    eyebrow: "From your data",
    detail,
    dataset: dataset === "your data" ? undefined : dataset,
    figures,
    caveat: record.truncated ? "Based on a partial result (first 200 rows)." : undefined,
  }
}

export function explainSource(
  claim: ClaimProvenanceItem | null,
  record: SourceRecord | null
): SourceExplanation | null {
  if (!claim) return null
  if (claim.source === "prompt") {
    return {
      displayClaim: claim.claim?.trim() || "this number",
      eyebrow: "Stated in your message",
      detail: "This number came from your question. It was not found in the dataset.",
      figures: [],
    }
  }
  if (claim.status === "untraced" || claim.source === "none") {
    return {
      displayClaim: claim.claim?.trim() || "this number",
      eyebrow: "Not found in the data",
      detail: "This number could not be matched to the checked results.",
      figures: [],
    }
  }
  if (!record) return null
  if (claim.source === "python" || record.origin_type === "python") return explainPython(claim, record)
  return explainData(claim, record)
}
