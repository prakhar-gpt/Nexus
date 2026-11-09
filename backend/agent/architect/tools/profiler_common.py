"""Safe cell truncation and string formatting helpers for Schema Architect profiling tools."""

from __future__ import annotations

from typing import Any
import pandas as pd

MAX_CELL_CHARS = 80
MAX_SAMPLE_ROWS = 30
MAX_PREVIEW_ITEMS = 5


def truncate_val(val: Any) -> str:
    """Safely convert any cell value to truncated string."""
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if len(s) > MAX_CELL_CHARS:
        return s[:MAX_CELL_CHARS] + "..."
    return s


def sanitize_data_text(text: str) -> str:
    """Defuse potential prompt injections in untrusted cell text."""
    return text.replace("```", "'''").replace("<script>", "").replace("</script>", "")

