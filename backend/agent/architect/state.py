"""Architect agent state definition and constants."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict
from langgraph.graph.message import add_messages

from agent.architect.models import SchemaProposal

MAX_ARCHITECT_STEPS = 6


class ArchitectState(TypedDict, total=False):
    """The state passed through the Schema Architect LangGraph loop."""

    messages: Annotated[list, add_messages]
    step_count: int
    tool_calls_record: list[dict[str, Any]]
    final_proposal: SchemaProposal | None

