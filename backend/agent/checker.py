"""Verify that every number in a draft answer appears in tool output only.

The whitelist is SQL result rows PLUS run_python results. Numbers that appear
only in the conversation history are NOT whitelisted — the model must query
again for any figure it wants to cite.

Exception: numbers that appear verbatim in the last human question are exempt
(the user may quote a target, threshold, or prior figure).
Non-claims (years, dates, ordinals, list markers, 'Top N') are also exempt.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------------------
# Number extraction with full formatting support
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
    (?!(?:,\d|\w))                   # not followed by comma-digit or word char (allow trailing period or comma-space)
    """,
    re.VERBOSE | re.IGNORECASE,
)

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_ORDINAL_PROSE_RE = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)
_CODE_SPAN_RE = re.compile(r"`[^`]+`")


def _strip_code_spans(text: str) -> str:
    """Remove inline code spans so numbers inside them are not checked."""
    return _CODE_SPAN_RE.sub("", text)


def _is_exempt(raw: str, full_text: str, start: int = 0, end: int = 0) -> bool:
    """Return True when this raw match is a year, ordinal, Top-N reference, or list index."""
    s = raw.strip()
    if _YEAR_RE.fullmatch(s):
        return True
    if _ORDINAL_PROSE_RE.fullmatch(s):
        return True

    # Check date patterns (e.g. 2015-01-03, 08/11/2017, 01-03)
    window = full_text[max(0, start - 10) : min(len(full_text), end + 10)]
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", window) or re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", window):
        return True

    # Check duration suffixes like 4-year, 3-month, 10-day
    following = full_text[end : end + 10].lower()
    if re.match(r"^-(?:year|month|day|week|quarter|hr|min|sec)", following):
        return True

    # Check Top N: preceding text ends with 'Top ' or 'top '
    if start > 0:
        preceding = full_text[max(0, start - 10) : start]
        if re.search(r"(?i)\btop\s+$", preceding):
            return True
        # Check list numbering: e.g. "1. " or "2) " at line start
        at_line_start = re.search(r"(?:^|\n)\s*$", full_text[:start]) is not None
        at_list_punct = full_text[end : end + 2] in (". ", ") ", ".\t", ")\t")
        if at_line_start and at_list_punct:
            return True
    return False


def _normalize_raw(raw: str) -> Decimal | None:
    """Normalize a raw matched string to a Decimal value."""
    text = raw.strip()
    # Strip currency symbols
    for sym in ("$", "\u00a3", "\u20ac"):
        text = text.replace(sym, "")
    # Strip ordinal suffixes
    text = re.sub(r"(?i)(?:st|nd|rd|th)$", "", text)
    # Handle percent
    if text.endswith("%"):
        text = text[:-1]
    # Handle K/M/B suffixes
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
    # Remove thousands separators
    text = text.replace(",", "")
    if not text:
        return None
    try:
        value = Decimal(text) * scale
    except InvalidOperation:
        return None
    return value


def _displayed_precision(raw: str) -> int:
    """Return the number of decimal places visible in a raw number string."""
    clean = raw.replace(",", "")
    clean = re.sub(r"(?i)[kmb%\$\u00a3\u20ac]$", "", clean)
    clean = re.sub(r"(?i)(?:st|nd|rd|th)$", "", clean)
    if "." in clean:
        return len(clean.split(".", 1)[1])
    return 0


def _scale_of(raw: str) -> int:
    r = raw.strip().lower()
    if r.endswith("b"):
        return 1_000_000_000
    if r.endswith("m"):
        return 1_000_000
    if r.endswith("k"):
        return 1_000
    return 1


def _tolerance(raw: str, value: Decimal) -> Decimal:
    """Return acceptable match tolerance based on displayed precision and suffixes.

    - Shown to N decimals: tolerance = 0.5 * 10^(-N)
    - Shown as $1.2M or similar: 5% of the rounding step
    - Integer: 0.5
    """
    raw_stripped = raw.strip()
    has_scale = bool(re.search(r"(?i)[kmb]$", raw_stripped.rstrip("%").rstrip("$\u00a3\u20ac")))
    if has_scale:
        prec = _displayed_precision(raw_stripped)
        step = (Decimal(10) ** (-prec)) * Decimal(_scale_of(raw_stripped))
        return step * Decimal("0.05")
    prec = _displayed_precision(raw_stripped)
    return Decimal("0.5") * (Decimal(10) ** (-prec))


