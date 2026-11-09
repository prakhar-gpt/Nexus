"""test_parse tool: test parsing of the FULL column as numeric, integer, date, or boolean."""

from __future__ import annotations

from typing import Any
from langchain_core.tools import tool
import pandas as pd

from agent.architect.tools.profiler_common import sanitize_data_text, truncate_val
from ingest.schema_validation import check_column_parse_success


def execute_test_parse(
    df: pd.DataFrame,
    column: str,
    target_type: str,
    date_format: str | None = None,
) -> dict[str, Any]:
    target_col = None
    for col in df.columns:
        if col == column or col.strip().lower() == column.strip().lower():
            target_col = col
            break

    if target_col is None:
        return {"error": f"Column '{column}' not found."}

    vals = [str(x) for x in df[target_col].tolist()]
    rate, failures = check_column_parse_success(vals, target_type, date_format)
    sanitized_fails = [sanitize_data_text(truncate_val(f)) for f in failures]

    return {
        "column": target_col,
        "target_type": target_type,
        "date_format": date_format,
        "parse_success_rate": rate,
        "sample_failures": sanitized_fails,
    }


def make_test_parse_tool(df: pd.DataFrame):
    @tool("test_parse")
    def test_parse_tool(column: str, type: str, date_format: str | None = None) -> dict[str, Any]:
        """Test parse success rate of the FULL column as 'text', 'numeric', 'integer', 'date', or 'boolean'."""
        return execute_test_parse(df, column, type, date_format=date_format)

    return test_parse_tool

