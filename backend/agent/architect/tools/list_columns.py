"""list_columns tool: lists headers, count, and inferred pandas dtypes."""

from __future__ import annotations

from typing import Any
from langchain_core.tools import tool
import pandas as pd

from agent.architect.tools.profiler_common import sanitize_data_text, truncate_val


def execute_list_columns(df: pd.DataFrame) -> dict[str, Any]:
    cols_info = []
    for col in df.columns:
        dtype_str = str(df[col].dtype)
        cols_info.append({
            "source_name": sanitize_data_text(truncate_val(col)),
            "inferred_dtype": dtype_str,
        })
    return {
        "total_columns": len(cols_info),
        "total_rows": len(df),
        "columns": cols_info,
    }


def make_list_columns_tool(df: pd.DataFrame):
    @tool("list_columns")
    def list_columns_tool() -> dict[str, Any]:
        """List all header names in the uploaded file, column count, and inferred pandas dtypes."""
        return execute_list_columns(df)

    return list_columns_tool

