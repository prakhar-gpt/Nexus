"""Verify that every number in a draft answer appears in the tool output or query context."""

from __future__ import annotations

import re
from decimal import Decimal

_NUMBER = re.compile(
    r"(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:st|nd|rd|th)?(?![\w.])",
    re.IGNORECASE,
)


def extract_numbers(text: str) -> list[Decimal]:
    numbers = []
    for match in _NUMBER.finditer(text or ""):
        cleaned = re.sub(r"(?i)(?:st|nd|rd|th)$", "", match.group(0).replace(",", ""))
        try:
            numbers.append(Decimal(cleaned))
        except Exception:
            continue
    return numbers


def is_clarification(text: str) -> bool:
    """Return True when an answer is asking the user a question for clarification."""
    stripped = text.strip()
    return bool(stripped and "?" in stripped)


def check_answer(
    answer: str,
    rows: list[dict],
    context: list[str] | None = None,
) -> dict:
    """Return verified when every answer number matches a tool-output number or prompt/sql context."""
    if not rows and is_clarification(answer):
        return {"verified": True, "untraced": []}

    source_texts = [
        str(value)
        for row in rows
        for value in row.values()
        if value is not None and str(value) != ""
    ]
    if context:
        source_texts.extend([str(c) for c in context if c])
    source = " ".join(source_texts)
    source_numbers = extract_numbers(source)
    untraced = []
    for number in extract_numbers(answer):
        if not any(number == source for source in source_numbers):
            untraced.append(format(number, "f"))
    return {"verified": not untraced, "untraced": untraced}


def refusal_text(column: str) -> str:
    return (
        f"Cannot answer. {column} has no values in this workspace, "
        "so the question is refused."
    )


def draft_from_rows(rows: list[dict]) -> str:
    if not rows:
        return "The query returned no rows."
    lines = []
    for row in rows:
        parts = [
            f"{key}={value}"
            for key, value in row.items()
            if value is not None and str(value) != ""
        ]
        lines.append(", ".join(parts))
    return "\n".join(lines)
