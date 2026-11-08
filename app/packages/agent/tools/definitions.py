"""Declarative tool signatures exposed to the LLM.

The implementations here are schema stubs for tool binding.
The actual execution happens in handlers.py invoked by tools_node.
"""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def get_schema() -> str:
    """See which sales columns have values in this data room."""


@tool
def run_sql(sql: str) -> str:
    """Run one read-only SELECT against sales_clean. Pass only the SQL text."""


@tool
def read_kb(path: str) -> str:
    """Read one knowledge-base file by name, such as column_hints.md."""


TOOLS = [get_schema, run_sql, read_kb]
