"""Verify that every number in a draft answer appears in the tool output."""

from __future__ import annotations

import re
from decimal import Decimal

_NUMBER = re.compile(
    r"(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w.])"
)


def extract_numbers(text: str) -> list[Decimal]:
    numbers = []
    for match in _NUMBER.finditer(text or ""):
        numbers.append(Decimal(match.group(0).replace(",", "")))
    return numbers


def check_answer(answer: str, rows: list[dict]) -> dict:
    """Return verified when every answer number matches a tool-output number."""
    source = " ".join(
        str(value)
        for row in rows
        for value in row.values()
        if value is not None and str(value) != ""
    )
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
