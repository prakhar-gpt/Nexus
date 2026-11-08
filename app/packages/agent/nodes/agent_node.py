"""Agent decision node invoking the LLM with tool schemas."""

from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage

from packages.agent.state import AgentState, MAX_TOOL_STEPS, MESSAGE_TAIL
from packages.agent.tools.definitions import TOOLS


def agent_node(state: AgentState, model, system_prompt: str) -> dict:
    """Invoke the chat model to either generate an answer or pick a tool."""
    allowed = state.get("step_count", 0) < MAX_TOOL_STEPS
    chat = model.bind_tools(TOOLS) if allowed else model
    tail = list(state.get("messages") or [])[-MESSAGE_TAIL:]
    try:
        response = chat.invoke([SystemMessage(content=system_prompt), *tail])
    except Exception:
        response = AIMessage(content="The model could not be reached.")
    return {"messages": [response]}
