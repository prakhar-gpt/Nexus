"""Number audit for the copilot: claims, evidence records, and Python lineage."""

from agent.nexus.checker.checker import (
    check_answer,
    draft_from_rows,
    extract_numbers,
    is_clarification,
    refusal_text,
)
from agent.nexus.checker.evidence_collector import (
    collect_python_evidence,
    collect_sql_evidence,
    extract_python_input_lineage,
)
from agent.nexus.checker.provenance import (
    ClaimProvenance,
    EvidenceRecord,
    QueryResult,
    bind_claim,
    check_truncation_caveat,
    derive_column_kind,
    get_referenced_table,
    is_currency_or_percent_claim,
    synthesize_evidence_from_rows,
)

__all__ = [
    "ClaimProvenance",
    "EvidenceRecord",
    "QueryResult",
    "bind_claim",
    "check_answer",
    "check_truncation_caveat",
    "collect_python_evidence",
    "collect_sql_evidence",
    "derive_column_kind",
    "draft_from_rows",
    "extract_numbers",
    "extract_python_input_lineage",
    "get_referenced_table",
    "is_clarification",
    "is_currency_or_percent_claim",
    "refusal_text",
    "synthesize_evidence_from_rows",
]
