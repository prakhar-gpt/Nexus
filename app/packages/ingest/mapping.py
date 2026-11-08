"""Map source headers onto sales_clean columns."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

CANONICAL = (
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
)
AUTO_THRESHOLD = 70
HINTS_PATH = Path(__file__).resolve().parents[2] / "kb" / "column_hints.md"
_HINT_ROW = re.compile(r"^\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")


@dataclass
class Proposal:
    source: str
    canonical: str | None
    confidence: float
    method: str
    needs_confirmation: bool
    confirmed_by_user: bool = False


def normalize(value: str) -> str:
    text = value.lower().replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def load_hints(path: Path = HINTS_PATH) -> dict[str, str]:
    hints = {}
    if not path.exists():
        return hints
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _HINT_ROW.match(line.strip())
        if not match:
            continue
        source, canonical = match.group(1), match.group(2)
        if source.lower() == "source header" or set(source) <= {"-"}:
            continue
        if canonical in CANONICAL:
            hints[normalize(source)] = canonical
    return hints


def best_score(header: str) -> tuple[float, str]:
    folded = normalize(header)
    scored = [
        (fuzz.ratio(folded, normalize(name)), name) for name in CANONICAL
    ]
    return max(scored)


def propose_columns(headers: list[str], hints: dict[str, str] | None = None) -> list[Proposal]:
    hints = load_hints() if hints is None else hints
    proposals = []
    used = set()
    ranked = []
    for header in headers:
        score, name = best_score(header)
        ranked.append((score, header, name))
    for score, header, name in sorted(ranked, reverse=True):
        hinted = hints.get(normalize(header))
        if score >= AUTO_THRESHOLD and name not in used:
            used.add(name)
            proposals.append(
                Proposal(header, name, score, "fuzzy", needs_confirmation=False)
            )
            continue
        if hinted and hinted not in used:
            used.add(hinted)
            proposals.append(
                Proposal(header, hinted, score, "llm", needs_confirmation=True)
            )
            continue
        proposals.append(Proposal(header, None, score, "fuzzy", False))
    by_source = {proposal.source: proposal for proposal in proposals}
    return [by_source[header] for header in headers]


def domain_gap(columns: set[str]) -> str | None:
    missing = []
    if "order_date" not in columns:
        missing.append("a date")
    if "customer_id" not in columns and "product_id" not in columns:
        missing.append("a customer or product identifier")
    if "revenue" not in columns and "quantity" not in columns:
        missing.append("revenue or quantity")
    if not missing:
        return None
    return "missing " + ", ".join(missing)
