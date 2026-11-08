"""Upload ingestion and status tracking services."""

from __future__ import annotations

import asyncio
import csv
import io
import json
from fastapi import BackgroundTasks, HTTPException, Response

from apps.api.services.workspace_service import get_mappings, get_workspace_meta
from apps.api.sse import format_sse
from packages.agent.run_sql import SqlRejected, run_sql
from packages.ingest.clean import make_inert
from packages.ingest.pipeline import confirm_mappings, ingest, reserve_upload
from packages.ingest.store import execute

PROGRESS: dict[int, list[dict]] = {}


def handle_file_upload(
    workspace_id: int,
    filename: str,
    data: bytes,
    background: BackgroundTasks,
) -> dict:
    """Validate file, allocate upload ID, and enqueue ingestion job."""
    if get_workspace_meta(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file exceeds the 20 MB size cap")

    upload_id, path = reserve_upload(filename or "upload.csv", workspace_id, data)
    background.add_task(run_ingest_job, upload_id, path, workspace_id)
    return {"upload_id": upload_id}


def run_ingest_job(upload_id: int, path, workspace_id: int) -> None:
    """Background ingestion task."""
    def progress_callback(payload: dict) -> None:
        PROGRESS.setdefault(upload_id, []).append(payload)

    try:
        ingest(path, workspace_id, upload_id=upload_id, progress=progress_callback)
    except Exception:
        PROGRESS.setdefault(upload_id, []).append(
            {"event": "error", "message": "ingest failed"}
        )


async def stream_upload_events(upload_id: int):
    """Yield Server-Sent Events tracking the progress of an ingestion job."""
    sent = 0
    for _ in range(300):
        items = list(PROGRESS.get(upload_id, []))
        while sent < len(items):
            item = items[sent]
            sent += 1
            yield format_sse(item.get("event", "step"), item)
            if item.get("event") in {"done", "error"}:
                return
        await asyncio.sleep(0.2)
    yield format_sse("error", {"message": "ingest timed out"})


def update_column_mappings(upload_id: int, decisions: dict[str, str]) -> dict:
    """Save user column confirmations and finalize loading into sales_clean."""
    result = confirm_mappings(upload_id, decisions)
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


def get_upload_health_summary(upload_id: int, download: str | None = None):
    """Return upload health summary or stream quarantine CSV download."""
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
        "mappings": get_mappings(upload_id),
    }


def get_upload_mapping_detail(upload_id: int) -> dict:
    """Retrieve column mapping proposals, capabilities, and preview for an upload."""
    found = execute(
        "SELECT workspace_id, stored_name, status, capabilities FROM uploads "
        f"WHERE id = {int(upload_id)}"
    )
    if not found:
        raise HTTPException(status_code=404, detail="upload not found")
    upload = found[0]
    raw_caps = upload.get("capabilities") or "{}"
    try:
        caps = json.loads(raw_caps) if isinstance(raw_caps, str) else raw_caps
    except Exception:
        caps = {}
    mappings = get_mappings(upload_id)

    preview = []
    try:
        rows = run_sql(
            f"SELECT * FROM sales_clean WHERE upload_id = {int(upload_id)} LIMIT 10",
            int(upload["workspace_id"]),
        )
        for r in rows:
            attrs = {}
            if "attributes" in r and r["attributes"]:
                try:
                    attrs = json.loads(r["attributes"]) if isinstance(r["attributes"], str) else r["attributes"]
                except Exception:
                    pass
            clean_row = {k: v for k, v in r.items() if k not in ("attributes", "workspace_id", "upload_id")}
            preview.append({**clean_row, **attrs})
    except Exception:
        preview = []

    return {
        "mappings": mappings,
        "capabilities": caps or {},
        "preview": preview,
    }


