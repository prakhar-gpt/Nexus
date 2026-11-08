"""Declarative tool signatures exposed to the LLM.

The implementations here are schema stubs for tool binding.
The actual execution happens in handlers.py invoked by tools_node.
"""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def get_schema() -> str:
    """See which canonical sales columns, capabilities, and dynamic attributes have values in this data room."""


@tool
def run_sql(sql: str) -> str:
    """Run one read-only SELECT against sales_clean for data extraction and basic aggregations (GROUP BY, SUM, COUNT, AVG, MIN, MAX).
    Pass only the SQL text.
    STRICTLY FORBIDDEN: Do NOT calculate differences, percentages, growth rates, or ratios in SQL. Use run_python for all math."""


@tool
def read_kb(path: str) -> str:
    """Read one knowledge-base file by name, such as column_hints.md."""


@tool
def run_python(code: str, inputs: list[str]) -> str:
    """Run deterministic Python (pandas/numpy/math) on prior SQL results.
    MUST be used for all comparisons (comparing regions, segments, categories), differences, percentage changes, ratios, CAGR, and correlations.
    Prior SQL rows are automatically available in a pandas DataFrame named `data`.
    Code must assign a dict named `result` of {label: number}, e.g.
    result = {'difference': round(west - south, 2), 'pct_higher': round(((west - south) / south) * 100, 2)}.
    inputs is ['data'].
    No database access. No network. No file I/O."""


TOOLS = [get_schema, run_sql, read_kb, run_python]
