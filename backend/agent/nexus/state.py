"""Agent state definition, constants, and status formatting."""

from __future__ import annotations

from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

try:
    from config import settings
    MAX_TOOL_STEPS = settings.NEXUS_MAX_TOOL_STEPS
    HISTORY_TURNS = settings.NEXUS_HISTORY_TURNS
    MESSAGE_TAIL = settings.NEXUS_MESSAGE_TAIL
except Exception:
    MAX_TOOL_STEPS = 8
    HISTORY_TURNS = 8
    MESSAGE_TAIL = 20

STEP_LIMIT = "The step limit was reached before an answer."

STATUS_RUNNING: dict[str, str] = {
    "get_schema": "Looking at the columns...",
    "run_sql": "Running a query...",
    "read_kb": "Reading the notes...",
    "run_python": "Running Python calculation...",
}

STATUS_FINISHED: dict[str, str] = {
    "get_schema": "Looked at the columns",
    "run_sql": "Ran a query",
    "read_kb": "Read the notes",
    "run_python": "Ran calculation",
}


class AgentState(TypedDict, total=False):
    """The shared state passed through the LangGraph loop."""

    messages: Annotated[list, add_messages]
    workspace_id: str | int
    rows: list
    sqls: list
    steps: list
    step_count: int
    answer: str
    check: dict
    kind: str
    python_rows: list  # results from run_python: [{"label": str, "value": float}]
    sql_results: dict  # results by id or alias: {"sql_1": [...], ...}
    tools_used: list  # list of tool names called this turn: ["run_sql", "run_python"]
    allowed_dataset_ids: list[str | int] | None  # filtered datasets allowed for this thread


def format_status_line(name: str, status: str) -> str:
    """Format user-facing status lines emitted during tool execution."""
    if status == "running":
        return STATUS_RUNNING.get(name, "Working...")
    if status == "error":
        return "That step was rejected"
    return STATUS_FINISHED.get(name, "Done")
