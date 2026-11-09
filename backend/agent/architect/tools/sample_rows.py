"""sample_rows tool: capped random sample rows with truncated cells."""

from __future__ import annotations

from langchain_core.tools import tool
import pandas as pd

from agent.architect.tools.profiler_common import MAX_SAMPLE_ROWS, sanitize_data_text, truncate_val


def execute_sample_rows(df: pd.DataFrame, n: int = 20, seed: int | None = None) -> list[dict[str, str]]:
    total_rows = len(df)
    if total_rows == 0:
        return []
    sample_size = min(max(1, int(n)), MAX_SAMPLE_ROWS, total_rows)
    sampled_df = df.sample(n=sample_size, random_state=seed) if total_rows > sample_size else df
    rows: list[dict[str, str]] = []
    for _, row in sampled_df.iterrows():
        row_dict = {
            sanitize_data_text(truncate_val(k)): sanitize_data_text(truncate_val(v))
            for k, v in row.items()
        }
        rows.append(row_dict)
    return rows


def make_sample_rows_tool(df: pd.DataFrame):
    @tool("sample_rows")
    def sample_rows_tool(n: int = 20, seed: int | None = None) -> list[dict[str, str]]:
        """Return random sample rows (capped at 30, cells truncated) to inspect cell contents safely."""
        return execute_sample_rows(df, n=n, seed=seed)

    return sample_rows_tool

