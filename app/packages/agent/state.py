"""Agent state definition, constants, and status formatting."""

from __future__ import annotations

from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

MAX_TOOL_STEPS = 6
HISTORY_TURNS = 8
MESSAGE_TAIL = 30
STEP_LIMIT = "The step limit was reached before an answer."

STATUS_RUNNING: dict[str, str] = {
    "get_schema": "Looking at the columns…",
    "run_sql": "Running a query…",
    "read_kb": "Reading the notes…",
}

STATUS_FINISHED: dict[str, str] = {
    "get_schema": "Looked at the columns",
    "run_sql": "Ran a query",
    "read_kb": "Read the notes",
}


class AgentState(TypedDict, total=False):
    """The shared state passed through the LangGraph loop."""

    messages: Annotated[list, add_messages]
    workspace_id: int
    rows: list
    sqls: list
    steps: list
    step_count: int
    answer: str
    check: dict
    kind: str


def format_status_line(name: str, status: str) -> str:
    """Format user-facing status lines emitted during tool execution."""
    if status == "running":
        return STATUS_RUNNING.get(name, "Working…")
    if status == "error":
        return "That step was rejected"
    return STATUS_FINISHED.get(name, "Done")
