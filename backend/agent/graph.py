"""LangGraph agent assembly, state management, and conversational execution."""

from __future__ import annotations

import time
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent.model import chat_model
from agent.nodes import (
    agent_node,
    checker_node,
    chunk_text,
    clean_answer_text,
    extract_visible_text,
    route_next_step,
    tools_node,
)
from agent.state import AgentState, HISTORY_TURNS, MAX_TOOL_STEPS

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8").strip()

# Backward compatibility alias for test suites
_chunk_text = chunk_text


def load_conversation_history(workspace_id: int, thread_id: str | None = None) -> list:
    """Load the most recent turns from the runs table for cold start thread hydration."""
    from ingest.store import StoreError, execute, sql_literal
    where_clauses = [f"workspace_id = {int(workspace_id)}"]
    if thread_id:
        clean_thread = thread_id.strip()
        where_clauses.append(f"coalesce(checker_result->>'thread_id', 'default') = {sql_literal(clean_thread)}")
    where_sql = " AND ".join(where_clauses)

    try:
        rows = execute(
            "SELECT question, answer FROM runs "
            f"WHERE {where_sql} "
            f"ORDER BY id DESC LIMIT {HISTORY_TURNS}"
        )
    except StoreError:
        return []
    messages = []
    for row in reversed(rows):
        question = (row.get("question") or "").strip()
        answer = (row.get("answer") or "").strip()
        if question:
            messages.append(HumanMessage(content=question))
        if answer:
            messages.append(AIMessage(content=answer))
    return messages


class Agent:
    """The LangGraph agent runtime with per-workspace and per-thread checkpoints."""

    def __init__(self, model):
        self.model = model
        self.model_name = getattr(model, "nexus_name", "scripted")

        workflow = StateGraph(AgentState)
        workflow.add_node("agent", lambda state: agent_node(state, self.model, SYSTEM_PROMPT))
        workflow.add_node("tools", tools_node)
        workflow.add_node("checker", checker_node)

        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", route_next_step, ["tools", "checker"])
        workflow.add_edge("tools", "agent")
        workflow.add_edge("checker", END)

        self.graph = workflow.compile(checkpointer=MemorySaver())

    def _prepare(self, question: str, workspace_id: int, thread_id: str | None, history):
        effective_thread = thread_id.strip() if thread_id else "default"
        config = {
            "configurable": {"thread_id": f"ws-{int(workspace_id)}-thread-{effective_thread}"},
            "recursion_limit": 30,
        }
        try:
            snapshot = self.graph.get_state(config)
            existing = list((snapshot.values or {}).get("messages") or [])
        except Exception:
            existing = []

        incoming = [HumanMessage(content=question)]
        if not existing:
            prior = list(history) if history is not None else load_conversation_history(workspace_id, effective_thread)
            incoming = prior + incoming

        payload = {
            "messages": incoming,
            "workspace_id": int(workspace_id),
            "rows": [],
            "sqls": [],
            "steps": [],
            "python_rows": [],
            "step_count": 0,
        }
        return config, payload

    def _result(self, values: dict, started: float) -> dict:
        sqls = list(values.get("sqls") or [])
        steps = list(values.get("steps") or [])
        python_rows = list(values.get("python_rows") or [])
        return {
            "kind": values.get("kind") or "unknown",
            "plan": ", ".join(step["tool"] for step in steps),
            "sql": "\n\n".join(sqls) if sqls else None,
            "rows": list(values.get("rows") or []),
            "python_results": python_rows,
            "tools_used": list(values.get("tools_used") or []),
            "answer": values.get("answer") or "",
            "check": values.get("check") or {"status": "caveat", "verified": False, "untraced": []},
            "steps": steps,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "model": self.model_name,
        }

    def ask(self, question: str, workspace_id: int, *, thread_id: str | None = None, history=None) -> dict:
        """Run the complete agent graph and return the audited final result."""
        started = time.perf_counter()
        config, payload = self._prepare(question, workspace_id, thread_id, history)
        values = self.graph.invoke(payload, config)
        return self._result(values, started)

    def watch(self, question: str, workspace_id: int, *, thread_id: str | None = None, history=None):
        """Yield tool lines and answer tokens as they happen, then the finished result."""
        started = time.perf_counter()
        config, payload = self._prepare(question, workspace_id, thread_id, history)
        saw_token = False

        try:
            for mode, chunk in self.graph.stream(
                payload, config, stream_mode=["custom", "messages"]
            ):
                if mode == "custom" and isinstance(chunk, dict):
                    yield ("step", chunk)
                elif mode == "messages":
                    message = chunk[0] if isinstance(chunk, tuple) else chunk
                    text = chunk_text(message)
                    if text:
                        saw_token = True
                        yield ("token", text)
        except Exception:
            saw_token = True
            yield ("token", "The model could not be reached.")

        try:
            values = self.graph.get_state(config).values or {}
        except Exception:
            values = {}

        result = self._result(values, started)
        if not saw_token and result["answer"]:
            yield ("token", result["answer"])
        yield ("result", result)


def ask(question: str, workspace_id: int, **kwargs) -> dict:
    agent = kwargs.pop("agent", None) or GRAPH
    return agent.ask(question, workspace_id, **kwargs)


def stream(question: str, workspace_id: int, **kwargs):
    agent = kwargs.pop("agent", None) or GRAPH
    yield from agent.watch(question, workspace_id, **kwargs)


GRAPH = Agent(chat_model())
