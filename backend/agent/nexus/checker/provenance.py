"""Evidence tagging, claim provenance binding, and dataset attribution."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal

from agent.nexus.checker.extraction import normalize_raw_number
from agent.nexus.checker.matching import is_loss_context, match_target_value


class QueryResult(tuple):
    """3-tuple (preview_text, rows, validated_sql) with truncated and table_name metadata."""

    def __new__(
        cls,
        text: str,
        rows: list[dict],
        query: str | None,
        truncated: bool = False,
        table_name: str | None = None,
    ):
        obj = super().__new__(cls, (text, rows, query))
        obj.truncated = truncated
        obj.table_name = table_name
        return obj


def get_referenced_table(sql: str) -> str | None:
    """Extract primary relation name referenced in a guarded SQL query."""
    if not sql:
        return None
    cleaned = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    cleaned = re.sub(r"--[^\n]*", " ", cleaned).strip()
    masked = re.sub(r"'(?:''|[^'])*'", "''", cleaned)
    stripped = re.sub(r"(?is)\b(?:extract|trim|substring|overlay)\s*\([^)]*\)", "", masked)
    ctes = {m.group(1).lower() for m in re.finditer(r"(?is)\b([a-z_][a-z0-9_]*)\s+as\s*\(", stripped)}
    for m in re.finditer(r"(?is)\b(?:from|join)\s+(?:only\s+|lateral\s+)?([a-z_][a-z0-9_]*)", stripped):
        relation = m.group(1).lower()
        if relation not in ctes:
            return relation
    return None


@dataclass
class EvidenceRecord:
    query_id: int | str
    dataset_id: str | None
    table_label: str | None
    column: str
    kind: str  # "measure" | "identifier" | "count" | "date" | "python"
    row_index: int
    value: Decimal
    raw_string: str
    derived_from: list[int | str] = field(default_factory=list)


@dataclass
class ClaimProvenance:
    claim: str
    status: str  # "matched" | "untraced" | "exempt"
    source: str  # "data" | "python" | "prompt" | "exemption" | "none"
    query_id: int | str | None = None
    dataset: str | None = None
    dataset_id: str | None = None
    table_label: str | None = None
    column: str | None = None
    kind: str | None = None
    row_index: int | None = None
    exemption_reason: str | None = None
    reason: str | None = None
    also_in: list[int | str] = field(default_factory=list)
    derived_from: list[int | str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["dataset"] = self.dataset or self.table_label or self.dataset_id
        return d


_CURRENCY_OR_PERCENT_RE = re.compile(
    r"[\$£€]|%\s*$|\b(?:usd|eur|gbp|inr|dollars?|cents?|percent)\b",
    re.IGNORECASE,
)
_IDENTIFIER_COL_RE = re.compile(r"\b(?:id|code|zip|postal|pin)\b|_(?:id|code|zip|postal|pin)$", re.IGNORECASE)
_COUNT_COL_RE = re.compile(r"\b(?:count|row_count|total_rows|cnt|populated)\b|_(?:count|cnt)$", re.IGNORECASE)
_DATE_COL_RE = re.compile(r"\b(?:date|year|month|day|quarter|time|timestamp)\b|_(?:date|time)$", re.IGNORECASE)
_TOTAL_OR_COUNT_WORD_RE = re.compile(r"\b(?:total|sum|overall|count|top\s+\d+)\b", re.IGNORECASE)


def is_currency_or_percent_claim(raw: str) -> bool:
    """Return True if the claim string represents a currency or percentage."""
    return bool(_CURRENCY_OR_PERCENT_RE.search(raw.strip()))


def derive_column_kind(
    column_name: str,
    catalog_role: str | None = None,
    is_count_aggregate: bool = False,
) -> str:
    """Derive evidence kind: 'count', 'identifier', 'date', or 'measure'."""
    if is_count_aggregate:
        return "count"

    col = column_name.strip()
    if _COUNT_COL_RE.search(col):
        return "count"

    if catalog_role:
        r = catalog_role.lower().strip()
        if r in ("identifier", "id"):
            return "identifier"
        if r in ("measure", "metric", "numeric"):
            return "measure"
        if r in ("date", "time", "timestamp"):
            return "date"

    if _IDENTIFIER_COL_RE.search(col):
        return "identifier"
    if _DATE_COL_RE.search(col):
        return "date"

    return "measure"


def detect_named_dataset(text: str, available_labels: list[str]) -> str | None:
    """Return the table label explicitly named in answer text, if any."""
    clean_text = text.lower()
    for label in available_labels:
        if label and len(label) >= 3 and label.lower() in clean_text:
            return label

    # Detect explicit dataset references like "In the Superstore dataset" or "According to Superstore data"
    m = re.search(r"\b(?:in\s+the|from\s+the|according\s+to)\s+([A-Za-z0-9_-]+)\s+(?:data|dataset|table)\b", text, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        if candidate.lower() not in ("this", "our", "the", "your", "that", "data", "a"):
            return candidate

    return None


def bind_claim(
    value: Decimal,
    raw: str,
    evidence_records: list[EvidenceRecord],
    full_text: str,
    claim_start: int,
    named_dataset: str | None = None,
) -> tuple[EvidenceRecord | None, list[int | str], str | None]:
    """Bind a numeric claim to the first matching evidence record respecting provenance rules."""
    is_curr_or_pct = is_currency_or_percent_claim(raw)
    is_loss = is_loss_context(full_text, claim_start)

    # 1. Matching rule: Currency/percent claims may NOT match identifiers or counts
    eligible = [
        rec for rec in evidence_records
        if not (is_curr_or_pct and rec.kind in ("identifier", "count"))
    ]

    # Prioritize queries matching explicitly named dataset
    if named_dataset:
        prioritized = [r for r in eligible if r.table_label and r.table_label.lower() == named_dataset.lower()]
        other_records = [r for r in eligible if not (r.table_label and r.table_label.lower() == named_dataset.lower())]
        ordered_candidates = prioritized + other_records
    else:
        ordered_candidates = eligible

    matches: list[EvidenceRecord] = []
    for rec in ordered_candidates:
        if match_target_value(value, raw, rec.value, is_loss=is_loss):
            matches.append(rec)

    if not matches:
        return None, [], None

    best = matches[0]
    also_in = [rec.query_id for rec in matches[1:] if rec.query_id != best.query_id]
    # Remove duplicate query IDs preserving order
    also_in_unique = list(dict.fromkeys(also_in))

    # 2. Matching rule: Named dataset mismatch
    if named_dataset and best.table_label and best.table_label.lower() != named_dataset.lower():
        # Check if any match belonged to the named dataset
        has_named_match = any(m.table_label and m.table_label.lower() == named_dataset.lower() for m in matches)
        if not has_named_match:
            return None, also_in_unique, f"found in a different dataset ({best.table_label})"

    return best, also_in_unique, None


def check_truncation_caveat(queries: list[dict], text: str) -> str | None:
    """Return caveat reason if answer asserts a total/count/top claim over truncated evidence."""
    any_truncated = any(q.get("truncated", False) for q in queries)
    if any_truncated and _TOTAL_OR_COUNT_WORD_RE.search(text):
        return "Based on a partial result (first 200 rows)"
    return None


def synthesize_evidence_from_rows(
    rows: list[dict],
    python_results: dict | list | None = None,
) -> list[EvidenceRecord]:
    """Synthesize typed EvidenceRecords from rows and python_results for backward compatibility."""
    records: list[EvidenceRecord] = []
    for r_idx, row in enumerate(rows):
        for col_name, val in row.items():
            if val is None or str(val).strip() == "":
                continue
            norm = normalize_raw_number(str(val))
            if norm is not None:
                records.append(
                    EvidenceRecord(
                        query_id=1,
                        dataset_id=None,
                        table_label="Query 1",
                        column=str(col_name),
                        kind=derive_column_kind(str(col_name)),
                        row_index=r_idx,
                        value=norm,
                        raw_string=str(val).strip(),
                    )
                )

    if rows:
        records.append(
            EvidenceRecord(
                query_id=1,
                dataset_id=None,
                table_label="Query 1",
                column="row_count",
                kind="count",
                row_index=0,
                value=Decimal(len(rows)),
                raw_string=str(len(rows)),
            )
        )

    if python_results:
        items = python_results.items() if isinstance(python_results, dict) else [
            (it.get("label", str(i)), it.get("value"))
            for i, it in enumerate(python_results) if isinstance(it, dict)
        ]
        for label, val in items:
            if val is not None:
                val_norm = normalize_raw_number(str(val))
                if val_norm is not None:
                    records.append(
                        EvidenceRecord(
                            query_id="python",
                            dataset_id=None,
                            table_label="Calculated by Python",
                            column=str(label),
                            kind="python",
                            row_index=0,
                            value=val_norm,
                            raw_string=str(val),
                            derived_from=[1] if rows else [],
                        )
                    )

    return records
