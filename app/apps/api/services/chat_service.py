"""Conversational streaming, audit logging, feedback, and result export services."""

from __future__ import annotations

import csv
import io
import json
import traceback
from fastapi import HTTPException, Response

from apps.api.sse import format_sse
from packages.ingest.clean import make_inert
from packages.ingest.store import StoreError, execute, sql_literal


def save_run(workspace_id: int, question: str, result: dict) -> int:
    """Persist an agent execution run, its SQL queries, answer, and checker audit result."""
    payload = json.dumps(
        {
            "verified": result["check"]["verified"],
            "untraced": result["check"]["untraced"],
            "kind": result["kind"],
            "rows": result["rows"],
        }
    )
    try:
        rows = execute(
            "INSERT INTO runs "
            "(workspace_id, question, plan, sql_list, answer, checker_result, "
            "latency_ms, tokens, cost, model) "
            f"VALUES ({int(workspace_id)}, {sql_literal(question)}, "
            f"{sql_literal(result['plan'])}, {sql_literal(result['sql'])}, "
            f"{sql_literal(result['answer'])}, {sql_literal(payload)}::jsonb, "
            f"{int(result['latency_ms'])}, 0, 0, {sql_literal(result.get('model') or 'langgraph')}) "
            "RETURNING id"
        )
    except StoreError as exc:
        raise HTTPException(status_code=500, detail="could not store the run") from exc
    return int(rows[0]["id"])


def record_feedback(run_id: int, rating: str, reason: str | None = None) -> dict:
    """Record user thumbs up / down feedback."""
    found = execute(f"SELECT id FROM runs WHERE id = {int(run_id)}")
    if not found:
        raise HTTPException(status_code=404, detail="run not found")
    execute(
        "INSERT INTO feedback (run_id, rating, reason) "
        f"VALUES ({int(run_id)}, {sql_literal(rating)}, {sql_literal(reason)})"
    )
    return {"ok": True}


def export_result_csv(run_id: int) -> Response:
    """Export the SQL results of a run as a sanitized CSV download."""
    found = execute(
        "SELECT answer, checker_result FROM runs "
        f"WHERE id = {int(run_id)}"
    )
    if not found:
        raise HTTPException(status_code=404, detail="run not found")
    stored = json.loads(found[0]["checker_result"])
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
        writer.writerow([make_inert(found[0]["answer"])])
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=run-{int(run_id)}.csv"},
    )


def generate_chat_events(workspace_id: int, question: str, stream_func):
    """Generator yielding formatted Server-Sent Events from the agent stream."""
    result = None
    try:
        for kind, payload in stream_func(question, workspace_id):
            if kind == "step" and isinstance(payload, dict):
                yield format_sse(
                    "step",
                    {
                        key: payload[key]
                        for key in ("id", "tool", "status", "detail", "ms")
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
        run_id = save_run(workspace_id, question, result)
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
            "answer": result.get("answer") or "",
        },
    )
