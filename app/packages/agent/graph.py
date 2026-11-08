"""One agent loop. The model chooses the next tool. The thread keeps the chat."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from packages.agent.checker import check_answer, is_clarification
from packages.agent.model import chat_model
from packages.agent.run_sql import SqlRejected
from packages.agent.run_sql import run_sql as execute_sql
from packages.agent.sql_guard import SqlRejected as GuardRejected
from packages.ingest.store import StoreError, execute

PROMPT = Path(__file__).resolve().parent / "prompts" / "system.md"
KB = Path(__file__).resolve().parents[2] / "kb"
SYSTEM = PROMPT.read_text(encoding="utf-8").strip()

MAX_TOOL_STEPS = 6
HISTORY_TURNS = 8
MESSAGE_TAIL = 30
STEP_LIMIT = "The step limit was reached before an answer."
_RUNNING = {
    "get_schema": "Looking at the columns…",
    "run_sql": "Running a query…",
    "read_kb": "Reading the notes…",
}
_FINISHED = {
    "get_schema": "Looked at the columns",
    "run_sql": "Ran a query",
    "read_kb": "Read the notes",
}

SCHEMA_SQL = (
    "SELECT count(*) AS rows, count(order_date) AS order_date, "
    "count(customer_id) AS customer_id, count(product_id) AS product_id, "
    "count(segment) AS segment, count(region) AS region, "
    "count(category) AS category, count(sub_category) AS sub_category, "
    "count(revenue) AS revenue, count(quantity) AS quantity, "
    "count(unit_price) AS unit_price, count(discount_pct) AS discount_pct, "
    "count(cost) AS cost, count(profit) AS profit, count(channel) AS channel "
    "FROM sales_clean"
)


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


class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    workspace_id: int
    rows: list
    sqls: list
    steps: list
    step_count: int
    answer: str
    check: dict
    kind: str


def _visible(message) -> str:
    """User-facing text. A streamed token keeps its leading space."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
                continue
            if not isinstance(part, dict):
                continue
            kind = str(part.get("type") or "")
            if kind in {"reasoning", "thinking", "reasoning_content"}:
                continue
            parts.append(str(part.get("text") or ""))
        return "".join(parts)
    return str(content or "")


def _text(message) -> str:
    return _visible(message).strip()


def _args(call: dict) -> dict:
    raw = call.get("args") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _schema(workspace_id: int) -> str:
    try:
        rows = execute_sql(SCHEMA_SQL, workspace_id)
    except (SqlRejected, GuardRejected) as exc:
        return f"rejected: {exc}"
    if not rows:
        return "0 rows"
    return ", ".join(f"{key}={value}" for key, value in rows[0].items())


def _query(sql: str, workspace_id: int) -> tuple[str, list[dict], str | None]:
    text = str(sql or "").strip()
    if not text:
        return "rejected: sql is empty", [], None
    try:
        rows = execute_sql(text, workspace_id)
    except (SqlRejected, GuardRejected) as exc:
        return f"rejected: {exc}", [], None
    if not rows:
        return "0 rows", [], text
    header = list(rows[0].keys())
    lines = [", ".join(header)]
    for row in rows:
        lines.append(", ".join("" if row.get(col) is None else str(row.get(col)) for col in header))
    return "\n".join(lines), rows, text


def _kb(path: str) -> str:
    root = KB.resolve()
    name = str(path or "").replace("\\", "/").strip().lstrip("/")
    if not name or ".." in name.split("/"):
        return "rejected: path is outside the knowledge base"
    candidate = (root / name).resolve()
    if candidate != root and root not in candidate.parents:
        return "rejected: path is outside the knowledge base"
    if not candidate.is_file():
        return "rejected: file not found"
    return candidate.read_text(encoding="utf-8")[:6000]


def _emit(payload: dict) -> None:
    try:
        get_stream_writer()(payload)
    except Exception:
        return


def _status_line(name: str, status: str) -> str:
    if status == "running":
        return _RUNNING.get(name, "Working…")
    if status == "error":
        return "That step was rejected"
    return _FINISHED.get(name, "Done")


