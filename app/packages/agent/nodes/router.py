"""Router deciding conditional state transitions in the agent loop."""

from __future__ import annotations

from packages.agent.state import AgentState, MAX_TOOL_STEPS


def route_next_step(state: AgentState) -> str:
    """Route to 'tools' if the agent requested tool calls within step budget, else 'checker'."""
    last = (state.get("messages") or [None])[-1]
    calls = getattr(last, "tool_calls", None)
    if calls and state.get("step_count", 0) < MAX_TOOL_STEPS:
        return "tools"
    return "checker"

