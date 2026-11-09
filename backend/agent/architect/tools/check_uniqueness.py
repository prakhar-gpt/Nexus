"""check_uniqueness tool: check whether a combination of columns forms a unique key across all rows."""

from __future__ import annotations

from typing import Any
from langchain_core.tools import tool
import pandas as pd


def execute_check_uniqueness(df: pd.DataFrame, columns: list[str]) -> dict[str, Any]:
    target_cols = []
    for col_name in columns:
        found = False
        for c in df.columns:
            if c == col_name or c.strip().lower() == col_name.strip().lower():
                target_cols.append(c)
                found = True
                break
        if not found:
            return {"error": f"Column '{col_name}' not found."}

    if not target_cols:
        return {"error": "No valid columns provided."}

    total_rows = len(df)
    subset = df[target_cols].dropna(how="all")
    dups = subset.duplicated().sum()
    is_unique = (dups == 0) and (len(subset) == total_rows)

    return {
        "columns": target_cols,
        "total_rows": total_rows,
        "duplicate_count": int(dups),
        "is_unique_key": bool(is_unique),
    }


def make_check_uniqueness_tool(df: pd.DataFrame):
    @tool("check_uniqueness")
    def check_uniqueness_tool(columns: list[str]) -> dict[str, Any]:
        """Check whether a combination of columns forms a unique grain key across all rows."""
        return execute_check_uniqueness(df, columns)

    return check_uniqueness_tool

