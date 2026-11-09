"""Text normalization and pre-processing for the number checker."""

from __future__ import annotations

import re

# Fenced code blocks with language tag or bare: ```...```
_FENCED_BLOCK_RE = re.compile(r"```[\s\S]*?```")

# Unicode punctuation mapping: hyphens, minus, and non-breaking spaces
_UNICODE_TRANSLATION = str.maketrans(
    {
        "\u2010": "-",  # Hyphen
        "\u2011": "-",  # Non-breaking hyphen
        "\u2012": "-",  # Figure dash
        "\u2013": "-",  # En dash
        "\u2014": "-",  # Em dash
        "\u2015": "-",  # Horizontal bar
        "\u2212": "-",  # Minus sign
        "\u00a0": " ",  # Non-breaking space
        "\u202f": " ",  # Narrow no-break space
        "\u2007": " ",  # Figure space
        "\u2009": " ",  # Thin space
    }
)


def normalize_text(text: str) -> str:
    """Normalize unicode hyphens, minus signs, and non-breaking spaces to ASCII."""
    if not text:
        return ""
    return text.translate(_UNICODE_TRANSLATION)


def strip_fenced_code_blocks(text: str) -> str:
    """Remove fenced code blocks (``` ... ```) so SQL/code blocks do not trigger false claims.

    Inline code spans (`...`) are intentionally PRESERVED because a number inside
    backticks in prose (e.g. `$9.9M`) represents a user-facing factual claim.
    """
    if not text:
        return ""
    return _FENCED_BLOCK_RE.sub("", text)

