"""Nexus API. Routes, server-sent events, and in-process ingestion."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import traceback
import uuid
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from eval.runner import THRESHOLDS, evaluate
from packages.agent.run_sql import SqlRejected, run_sql
from packages.agent.loop import stream
from packages.ingest.clean import make_inert
from packages.ingest.pipeline import confirm_mappings, ingest, reserve_upload
from packages.ingest.store import StoreError, execute, sql_literal

app = FastAPI(title="Nexus")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROGRESS: dict[int, list[dict]] = {}

HEALTH_SQL = (
    "SELECT count(*) AS rows, min(order_date)::text AS first_order, "
    "max(order_date)::text AS last_order, "
    "coalesce(round(sum(revenue), 2)::text, '') AS revenue "
    "FROM sales_clean"
)


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class MappingUpdate(BaseModel):
    decisions: dict[str, str]


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    reason: str | None = None


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _workspace(workspace_id: int) -> dict | None:
    rows = execute(
        "SELECT id, name FROM workspaces "
        f"WHERE id = {int(workspace_id)}"
    )
    return rows[0] if rows else None


def _mappings(upload_id: int) -> list[dict]:
    saved = execute(
        "SELECT source_column, canonical_column, confidence, method, confirmed_by_user "
        f"FROM column_mapping WHERE upload_id = {int(upload_id)} ORDER BY id"
    )
    mappings = []
    for item in saved:
        confirmed = str(item["confirmed_by_user"]).lower() in {"t", "true"}
        mappings.append(
            {
                "source": item["source_column"],
                "canonical": item["canonical_column"] or None,
                "confidence": float(item["confidence"] or 0),
                "method": item["method"],
                "needs_confirmation": item["method"] == "llm" and not confirmed,
                "confirmed_by_user": confirmed,
            }
        )
    return mappings


def _health(workspace_id: int) -> dict:
    try:
        rows = run_sql(HEALTH_SQL, workspace_id)
    except SqlRejected:
        rows = []
    health = rows[0] if rows else {}
    counted = execute(
        "SELECT count(*) AS quarantine FROM quarantine q "
        "JOIN uploads u ON u.id = q.upload_id "
        f"WHERE u.workspace_id = {int(workspace_id)}"
    )
    return {
        "rows": health.get("rows") or "0",
        "first_order": health.get("first_order") or "",
        "last_order": health.get("last_order") or "",
        "revenue": health.get("revenue") or "",
        "quarantine": counted[0]["quarantine"] if counted else "0",
    }


@app.get("/workspaces")
def list_workspaces():
    return execute("SELECT id, name, created_at FROM workspaces ORDER BY id")


@app.post("/workspaces")
def create_workspace(body: WorkspaceCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    rows = execute(
        "INSERT INTO workspaces (name) "
        f"VALUES ({sql_literal(name)}) RETURNING id"
    )
    return {"id": int(rows[0]["id"]), "name": name}


def _turns(workspace_id: int) -> list[dict]:
    rows = execute(
        "SELECT id, question, answer, sql_list, checker_result FROM runs "
        f"WHERE workspace_id = {int(workspace_id)} ORDER BY id DESC LIMIT 20"
    )
    turns = []
    for row in reversed(rows):
        raw = row.get("checker_result") or "{}"
        try:
            check = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            check = {}
        turns.append(
            {
                "run_id": int(row["id"]),
                "question": row.get("question") or "",
                "answer": row.get("answer") or "",
                "sql": row.get("sql_list") or None,
                "kind": check.get("kind"),
                "verified": check.get("verified"),
                "rows": check.get("rows") or [],
            }
        )
    return turns


@app.get("/workspaces/{workspace_id}")
def get_workspace(workspace_id: int):
    room = _workspace(workspace_id)
    if room is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    uploads = execute(
        "SELECT id, original_name, status FROM uploads "
        f"WHERE workspace_id = {int(workspace_id)} ORDER BY id DESC"
    )
    latest = uploads[0]["id"] if uploads else None
    quarantine = execute(
        "SELECT q.row_number, q.reason FROM quarantine q "
        "JOIN uploads u ON u.id = q.upload_id "
        f"WHERE u.workspace_id = {int(workspace_id)} "
        "ORDER BY q.id DESC LIMIT 20"
    )
    return {
        "id": int(room["id"]),
        "name": room["name"],
        "uploads": uploads,
        "health": _health(workspace_id),
        "quarantine": quarantine,
        "mappings": _mappings(int(latest)) if latest else [],
        "turns": _turns(workspace_id),
    }


@app.post("/workspaces/{workspace_id}/uploads")
async def create_upload(
    workspace_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
):
    if _workspace(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file exceeds the 20 MB size cap")
    upload_id, path = reserve_upload(file.filename or "upload.csv", workspace_id, data)
    background.add_task(_run_ingest, upload_id, path, workspace_id)
    return {"upload_id": upload_id}


def _run_ingest(upload_id: int, path, workspace_id: int) -> None:
    def progress(payload: dict) -> None:
        PROGRESS.setdefault(upload_id, []).append(payload)

    try:
        ingest(path, workspace_id, upload_id=upload_id, progress=progress)
    except Exception:
        PROGRESS.setdefault(upload_id, []).append(
            {"event": "error", "message": "ingest failed"}
        )


@app.get("/uploads/{upload_id}/events")
async def upload_events(upload_id: int):
    return StreamingResponse(_upload_stream(upload_id), media_type="text/event-stream")


async def _upload_stream(upload_id: int):
    sent = 0
    for _ in range(300):
        items = list(PROGRESS.get(upload_id, []))
        while sent < len(items):
            item = items[sent]
            sent += 1
            yield _sse(item.get("event", "step"), item)
            if item.get("event") in {"done", "error"}:
                return
        await asyncio.sleep(0.2)
    yield _sse("error", {"message": "ingest timed out"})


@app.get("/uploads/{upload_id}/mapping")
def get_mapping(upload_id: int):
    return {"mappings": _mappings(upload_id)}


@app.put("/uploads/{upload_id}/mapping")
def put_mapping(upload_id: int, body: MappingUpdate):
    result = confirm_mappings(upload_id, body.decisions)
    return {
        "status": result.status,
        "reason": result.reason,
        "upload_id": result.upload_id,
        "loaded_rows": result.loaded_rows,
        "quarantined_rows": result.quarantined_rows,
        "mappings": [
            {
                "source": item.source,
                "canonical": item.canonical,
                "confidence": item.confidence,
                "method": item.method,
                "needs_confirmation": item.needs_confirmation,
                "confirmed_by_user": item.confirmed_by_user,
            }
            for item in result.mappings
        ],
    }


@app.get("/uploads/{upload_id}/health")
def upload_health(upload_id: int, download: str | None = None):
    found = execute(
        "SELECT id, workspace_id, original_name, status FROM uploads "
        f"WHERE id = {int(upload_id)}"
    )
    if not found:
        raise HTTPException(status_code=404, detail="upload not found")
    if download == "quarantine":
        rows = execute(
            "SELECT row_number, reason, raw_json FROM quarantine "
            f"WHERE upload_id = {int(upload_id)} ORDER BY row_number"
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["row_number", "reason", "raw_json"])
        for row in rows:
            writer.writerow(
                [
                    row["row_number"],
                    make_inert(row["reason"]),
                    make_inert(row["raw_json"]),
                ]
            )
        return Response(
            buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=quarantine.csv"},
        )
    upload = found[0]
    try:
        summary = run_sql(
            "SELECT count(*) AS rows, min(order_date)::text AS first_order, "
            "max(order_date)::text AS last_order, "
            "coalesce(round(sum(revenue), 2)::text, '') AS revenue "
            f"FROM sales_clean WHERE upload_id = {int(upload_id)}",
            int(upload["workspace_id"]),
        )
    except SqlRejected:
        summary = []
    return {
        "upload_id": int(upload_id),
        "original_name": upload["original_name"],
        "status": upload["status"],
        "summary": summary[0] if summary else {},
        "mappings": _mappings(upload_id),
    }


@app.post("/workspaces/{workspace_id}/chat")
def chat(workspace_id: int, body: ChatRequest):
    if _workspace(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    def events():
        result = None
        try:
            for kind, payload in stream(question, workspace_id):
                if kind == "step" and isinstance(payload, dict):
                    yield _sse(
                        "step",
                        {
                            key: payload[key]
                            for key in ("id", "tool", "status", "detail", "ms")
                            if payload.get(key) is not None
                        },
                    )
                    if payload.get("query"):
                        yield _sse(
                            "sql",
                            {
                                "query": payload["query"],
                                "row_count": payload.get("row_count") or 0,
                            },
                        )
                elif kind == "token":
                    yield _sse("token", {"text": payload})
                elif kind == "result":
                    result = payload
        except Exception:
            traceback.print_exc()
            yield _sse("error", {})
            return
        if not isinstance(result, dict):
            yield _sse("error", {})
            return
        try:
            run_id = _save_run(workspace_id, question, result)
        except HTTPException:
            yield _sse("error", {})
            return
        if result["sql"]:
            yield _sse(
                "sql",
                {"query": result["sql"], "row_count": len(result["rows"])},
            )
        yield _sse("check", {"kind": result["kind"], **result["check"]})
        yield _sse(
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

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _save_run(workspace_id: int, question: str, result: dict) -> int:
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


@app.post("/runs/{run_id}/feedback")
def add_feedback(run_id: int, body: FeedbackRequest):
    found = execute(f"SELECT id FROM runs WHERE id = {int(run_id)}")
    if not found:
        raise HTTPException(status_code=404, detail="run not found")
    execute(
        "INSERT INTO feedback (run_id, rating, reason) "
        f"VALUES ({int(run_id)}, {sql_literal(body.rating)}, {sql_literal(body.reason)})"
    )
    return {"ok": True}


@app.get("/eval/runs")
def list_eval_runs():
    rows = execute(
        "SELECT metrics_json, created_at FROM eval_results "
        "WHERE question_id = 'summary' ORDER BY id DESC LIMIT 1"
    )
    if not rows:
        return {"scores": None}
    return {"scores": json.loads(rows[0]["metrics_json"]), "created_at": rows[0]["created_at"]}


@app.post("/eval/runs")
def create_eval_run():
    result = evaluate()
    scores = {name: result["scores"][name] for name in THRESHOLDS}
    passed = result["exit_code"] == 0
    payload = json.dumps({"scores": scores, "problems": result["problems"]})
    eval_run_id = uuid.uuid4().hex[:12]
    execute(
        "INSERT INTO eval_results (eval_run_id, question_id, passed, metrics_json) "
        f"VALUES ({sql_literal(eval_run_id)}, 'summary', "
        f"{'true' if passed else 'false'}, {sql_literal(payload)}::jsonb)"
    )
    return {"eval_run_id": eval_run_id, "passed": passed, "scores": scores}


@app.get("/results/{run_id}/export")
def export_result(run_id: int):
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
