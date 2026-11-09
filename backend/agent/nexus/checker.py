"""Deterministic claim-to-evidence checker and verification coordinator."""

from __future__ import annotations

import re
import time
from decimal import Decimal

from agent.nexus.extraction import (
    _NUMBER,
    extract_numbers,
    is_contextual_year,
    is_exempt_number,
    normalize_raw_number,
)
from agent.nexus.normalization import normalize_text, strip_fenced_code_blocks
from agent.nexus.provenance import (
    ClaimProvenance,
    EvidenceRecord,
    bind_claim,
    check_truncation_caveat,
    detect_named_dataset,
    synthesize_evidence_from_rows,
)

_METHOD_CLAIM = re.compile(
    r"\b(?:using|with|via)\s+(?:python|the\s+math\s+tool|the\s+python\s+tool|the\s+tool)\b|"
    r"\bcalculated\s+(?:with|using|in)\s+(?:python|the\s+math\s+tool|the\s+tool)\b|"
    r"\bpython\s+calculation\b",
    re.IGNORECASE,
)
_GREETING_RE = re.compile(
    r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|howdy|greetings)[!., ]*$",
    re.IGNORECASE,
)


def is_greeting(text: str) -> bool:
    """Return True strictly for short conversational greetings."""
    return bool(_GREETING_RE.match((text or "").strip()))


def is_clarification(text: str) -> bool:
    """Return True when an answer is asking the user a question for clarification."""
    stripped = (text or "").strip()
    return bool(stripped and "?" in stripped)


