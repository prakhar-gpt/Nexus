"""Conversational streaming, audit logging, feedback, and result export services."""

from __future__ import annotations

import csv
import io
import traceback
from fastapi import HTTPException, Response

from db.models import Feedback, Run, Thread
from db.session import session_scope
from utils import format_sse, make_inert, to_uuid


def save_run(workspace_id: int | str, question: str, result: dict, thread_id: str = "default") -> str:
    """Persist an agent execution run, its SQL queries, answer, checker audit result, and python results via SQLAlchemy."""
    clean_thread = (thread_id or "default").strip()
    check_data = result.get("check") or {}
    raw_rows = list(result.get("rows") or [])
    checker_payload = {
        "status": check_data.get("status", "refused" if result["kind"] == "refusal" else ("verified" if check_data.get("verified") else "caveat")),
        "verified": check_data.get("verified", False),
        "untraced": check_data.get("untraced", []),
        "matched": check_data.get("matched", []),
        "provenance": check_data.get("provenance", [])[:100],
        "queries": result.get("queries", check_data.get("queries", [])),
        "ms": check_data.get("ms", 0),
        "kind": result["kind"],
        "rows": raw_rows[:25],
        "tools_used": result.get("tools_used", []),
        "steps": result.get("steps", []),
        "python_results": result.get("python_results", []),
        "thread_id": clean_thread,
    }
    py_results = result.get("python_results") or []
    ws_uuid = to_uuid(workspace_id)

    with session_scope() as session:
        # Ensure thread title reflects the first real user question instead of "New Conversation"
        thread = session.get(Thread, (ws_uuid, clean_thread))
        if thread and (not thread.title or thread.title == "New Conversation"):
            clean_q = (question or "").strip()
            if clean_q:
                thread.title = clean_q[:37] + "..." if len(clean_q) > 40 else clean_q

        run = Run(
            workspace_id=ws_uuid,
            question=question,
            plan=result.get("plan"),
            sql_list=result.get("sql"),
            answer=result.get("answer"),
            checker_result=checker_payload,
            python_results=py_results,
            latency_ms=int(result.get("latency_ms") or 0),
            tokens=0,
            cost=0.0,
            model=result.get("model") or "langgraph",
        )
        session.add(run)
        session.flush()
        return str(run.id)


def record_feedback(run_id: int | str, rating: str, reason: str | None = None) -> dict:
    """Record user thumbs up / down feedback via SQLAlchemy."""
    run_uuid = to_uuid(run_id)
    with session_scope() as session:
        run = session.get(Run, run_uuid)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        feedback = Feedback(run_id=run_uuid, rating=rating, reason=reason)
        session.add(feedback)
    return {"ok": True}


def export_result_csv(run_id: int | str) -> Response:
    """Export the SQL results of a run as a sanitized CSV download via SQLAlchemy."""
    run_uuid = to_uuid(run_id)
    with session_scope() as session:
        run = session.get(Run, run_uuid)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        stored = run.checker_result or {}
        answer = run.answer or ""

    rows = stored.get("rows") or []
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if rows:
        headers = list(rows[0].keys())
        writer.writerow(headers)
        for row in rows:
            writer.writerow([make_inert(str(row.get(header, ""))) for header in headers])
    else:
        writer.writerow(["answer"])
        writer.writerow([make_inert(answer)])
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=run-{run_id}.csv"},
    )


def generate_chat_events(
    workspace_id: int,
    question: str,
    stream_func,
    thread_id: str = "default",
    allowed_dataset_ids: list[int] | None = None,
):
    """Generator yielding formatted Server-Sent Events from the agent stream."""
    result = None
    clean_thread = (thread_id or "default").strip()
    try:
        # Pass thread_id and allowed_dataset_ids to the agent stream function
        stream_kwargs = {"thread_id": clean_thread, "allowed_dataset_ids": allowed_dataset_ids}
        try:
            stream_iter = stream_func(question, workspace_id, **stream_kwargs)
        except TypeError:
            try:
                stream_iter = stream_func(question, workspace_id, thread_id=clean_thread)
            except TypeError:
                stream_iter = stream_func(question, workspace_id)

        for kind, payload in stream_iter:
            if kind == "step" and isinstance(payload, dict):
                yield format_sse(
                    "step",
                    {
                        key: payload[key]
                        for key in ("id", "tool", "status", "detail", "ms", "query", "row_count", "input", "output")
                        if payload.get(key) is not None
                    },
                )
                if payload.get("query"):
                    yield format_sse(
                        "sql",
                        {
                            "query": payload["query"],
                            "row_count": payload.get("row_count") or 0,
                        },
                    )
            elif kind == "token":
                yield format_sse("token", {"text": payload})
            elif kind == "result":
                result = payload
    except Exception:
        traceback.print_exc()
        yield format_sse("error", {})
        return

    if not isinstance(result, dict):
        yield format_sse("error", {})
        return

    try:
        run_id = save_run(workspace_id, question, result, thread_id=clean_thread)
    except HTTPException:
        yield format_sse("error", {})
        return

    if result["sql"]:
        yield format_sse(
            "sql",
            {"query": result["sql"], "row_count": len(result["rows"])},
        )
    yield format_sse("check", {"kind": result["kind"], **result["check"]})
    yield format_sse(
        "done",
        {
            "run_id": run_id,
            "latency_ms": result["latency_ms"],
            "cost": 0,
            "tokens": 0,
            "model": result.get("model") or "langgraph",
            "rows": result["rows"],
            "tools_used": result.get("tools_used", []),
            "answer": result.get("answer") or "",
            "thread_id": clean_thread,
            "steps": result.get("steps", []),
            "queries": result.get("queries", []),
        },
    )