def _history(workspace_id: int) -> list:
    try:
        rows = execute(
            "SELECT question, answer FROM runs "
            f"WHERE workspace_id = {int(workspace_id)} "
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
    """A tool-calling loop with a per-thread memory of the conversation."""

    def __init__(self, model):
        self.model = model
        self.model_name = getattr(model, "nexus_name", "scripted")
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self._agent)
        workflow.add_node("tools", self._tools)
        workflow.add_node("checker", self._checker)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", self._route, ["tools", "checker"])
        workflow.add_edge("tools", "agent")
        workflow.add_edge("checker", END)
        self.graph = workflow.compile(checkpointer=MemorySaver())

    def _agent(self, state: AgentState) -> dict:
        allowed = state.get("step_count", 0) < MAX_TOOL_STEPS
        chat = self.model.bind_tools(TOOLS) if allowed else self.model
        tail = list(state.get("messages") or [])[-MESSAGE_TAIL:]
        try:
            response = chat.invoke([SystemMessage(content=SYSTEM), *tail])
        except Exception:
            response = AIMessage(content="The model could not be reached.")
        return {"messages": [response]}

    def _route(self, state: AgentState) -> str:
        last = (state.get("messages") or [None])[-1]
        calls = getattr(last, "tool_calls", None)
        if calls and state.get("step_count", 0) < MAX_TOOL_STEPS:
            return "tools"
        return "checker"

    def _tools(self, state: AgentState) -> dict:
        last = state["messages"][-1]
        workspace_id = int(state["workspace_id"])
        rows = list(state.get("rows") or [])
        sqls = list(state.get("sqls") or [])
        steps = list(state.get("steps") or [])
        messages = []
        for call in last.tool_calls:
            name = call.get("name") or ""
            call_id = str(call.get("id") or f"{name}-{len(steps)}")
            args = _args(call)
            _emit(
                {
                    "id": call_id,
                    "tool": name or "unknown",
                    "status": "running",
                    "detail": _status_line(name, "running"),
                }
            )
            started = time.perf_counter()
            query = None
            found: list[dict] = []
            if name == "get_schema":
                text = _schema(workspace_id)
            elif name == "run_sql":
                text, found, query = _query(str(args.get("sql") or ""), workspace_id)
                rows.extend(found)
                if query:
                    sqls.append(query)
            elif name == "read_kb":
                text = _kb(str(args.get("path") or ""))
            else:
                text = "rejected: unknown tool"
            elapsed = int((time.perf_counter() - started) * 1000)
            status = "error" if text.startswith("rejected") else "ok"
            _emit(
                {
                    "id": call_id,
                    "tool": name or "unknown",
                    "status": status,
                    "ms": elapsed,
                    "detail": _status_line(name, status),
                    "query": query,
                    "row_count": len(found),
                }
            )
            steps.append(
                {
                    "id": call_id,
                    "tool": name or "unknown",
                    "status": status,
                    "ms": elapsed,
                    "detail": _status_line(name, status),
                }
            )
            messages.append(
                ToolMessage(content=text, tool_call_id=call.get("id") or "missing")
            )
        return {
            "messages": messages,
            "rows": rows,
            "sqls": sqls,
            "steps": steps,
            "step_count": state.get("step_count", 0) + 1,
        }

    def _checker(self, state: AgentState) -> dict:
        last = (state.get("messages") or [None])[-1]
        if getattr(last, "tool_calls", None):
            answer = STEP_LIMIT
        else:
            answer = _text(last) or "No answer was produced."
        rows = list(state.get("rows") or [])
        sqls = list(state.get("sqls") or [])
        lowered = answer.lower()
        if sqls:
            kind = "sql"
        elif "cannot answer" in lowered or "refus" in lowered:
            kind = "refusal"
        elif is_clarification(answer):
            kind = "clarification"
        else:
            kind = "unknown"

        context_texts = list(sqls)
        for msg in (state.get("messages") or []):
            content = getattr(msg, "content", "")
            if isinstance(content, str):
                context_texts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, str):
                        context_texts.append(part)
                    elif isinstance(part, dict) and "text" in part:
                        context_texts.append(str(part["text"]))

        check = check_answer(answer, rows, context=context_texts)
        if kind in ("refusal", "clarification"):
            check = {"verified": True, "untraced": []}

        steps = list(state.get("steps") or [])
        detail = "numbers match the tool output" if check["verified"] else "untraced number"
        if kind == "clarification":
            detail = "clarification requested"
        elif kind == "refusal":
            detail = "question refused"

        steps.append(
            {
                "tool": "checker",
                "status": "ok" if check["verified"] else "caveat",
                "ms": 0,
                "detail": detail,
            }
        )
        return {"answer": answer, "check": check, "kind": kind, "steps": steps}

    def _prepare(self, question: str, workspace_id: int, thread_id: str | None, history):
        config = {
            "configurable": {"thread_id": thread_id or f"workspace-{int(workspace_id)}"},
            "recursion_limit": 30,
        }
        try:
            snapshot = self.graph.get_state(config)
            existing = list((snapshot.values or {}).get("messages") or [])
        except Exception:
            existing = []
        incoming = [HumanMessage(content=question)]
        if not existing:
            prior = list(history) if history is not None else _history(workspace_id)
            incoming = prior + incoming
        payload = {
            "messages": incoming,
            "workspace_id": int(workspace_id),
            "rows": [],
            "sqls": [],
            "steps": [],
            "step_count": 0,
        }
        return config, payload

    def _result(self, values: dict, started: float) -> dict:
        sqls = list(values.get("sqls") or [])
        steps = list(values.get("steps") or [])
        return {
            "kind": values.get("kind") or "unknown",
            "plan": ", ".join(step["tool"] for step in steps),
            "sql": "\n\n".join(sqls) if sqls else None,
            "rows": list(values.get("rows") or []),
            "answer": values.get("answer") or "",
            "check": values.get("check") or {"verified": False, "untraced": []},
            "steps": steps,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "model": self.model_name,
        }

    def ask(self, question: str, workspace_id: int, *, thread_id: str | None = None, history=None) -> dict:
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
                    text = _chunk_text(message)
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


def _chunk_text(message) -> str:
    kind = getattr(message, "type", "")
    if kind in {"tool", "human", "system"}:
        return ""
    if getattr(message, "tool_call_chunks", None):
        return ""
    return _visible(message)


def ask(question: str, workspace_id: int, **kwargs) -> dict:
    agent = kwargs.pop("agent", None) or GRAPH
    return agent.ask(question, workspace_id, **kwargs)


def stream(question: str, workspace_id: int, **kwargs):
    agent = kwargs.pop("agent", None) or GRAPH
    yield from agent.watch(question, workspace_id, **kwargs)


GRAPH = Agent(chat_model())
