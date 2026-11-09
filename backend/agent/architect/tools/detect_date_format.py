"""detect_date_format tool: candidate date formats with counts and day/month ambiguity flag."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any
from langchain_core.tools import tool
import pandas as pd


def execute_detect_date_format(df: pd.DataFrame, column: str) -> dict[str, Any]:
    target_col = None
    for col in df.columns:
        if col == column or col.strip().lower() == column.strip().lower():
            target_col = col
            break

    if target_col is None:
        return {"error": f"Column '{column}' not found."}

    series = df[target_col].dropna()
    vals = [str(x).strip() for x in series if str(x).strip() not in {"", "nan", "null"}]
    if not vals:
        return {"column": target_col, "candidate_formats": [], "ambiguous_day_month": False}

    CANDIDATES = [
        ("%Y-%m-%d", r"^\d{4}-\d{1,2}-\d{1,2}$"),
        ("%m/%d/%Y", r"^\d{1,2}/\d{1,2}/\d{4}$"),
        ("%d/%m/%Y", r"^\d{1,2}/\d{1,2}/\d{4}$"),
        ("%d-%m-%Y", r"^\d{1,2}-\d{1,2}-\d{4}$"),
        ("%Y/%m/%d", r"^\d{4}/\d{1,2}/\d{1,2}$"),
        ("%b %d, %Y", r"^[A-Za-z]{3}\s+\d{1,2},\s*\d{4}$"),
    ]

    format_counts: Counter[str] = Counter()
    ambiguous_count = 0

    for s in vals:
        m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
        if m:
            part1, part2 = int(m.group(1)), int(m.group(2))
            if 1 <= part1 <= 12 and 1 <= part2 <= 12:
                ambiguous_count += 1

        for fmt, _ in CANDIDATES:
            try:
                datetime.strptime(s, fmt)
                format_counts[fmt] += 1
            except ValueError:
                pass

    ambiguous = ambiguous_count > 0 and len(vals) > 0 and (ambiguous_count / len(vals) > 0.5)

    return {
        "column": target_col,
        "candidate_formats": [
            {"format": fmt, "matches": cnt, "rate": round(cnt / len(vals), 4)}
            for fmt, cnt in format_counts.most_common(4)
        ],
        "ambiguous_day_month": ambiguous,
        "warning": "Ambiguous day/month ordering detected (e.g. 03/04/2024). Verify date_format carefully." if ambiguous else None,
    }


def make_detect_date_format_tool(df: pd.DataFrame):
    @tool("detect_date_format")
    def detect_date_format_tool(column: str) -> dict[str, Any]:
        """Detect candidate date formats and flag ambiguous day/month order (e.g. 03/04/2024)."""
        return execute_detect_date_format(df, column)

    return detect_date_format_tool

