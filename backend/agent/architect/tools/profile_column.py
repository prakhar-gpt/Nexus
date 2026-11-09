"""profile_column tool: null rate, distinct count, min/max, top values, and leading-zero detection."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any
from langchain_core.tools import tool
import pandas as pd

from agent.architect.tools.profiler_common import MAX_PREVIEW_ITEMS, sanitize_data_text, truncate_val


def execute_profile_column(df: pd.DataFrame, name: str) -> dict[str, Any]:
    target_col = None
    for col in df.columns:
        if col == name or col.strip().lower() == name.strip().lower():
            target_col = col
            break

    if target_col is None:
        return {"error": f"Column '{name}' not found."}

    series = df[target_col]
    non_null = series.dropna()
    clean_vals = [str(x).strip() for x in non_null if str(x).strip() not in {"", "nan", "none", "null"}]
    total_rows = len(df)
    null_count = total_rows - len(clean_vals)
    null_rate = round(null_count / total_rows, 4) if total_rows > 0 else 0.0

    distinct_count = len(set(clean_vals))
    counter = Counter(clean_vals)
    top_5 = [
        {"value": sanitize_data_text(truncate_val(val)), "count": count}
        for val, count in counter.most_common(MAX_PREVIEW_ITEMS)
    ]

    has_leading_zero = any(re.match(r"^0\d+$", v) for v in clean_vals[:200])
    min_val = sanitize_data_text(truncate_val(min(clean_vals))) if clean_vals else None
    max_val = sanitize_data_text(truncate_val(max(clean_vals))) if clean_vals else None

    return {
        "column": sanitize_data_text(target_col),
        "total_rows": total_rows,
        "null_count": null_count,
        "null_rate": null_rate,
        "distinct_count": distinct_count,
        "is_unique": distinct_count == total_rows,
        "has_leading_zero_ids": has_leading_zero,
        "min_sample": min_val,
        "max_sample": max_val,
        "top_values": top_5,
    }


def make_profile_column_tool(df: pd.DataFrame):
    @tool("profile_column")
    def profile_column_tool(name: str) -> dict[str, Any]:
        """Profile full column: null rate, distinct count, min/max, top values, and leading-zero detection."""
        return execute_profile_column(df, name)

    return profile_column_tool

