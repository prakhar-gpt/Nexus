"""Parse dates and numbers, and make formula-like text inert."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y")
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def parse_date(value: str):
    text = (value or "").strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_number(value: str) -> Decimal | None:
    text = (value or "").strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    for symbol in ("$", "€", "£", ","):
        text = text.replace(symbol, "")
    text = text.replace(" ", "")
    if text.endswith("%"):
        text = text[:-1]
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return -number if negative else number


def make_inert(value: str) -> str:
    """Store formula triggers as text. A leading apostrophe is not doubled."""
    if not value:
        return value
    if value.startswith("'"):
        return value
    if value[0] in _FORMULA_PREFIXES:
        return "'" + value
    return value
