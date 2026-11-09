"""Deterministic heuristic question generation from dataset column profiles."""

from __future__ import annotations

from typing import Any

NON_MEASURE_KEYWORDS = (
    "postal",
    "zip",
    "code",
    "phone",
    "fax",
    "ssn",
    "ein",
    "id",
    "nbr",
    "num",
)

PRIORITY_MEASURES = (
    "revenue",
    "sales",
    "profit",
    "amount",
    "spend",
    "cost",
    "total",
    "margin",
    "quantity",
    "units",
    "discount",
)

PRIORITY_DIMENSIONS = (
    "category",
    "sub_category",
    "segment",
    "region",
    "channel",
    "department",
    "state",
    "brand",
    "country",
)

PRIORITY_DATES = ("order_date", "transaction_date", "date", "created_at", "ship_date")
PRIORITY_IDS = (
    "customer_name",
    "customer_id",
    "product_name",
    "product_id",
    "store_name",
    "store_id",
    "item",
)


def _sort_by_priority(items: list[str], priority_list: tuple[str, ...]) -> list[str]:
    def rank(name: str):
        lower = name.lower()
        for idx, pfx in enumerate(priority_list):
            if pfx in lower:
                return (0, idx)
        return (1, name)

    return sorted(items, key=rank)


def generate_suggested_questions(proposal: dict[str, Any]) -> list[dict[str, str]]:
    """Generate up to 3 suggested retail questions from column roles."""
    columns = proposal.get("columns") or []
    raw_measures = [
        c["column_name"]
        for c in columns
        if c.get("role") == "measure" and not c.get("excluded")
    ]
    raw_dimensions = [
        c["column_name"]
        for c in columns
        if c.get("role") == "dimension" and not c.get("excluded")
    ]
    raw_dates = [
        c["column_name"]
        for c in columns
        if c.get("role") == "date" and not c.get("excluded")
    ]
    raw_identifiers = [
        c["column_name"]
        for c in columns
        if c.get("role") == "identifier" and not c.get("excluded")
    ]

    filtered_measures = [
        m
        for m in raw_measures
        if not any(k in m.lower() for k in NON_MEASURE_KEYWORDS)
    ]

    measures = _sort_by_priority(filtered_measures, PRIORITY_MEASURES)
    dimensions = _sort_by_priority(raw_dimensions, PRIORITY_DIMENSIONS)
    dates = _sort_by_priority(raw_dates, PRIORITY_DATES)
    identifiers = _sort_by_priority(raw_identifiers, PRIORITY_IDS)

    suggestions: list[dict[str, str]] = []

    if measures and dimensions:
        m = measures[0].replace("_", " ")
        d = dimensions[0].replace("_", " ")
        suggestions.append({
            "question": f"What is total {m} by {d}?",
            "hint": "measure × dimension",
        })

    if measures and dates:
        m = measures[0].replace("_", " ")
        dt = dates[0].replace("_", " ")
        suggestions.append({
            "question": f"Show {m} over time by {dt}",
            "hint": "measure over date",
        })

    if measures and identifiers:
        m = measures[0].replace("_", " ")
        i = identifiers[0].replace("_", " ")
        suggestions.append({
            "question": f"Top 10 {i} by {m}",
            "hint": "top N by identifier",
        })

    if not suggestions and measures:
        m = measures[0].replace("_", " ")
        suggestions.append({
            "question": f"What is the total and average {m}?",
            "hint": "summary statistics",
        })

    return suggestions[:3]
