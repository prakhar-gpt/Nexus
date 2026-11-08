"""Deterministic audit node validating figures and classifying answer kinds."""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from packages.agent.checker import check_answer, is_clarification
from packages.agent.formatting import clean_answer_text
from packages.agent.state import AgentState, STEP_LIMIT


def checker_node(state: AgentState) -> dict:
    """Audit the drafted answer against SQL results, Python results, and question context."""
    last = (state.get("messages") or [None])[-1]
    if getattr(last, "tool_calls", None):
        answer = STEP_LIMIT
    else:
        answer = clean_answer_text(last) or "No answer was produced."

    rows = list(state.get("rows") or [])
    sqls = list(state.get("sqls") or [])
    python_rows = list(state.get("python_rows") or [])
    lowered = answer.lower()

    if sqls or python_rows:
        kind = "sql"
    elif "cannot answer" in lowered or "refus" in lowered:
        kind = "refusal"
    elif is_clarification(answer):
        kind = "clarification"
    else:
        kind = "unknown"

    # Extract user question text from the most recent HumanMessage
    question_text = None
    for msg in reversed(state.get("messages") or []):
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            question_text = str(getattr(msg, "content", ""))
            break

    py_dict = {
        item.get("label", str(i)): item.get("value")
        for i, item in enumerate(python_rows)
        if isinstance(item, dict)
    }

    check = check_answer(
        answer,
        rows,
        python_results=py_dict,
        question_text=question_text,
    )

    if kind in ("refusal", "clarification"):
        check = {"status": "verified", "verified": True, "untraced": [], "matched": []}

    steps = list(state.get("steps") or [])
    detail = "numbers match the tool output" if check.get("verified") else "untraced number"
    if kind == "clarification":
        detail = "clarification requested"
    elif kind == "refusal":
        detail = "question refused"

    steps.append(
        {
            "tool": "checker",
            "status": "ok" if check.get("verified") else "caveat",
            "ms": 0,
            "detail": detail,
        }
    )
    return {"answer": answer, "check": check, "kind": kind, "steps": steps}