def extract_numbers(text: str) -> list[Decimal]:
    """Extract all numeric claims from answer text, excluding exempt patterns."""
    clean = _strip_code_spans(text or "")
    numbers = []
    for match in _NUMBER.finditer(clean):
        raw = match.group(0)
        start, end = match.span()
        if _is_exempt(raw, clean, start, end):
            continue
        normalized = _normalize_raw(raw)
        if normalized is not None:
            numbers.append(normalized)
    return numbers


# ---------------------------------------------------------------------------
# Source number extraction from tool outputs
# ---------------------------------------------------------------------------

def _source_numbers_from_rows(rows: list[dict]) -> list[tuple[Decimal, str]]:
    """Extract (value, raw_string) from SQL result rows."""
    result = []
    for row in rows:
        for val in row.values():
            if val is None or str(val).strip() == "":
                continue
            raw = str(val).strip()
            norm = _normalize_raw(raw)
            if norm is not None:
                result.append((norm, raw))
    return result


def _source_numbers_from_python(python_results: dict | list) -> list[tuple[Decimal, str]]:
    """Extract (value, raw_string) from run_python results dict or list."""
    result = []
    if isinstance(python_results, dict):
        items = python_results.values()
    elif isinstance(python_results, list):
        items = [item.get("value") for item in python_results if isinstance(item, dict) and "value" in item]
    else:
        items = []

    for val in items:
        if val is None:
            continue
        try:
            d = Decimal(str(val))
            result.append((d, str(val)))
        except InvalidOperation:
            continue
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_METHOD_CLAIM = re.compile(
    r"\b(?:using|with|via)\s+(?:python|the\s+math\s+tool|the\s+python\s+tool|the\s+tool)\b|"
    r"\bcalculated\s+(?:with|using|in)\s+(?:python|the\s+math\s+tool|the\s+tool)\b|"
    r"\bpython\s+calculation\b",
    re.IGNORECASE,
)


def is_clarification(text: str) -> bool:
    """Return True when an answer is asking the user a question for clarification."""
    stripped = text.strip()
    return bool(stripped and "?" in stripped)


def check_answer(
    answer: str,
    rows: list[dict],
    context: list[str] | None = None,
    python_results: dict | list | None = None,
    question_text: str | None = None,
) -> dict:
    """Return verified when every answer number is traceable to tool output.

    Whitelist = SQL rows + python_results only.
    Numbers that appear verbatim in the question text are also exempt (user quotes).
    The `context` parameter is accepted for backward compatibility.
    """
    if not rows and not python_results and is_clarification(answer):
        return {"status": "verified", "verified": True, "untraced": [], "matched": []}

    source_pairs: list[tuple[Decimal, str]] = []
    source_pairs.extend(_source_numbers_from_rows(rows))
    if python_results:
        source_pairs.extend(_source_numbers_from_python(python_results))

    # User-quoted numbers in question
    question_numbers: list[Decimal] = []
    if question_text:
        question_numbers = extract_numbers(question_text)

    answer_clean = _strip_code_spans(answer or "")
    untraced: list[str] = []
    matched: list[str] = []

    for match in _NUMBER.finditer(answer_clean):
        raw = match.group(0)
        start, end = match.span()
        if _is_exempt(raw, answer_clean, start, end):
            continue
        value = _normalize_raw(raw)
        if value is None:
            continue
        tol = _tolerance(raw, value)
        is_pct = raw.strip().endswith("%")

        # Question exemption
        matched_in_question = False
        for qv in question_numbers:
            if abs(value - qv) <= tol:
                matched_in_question = True
                break
        if matched_in_question:
            matched.append(raw)
            continue

        # Whitelist matching (including percent vs fraction normalisation)
        found_match = False
        for sv, _ in source_pairs:
            # 1. Direct match with tolerance
            if abs(value - sv) <= tol:
                found_match = True
                break
            # 2. Answer is percent (e.g. 49.53%), source is fraction (0.4953)
            if is_pct and abs((value / 100) - sv) <= (tol / 100):
                found_match = True
                break
            # 3. Answer is fraction (e.g. 0.4953), source is percent (49.53)
            if not is_pct and abs((value * 100) - sv) <= (tol * 100):
                found_match = True
                break

        if found_match:
            matched.append(raw)
        else:
            untraced.append(raw)

    # Flag claims of using Python or math tools when no run_python results exist
    if not python_results:
        claim_match = _METHOD_CLAIM.search(answer_clean)
        if claim_match:
            untraced.append(f"method claim '{claim_match.group(0)}' without tool execution")

    status = "verified" if not untraced else "caveat"
    return {
        "status": status,
        "verified": not untraced,
        "untraced": untraced,
        "matched": matched,
    }


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