def check_answer(
    answer: str,
    rows: list[dict],
    context: list[str] | None = None,
    python_results: dict | list | None = None,
    question_text: str | None = None,
    sql_limit: int | None = None,
    kind: str | None = None,
    evidence_records: list[EvidenceRecord] | None = None,
    queries: list[dict] | None = None,
) -> dict:
    """Audit every number in an answer against tool evidence, prompt quotes, and loss context."""
    started = time.perf_counter()
    clean_answer = strip_fenced_code_blocks(normalize_text(answer or ""))

    no_tools_ran = (not rows) and (not python_results)
    is_refusal = (kind == "refusal") or ("cannot answer" in clean_answer.lower()) or ("refus" in clean_answer.lower())
    is_clarif = (kind == "clarification") or is_clarification(clean_answer)
    is_greet = is_greeting(clean_answer)

    # Use supplied tagged EvidenceRecords or synthesize from rows/python
    evidence = list(evidence_records) if evidence_records is not None else synthesize_evidence_from_rows(rows, python_results=python_results)
    queries_list = list(queries or [])

    available_labels = [r.table_label for r in evidence if r.table_label]
    named_dataset = detect_named_dataset(clean_answer, available_labels)

    # Parse user-quoted prompt numbers
    question_clean = strip_fenced_code_blocks(normalize_text(question_text or ""))
    prompt_numbers: list[tuple[Decimal, str, int, int]] = []
    if question_clean:
        for qm in _NUMBER.finditer(question_clean):
            q_raw = qm.group(0)
            q_val = normalize_raw_number(q_raw)
            if q_val is not None:
                prompt_numbers.append((q_val, q_raw, qm.start(), qm.end()))

    untraced: list[str] = []
    matched: list[str] = []
    provenance: list[dict] = []
    row_count = len(rows)

    for match in _NUMBER.finditer(clean_answer):
        raw = match.group(0)
        start, end = match.span()

        if is_exempt_number(raw, clean_answer, start, end, row_count=row_count, sql_limit=sql_limit):
            provenance.append(
                ClaimProvenance(claim=raw, status="exempt", source="exemption", exemption_reason="year_date_or_ordinal").to_dict()
            )
            continue

        value = normalize_raw_number(raw)
        if value is None:
            untraced.append(raw)
            provenance.append(ClaimProvenance(claim=raw, status="untraced", source="none", reason="unparseable_number").to_dict())
            continue

        best_rec, also_in, mismatch_reason = bind_claim(value, raw, evidence, clean_answer, start, named_dataset=named_dataset)

        if best_rec is not None:
            matched.append(raw)
            provenance.append(
                ClaimProvenance(
                    claim=raw,
                    status="matched",
                    source="python" if best_rec.kind == "python" else "data",
                    query_id=best_rec.query_id,
                    dataset_id=best_rec.dataset_id,
                    table_label=best_rec.table_label,
                    column=best_rec.column,
                    kind=best_rec.kind,
                    row_index=best_rec.row_index,
                    also_in=also_in,
                ).to_dict()
            )
            continue

        if mismatch_reason:
            untraced_msg = f"{raw} ({mismatch_reason})"
            untraced.append(untraced_msg)
            provenance.append(
                ClaimProvenance(claim=raw, status="untraced", source="data", reason=mismatch_reason, also_in=also_in).to_dict()
            )
            continue

        # Match against prompt-stated numbers
        matched_in_prompt = False
        prompt_is_year_or_top = False
        for q_val, q_raw, q_start, q_end in prompt_numbers:
            if abs(value - q_val) <= Decimal("0.5"):
                matched_in_prompt = True
                if is_contextual_year(q_raw, question_clean, q_start, q_end) or re.search(r"(?i)\btop\s+$", question_clean[max(0, q_start - 10) : q_start]):
                    prompt_is_year_or_top = True
                break

        if matched_in_prompt:
            if prompt_is_year_or_top:
                matched.append(raw)
                provenance.append(
                    ClaimProvenance(claim=raw, status="matched", source="prompt", exemption_reason="prompt_year_or_top_echo").to_dict()
                )
            else:
                untraced_msg = f"{raw} (stated in your message, not found in the data)"
                untraced.append(untraced_msg)
                provenance.append(
                    ClaimProvenance(claim=raw, status="untraced", source="prompt", reason="stated in your message, not found in the data").to_dict()
                )
            continue

        untraced.append(raw)
        provenance.append(ClaimProvenance(claim=raw, status="untraced", source="none").to_dict())

    # Flag ungrounded method claims
    if not python_results:
        claim_match = _METHOD_CLAIM.search(clean_answer)
        if claim_match:
            untraced.append(f"method claim '{claim_match.group(0)}' without tool execution")

    # Truncation audit: partial result serving total, count, or top N
    trunc_caveat = check_truncation_caveat(queries_list, clean_answer)
    if trunc_caveat and not untraced:
        untraced.append(trunc_caveat)

    elapsed_ms = max(round((time.perf_counter() - started) * 1000, 2), 0.01)

    bounded_prov = provenance[:100]

    # Verdict policy determination
    if untraced:
        return {
            "status": "caveat",
            "verified": False,
            "untraced": untraced,
            "matched": matched,
            "provenance": bounded_prov,
            "queries": queries_list,
            "ms": elapsed_ms,
        }

    if is_refusal:
        return {
            "status": "refused",
            "verified": False,
            "untraced": [],
            "matched": matched,
            "provenance": bounded_prov,
            "queries": queries_list,
            "ms": elapsed_ms,
        }

    if is_clarif or is_greet:
        return {
            "status": "verified",
            "verified": True,
            "untraced": [],
            "matched": matched,
            "provenance": bounded_prov,
            "queries": queries_list,
            "ms": elapsed_ms,
        }

    if no_tools_ran:
        return {
            "status": "caveat",
            "verified": False,
            "untraced": ["Not checked against your data"],
            "matched": matched,
            "provenance": bounded_prov,
            "queries": queries_list,
            "ms": elapsed_ms,
        }

    return {
        "status": "verified",
        "verified": True,
        "untraced": [],
        "matched": matched,
        "provenance": bounded_prov,
        "queries": queries_list,
        "ms": elapsed_ms,
    }


def refusal_text(column: str) -> str:
    """Standardized refusal sentence when a required column has no values."""
    return f"Cannot answer. {column} has no values in this workspace, so the question is refused."


def draft_from_rows(rows: list[dict]) -> str:
    """Format query result rows into key=value lines for evaluator drafts."""
    if not rows:
        return "The query returned no rows."
    lines = []
    for row in rows:
        parts = [f"{key}={value}" for key, value in row.items() if value is not None and str(value) != ""]
        lines.append(", ".join(parts))
    return "\n".join(lines)
