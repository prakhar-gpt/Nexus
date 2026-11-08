"""Agent tools package organizing the 4 core tools: get_schema, run_sql, read_kb, run_python."""

from __future__ import annotations

import json
from agent.tools.get_schema import execute_schema, get_schema
from agent.tools.read_kb import execute_kb, read_kb
from agent.tools.run_python import clean_code, execute_python, execute_sandboxed, run_python
from agent.tools.run_sql import SqlRejected, execute_query, execute_sql, guard_sql, populated_count, run_sql, run_sql_tool


def parse_tool_args(call: dict) -> dict:
    """Safely extract dict arguments from a tool call payload."""
    raw = call.get("args") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


TOOLS = [get_schema, run_sql_tool, read_kb, run_python]

__all__ = [
    "TOOLS",
    "get_schema",
    "execute_schema",
    "run_sql",
    "execute_sql",
    "execute_query",
    "guard_sql",
    "SqlRejected",
    "populated_count",
    "read_kb",
    "execute_kb",
    "run_python",
    "execute_python",
    "execute_sandboxed",
    "clean_code",
    "parse_tool_args",
]
