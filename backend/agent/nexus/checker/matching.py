"""Matching engine comparing answer claims against tool evidence."""

from __future__ import annotations

import math
import re
from decimal import Decimal

# Words indicating a loss, decline, or negative direction
_LOSS_WORD_RE = re.compile(
    r"\b(?:loss|lost|decline|declined|drop|dropped|down|negative|deficit|below|decreased?)\b",
    re.IGNORECASE,
)


def displayed_precision(raw: str) -> int:
    """Return the number of decimal places visible in a raw number string."""
    clean = raw.replace(",", "")
    clean = re.sub(r"[kmb%\$\u00a3\u20ac]$", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"(?:st|nd|rd|th)$", "", clean, flags=re.IGNORECASE)
    if "." in clean:
        return len(clean.split(".", 1)[1])
    return 0


def scale_of(raw: str) -> int:
    r = raw.strip().lower()
    if r.endswith("b"):
        return 1_000_000_000
    if r.endswith("m"):
        return 1_000_000
    if r.endswith("k"):
        return 1_000
    return 1


def calculate_tolerance(raw: str, value: Decimal) -> Decimal:
    """Return acceptable match tolerance based on displayed precision and suffixes.

    - Scaled (k/M/B): 5% of rounding step (capped strictly at half a step).
    - Decimals: 0.5 * 10^(-N).
    - Plain integer: 0.5 default; integer rounding rules also apply in match_claim.
    """
    raw_stripped = raw.strip()
    has_scale = bool(re.search(r"[kmb]$", raw_stripped.rstrip("%").rstrip("$\u00a3\u20ac"), re.IGNORECASE))
    if has_scale:
        prec = displayed_precision(raw_stripped)
        step = (Decimal(10) ** (-prec)) * Decimal(scale_of(raw_stripped))
        # 5% of rounding step, never exceeding half a step
        return min(step * Decimal("0.05"), step * Decimal("0.5"))
    prec = displayed_precision(raw_stripped)
    return Decimal("0.5") * (Decimal(10) ** (-prec))


def is_loss_context(full_text: str, start: int) -> bool:
    """Return True if the text preceding the claim (~40 chars) contains a loss word."""
    window = full_text[max(0, start - 40) : start]
    return bool(_LOSS_WORD_RE.search(window))


def match_target_value(
    value: Decimal,
    raw: str,
    target: Decimal,
    is_loss: bool = False,
) -> bool:
    """Return True if value matches target Decimal considering tolerance, sign, and rounding."""
    tol = calculate_tolerance(raw, value)
    is_pct = raw.strip().endswith("%")
    prec = displayed_precision(raw)
    is_integer = (prec == 0) and not bool(re.search(r"[kmb]$", raw.strip(), re.IGNORECASE))

    candidates = [target]
    if target < 0 and is_loss:
        candidates.append(abs(target))

    for cand in candidates:
        if abs(value - cand) <= tol:
            return True

        if is_integer:
            cand_floor = Decimal(math.floor(float(cand)))
            cand_round = Decimal(round(float(cand)))
            if value == cand_floor or value == cand_round:
                return True

        if is_pct and abs((value / 100) - cand) <= (tol / 100):
            return True

        if not is_pct and abs((value * 100) - cand) <= (tol * 100):
            return True

    return False


def match_claim(
    value: Decimal,
    raw: str,
    source_pairs: list[tuple[Decimal, str]],
    is_loss: bool = False,
) -> bool:
    """Check if value matches any source number within tolerance, considering sign & rounding."""
    for sv, _ in source_pairs:
        if match_target_value(value, raw, sv, is_loss=is_loss):
            return True
    return False

