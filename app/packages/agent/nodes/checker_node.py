"""Deterministic audit node validating figures and classifying answer kinds."""

from __future__ import annotations

from packages.agent.checker import check_answer, is_clarification
from packages.agent.formatting import clean_answer_text
from packages.agent.state import AgentState, STEP_LIMIT


def checker_node(state: AgentState) -> dict:
    """Audit the drafted answer against SQL results and query context."""
    last = (state.get("messages") or [None])[-1]
    if getattr(last, "tool_calls", None):
        answer = STEP_LIMIT
    else:
        answer = clean_answer_text(last) or "No answer was produced."

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
