"""Extraction of numeric tokens, claims, and exemptions from answer text."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from agent.nexus.normalization import normalize_text, strip_fenced_code_blocks

# ---------------------------------------------------------------------------
# Regex patterns for numbers, dates, ordinals, and year contexts
# ---------------------------------------------------------------------------

_NUMBER = re.compile(
    r"""
    (?<![.\w\d,])                    # not preceded by dot, word char, digit, or comma
    (?:[\$\u00a3\u20ac])?            # optional leading currency symbol ($, £, €)
    [+-]?                            # optional sign
    (?:
        \d{1,3}(?:,\d{3})*           # thousands-grouped (1,234 or 1,234,567)
        | \d+                        # plain integer
    )
    (?:\.\d+)?                       # optional decimal part
    (?:[KkMmBb](?![a-zA-Z]))?        # optional scale suffix (not followed by letter)
    (?:%)?                           # optional percent suffix
    (?:st|nd|rd|th)?                 # ordinal suffix
    (?!(?:,\d|\w))                   # not followed by comma-digit or word char
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Year contextual markers: preceded by in, during, since, FY, year, Q1-Q4, or month
_YEAR_CONTEXT_RE = re.compile(
    r"\b(?:in|during|since|fy|year|q[1-4]|january|february|march|april|may|june|july|"
    r"august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s*$",
    re.IGNORECASE,
)

# Date formats: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY
_EXACT_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"
)

_MONTH_DAY_RE = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+\d{1,2}\b|\b\d{1,2}\s+(?:january|february|"
    r"march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|"
    r"sep|sept|oct|nov|dec)\b",
    re.IGNORECASE,
)


def _is_date_token(raw: str, full_text: str, start: int, end: int) -> bool:
    """Return True if the match at [start:end] strictly falls inside an exact date token."""
    # Find all exact dates in full_text that overlap [start:end]
    for m in _EXACT_DATE_RE.finditer(full_text):
        if m.start() <= start and end <= m.end():
            return True
    for m in _MONTH_DAY_RE.finditer(full_text):
        if m.start() <= start and end <= m.end():
            return True
    return False


def is_contextual_year(raw: str, full_text: str, start: int, end: int) -> bool:
    """Return True if 1900-2099 is explicitly marked by date/year context."""
    s = raw.strip()
    if not (s.isdigit() and len(s) == 4 and 1900 <= int(s) <= 2099):
        return False

    # Check if part of recognized exact date
    if _is_date_token(raw, full_text, start, end):
        return True

    # Check preceding context (up to 30 characters before)
    preceding = full_text[max(0, start - 30) : start]
    if _YEAR_CONTEXT_RE.search(preceding):
        return True

    # Check following context (e.g. "2018 fiscal year", "2018-2019")
    following = full_text[end : min(len(full_text), end + 20)].lower()
    if re.match(r"^\s*(?:fiscal\s+year|fy|-|–|\/)", following):
        return True

    return False


def is_exempt_number(
    raw: str,
    full_text: str,
    start: int = 0,
    end: int = 0,
    row_count: int | None = None,
    sql_limit: int | None = None,
) -> bool:
    """Determine if matched raw token is an exempt non-claim (year, exact date, plausible Top N, code span)."""
    s = raw.strip()

    # Inline code span check: inside `...` (exempt if assignment/formula like `formula=9999`)
    left_tick = full_text.rfind("`", 0, start)
    right_tick = full_text.find("`", end)
    if left_tick != -1 and right_tick != -1 and "\n" not in full_text[left_tick:right_tick]:
        span_content = full_text[left_tick + 1 : right_tick]
        if "=" in span_content:
            return True

    # Exact date check
    if _is_date_token(raw, full_text, start, end):
        return True

    # Contextual year check
    if is_contextual_year(raw, full_text, start, end):
        return True

    # Duration suffix check: 4-year, 3-month, 10-day
    following = full_text[end : end + 10].lower()
    if re.match(r"^-(?:year|month|day|week|quarter|hr|min|sec)", following):
        return True

    # Ordinals: "1st quarter", "2nd half", "3rd place" (exempt as prose markers)
    clean_no_punct = re.sub(r"[,\$£€]", "", s, flags=re.IGNORECASE)
    if re.match(r"^\d+(?:st|nd|rd|th)$", clean_no_punct, re.IGNORECASE):
        return True

    # Top N: preceded by 'Top ' or 'top '
    if start > 0:
        preceding = full_text[max(0, start - 10) : start]
        if re.search(r"\btop\s+$", preceding, re.IGNORECASE):
            val = normalize_raw_number(raw)
            if val is not None:
                int_val = int(val)
                if int_val <= 25:
                    return True
                if row_count is not None and int_val <= max(row_count, 1):
                    return True
                if sql_limit is not None and int_val == sql_limit:
                    return True
            return False

        # List numbering at start of line: "1. " or "2) "
        at_line_start = re.search(r"(?:^|\n)\s*$", full_text[:start]) is not None
        at_list_punct = full_text[end : end + 2] in (". ", ") ", ".\t", ")\t")
        if at_line_start and at_list_punct:
            return True

    return False


def normalize_raw_number(raw: str) -> Decimal | None:
    """Normalize a raw matched string to a Decimal value, or None if unparseable."""
    text = raw.strip()
    for sym in ("$", "\u00a3", "\u20ac"):
        text = text.replace(sym, "")
    text = re.sub(r"(?:st|nd|rd|th)$", "", text, flags=re.IGNORECASE)
    if text.endswith("%"):
        text = text[:-1]

    scale = 1
    if text and text[-1].lower() == "k":
        scale = 1_000
        text = text[:-1]
    elif text and text[-1].lower() == "m":
        scale = 1_000_000
        text = text[:-1]
    elif text and text[-1].lower() == "b":
        scale = 1_000_000_000
        text = text[:-1]

    text = text.replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text) * scale
    except InvalidOperation:
        return None


def extract_numbers(
    text: str,
    row_count: int | None = None,
    sql_limit: int | None = None,
) -> list[Decimal]:
    """Extract all non-exempt Decimal claims from text."""
    normalized = normalize_text(text or "")
    clean = strip_fenced_code_blocks(normalized)
    numbers = []
    for match in _NUMBER.finditer(clean):
        raw = match.group(0)
        start, end = match.span()
        if is_exempt_number(raw, clean, start, end, row_count=row_count, sql_limit=sql_limit):
            continue
        val = normalize_raw_number(raw)
        if val is not None:
            numbers.append(val)
    return numbers

