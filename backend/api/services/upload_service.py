"""Upload ingestion, Schema Architect orchestration, and status tracking services."""

from __future__ import annotations

import csv
import io
import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import BackgroundTasks, HTTPException, Response
from sqlalchemy import func, select

from api.services.event_stream import stream_upload_events
from api.services.schema_questions import generate_suggested_questions
from api.services.workspace_service import get_or_create_thread, get_workspace_meta
from db.models import AgentEvent, Dataset, Quarantine, Run, Thread, Upload
from db.session import session_scope
from ingest import execute, ingest, reserve_upload
from ingest.custom_table import (
    compute_headers_hash,
    create_and_load_custom_table,
    get_cached_proposal,
)
from ingest.pipeline import UPLOAD_DIR
from ingest.reader import find_header, read_rows
from ingest.schema_validation import validate_schema_proposal
from utils import clean_grain, make_inert, to_uuid

PROGRESS: dict[str, list[dict]] = {}
_AGENT_SEQS: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Persistent Agent Event Ledger
# ---------------------------------------------------------------------------


def record_upload_event(
    upload_id: str | uuid.UUID,
    stage: str,
    event_type: str,
    label: str,
    payload: dict | None = None,
) -> dict:
    """Record an agent event in the unified agent_events table and in-memory cache."""
    up_str = str(upload_id)
    seq = _AGENT_SEQS.get(up_str, 0) + 1
    _AGENT_SEQS[up_str] = seq

    event_payload = dict(payload or {})
    event_payload.setdefault("upload_id", up_str)
    event_payload.setdefault("seq", seq)
    event_payload.setdefault("stage", stage)
    event_payload.setdefault("event_type", event_type)
    event_payload.setdefault("label", label)

    try:
        up_uuid = to_uuid(upload_id)
        with session_scope() as session:
            ev = AgentEvent(
                agent_kind="nexus",
                upload_id=up_uuid,
                seq=int(seq),
                stage=stage,
                event_type=event_type,
                label=label,
                payload=event_payload,
            )
            session.add(ev)
    except Exception:
        pass

    PROGRESS.setdefault(up_str, []).append(event_payload)
    return event_payload


def fetch_upload_events_from_db(upload_id: str | uuid.UUID, since_seq: int = 0) -> list[dict]:
    """Retrieve ordered persistent agent events since a given sequence number using SQLAlchemy."""
    up_str = str(upload_id)
    try:
        up_uuid = to_uuid(upload_id)
        with session_scope() as session:
            events = session.execute(
                select(AgentEvent)
                .where(AgentEvent.upload_id == up_uuid, AgentEvent.seq > since_seq)
                .order_by(AgentEvent.seq.asc())
            ).scalars().all()
            return [
                {
                    "seq": e.seq,
                    "stage": e.stage,
                    "event_type": e.event_type,
                    "label": e.label,
                    **(e.payload or {}),
                }
                for e in events
            ]
    except Exception:
        return [
            item for item in PROGRESS.get(up_str, [])
            if item.get("seq", 0) > since_seq
        ]


def _architect_step_event(
    upload_id: str,
    tool: str,
    status: str,
    evidence: str = "",
    payload: dict | None = None,
) -> dict:
    tool_labels = {
        "check_file": ("Checked the file", "parse"),
        "read_types": ("Read column types and null rates", "profile"),
        "check_grain": ("Checked table grain", "profile"),
        "classify_columns": ("Classified columns", "profile"),
        "name_table": ("Named table and documented schema", "propose"),
    }
    label, stage = tool_labels.get(tool, (tool, "profile"))
    step_id = f"{tool}_{upload_id}"
    event_data: dict[str, Any] = {
        "event": "step",
        "id": step_id,
        "tool": tool,
        "status": status,
        "label": label,
    }
    if evidence:
        event_data["evidence"] = evidence
    if payload:
        event_data.update(payload)

    record_upload_event(
        upload_id=upload_id,
        stage=stage,
        event_type="step",
        label=label,
        payload=event_data,
    )
    return event_data


def _emit_handoff(
    upload_id: str,
    table_name: str,
    table_label: str,
    grain: str,
    loaded: int,
    quarantined: int,
    proposal: dict,
) -> None:
    questions = generate_suggested_questions(proposal)
    handoff_payload = {
        "event": "handoff",
        "table_name": table_name,
        "table_label": table_label,
        "grain": clean_grain(grain),
        "row_count": loaded,
        "quarantined_count": quarantined,
        "suggested_questions": questions,
        "proposal": proposal,
    }
    record_upload_event(
        upload_id,
        "handoff",
        "step",
        f"Ready to explore {table_label}",
        payload=handoff_payload,
    )


# ---------------------------------------------------------------------------
# Upload Registration & Pipeline Execution
# ---------------------------------------------------------------------------


def handle_file_upload(
    workspace_id: str | uuid.UUID,
    filename: str,
    data: bytes,
    background: BackgroundTasks,
) -> dict:
    """Validate file, allocate upload ID, and enqueue ingestion job."""
    if get_workspace_meta(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file exceeds the 50 MB size cap")

    upload_id, path = reserve_upload(filename or "upload.csv", workspace_id, data)

    record_upload_event(
        upload_id=upload_id,
        stage="received",
        event_type="done",
        label=f"Received {filename or 'file'}",
        payload={"file_name": filename, "file_size": len(data)},
    )

    background.add_task(run_ingest_job, upload_id, path, workspace_id)
    return {"upload_id": upload_id}


def run_ingest_job(upload_id: str, path: Path, workspace_id: str | uuid.UUID) -> None:
    """Background ingestion task emitting canonical stage events."""

    def progress_callback(payload: dict) -> None:
        if payload.get("event") == "architect_tool":
            tool = payload.get("tool", "")
            action = payload.get("action", "start")
            evidence = payload.get("evidence", "")
            status = "running" if action == "start" else "done"
            _architect_step_event(
                upload_id=upload_id,
                tool=tool,
                status=status,
                evidence=evidence,
                payload=payload,
            )

    try:
        record_upload_event(upload_id, "safety", "start", "Checking file safety and macros…")
        res = ingest(path, workspace_id, upload_id=upload_id, progress=progress_callback, allow_custom_schema=True)

        if res.status == "rejected":
            record_upload_event(
                upload_id,
                "safety",
                "error",
                res.reason or "File safety check failed",
                payload={"event": "error", "final": "rejected", "status": "rejected", "reason": res.reason or "The file was rejected."},
            )
        elif res.status == "needs_schema_review":
            for item in PROGRESS.get(str(upload_id), []):
                if item.get("event") == "step" and item.get("status") == "running":
                    item["status"] = "done"
            _init_schema_proposal(upload_id, path, workspace_id, progress_callback)
        elif res.status == "needs_confirmation":
            record_upload_event(
                upload_id,
                "review",
                "needs_confirmation",
                res.reason or "Low-confidence columns require confirmation",
                payload={"event": "done", "final": "needs_confirmation", "status": "needs_confirmation", "reason": res.reason},
            )
        else:
            record_upload_event(
                upload_id,
                "load",
                "done",
                f"Loaded {res.loaded_rows} rows",
                payload={"event": "done", "final": "loaded", "status": "loaded", "loaded_rows": res.loaded_rows},
            )
    except Exception as exc:
        record_upload_event(
            upload_id,
            "error",
            "error",
            str(exc) or "Ingest failed",
            payload={"event": "error", "final": "rejected", "status": "rejected", "reason": str(exc) or "Ingest failed"},
        )


# ---------------------------------------------------------------------------
# Schema Architect Orchestration & Endpoints
# ---------------------------------------------------------------------------


def _get_upload_df_and_rows(upload_id: str) -> tuple[Upload, list[tuple[int, list[str]]], int, list[str], pd.DataFrame]:
    """Load parsed tabular data and pandas dataframe for an upload using SQLAlchemy."""
    up_uuid = to_uuid(upload_id)
    with session_scope() as session:
        upload = session.get(Upload, up_uuid)
        if not upload:
            raise HTTPException(status_code=404, detail="upload not found")
        stored = upload.stored_name
        path = UPLOAD_DIR / stored
        if not path.is_file():
            raise HTTPException(status_code=404, detail="upload file not found on disk")

        rows = read_rows(path, path.suffix.lower())
        header_line, headers = find_header(rows)
        if header_line is None:
            raise HTTPException(status_code=400, detail="header row not found in file")

        data_rows = []
        for line_num, cells in rows:
            if line_num <= header_line:
                continue
            data_rows.append({
                headers[i]: cells[i].strip() if i < len(cells) else ""
                for i in range(len(headers))
            })

        df = pd.DataFrame(data_rows)
        session.expunge(upload)
        return upload, rows, header_line, headers, df


def _init_schema_proposal(
    upload_id: str,
    path: Path,
    workspace_id: str | uuid.UUID,
    progress_callback=None,
) -> dict:
    """Generate or retrieve cached schema proposal and store on upload record."""
    from agent.architect import run_schema_architect

    raw_rows = read_rows(path, path.suffix.lower())
    header_line, headers = find_header(raw_rows)
    header_hash = compute_headers_hash(headers)
    num_rows = max(0, len(raw_rows) - header_line - 1)

    record_upload_event(
        upload_id,
        "parse",
        "done",
        f"Parsed {len(headers)} columns",
        payload={
            "event": "step",
            "id": f"chk_{upload_id}",
            "tool": "check_file",
            "status": "done",
            "label": "Checked the file",
            "evidence": f"({len(headers)} columns, {num_rows:,} rows)",
        },
    )
    record_upload_event(
        upload_id,
        "profile",
        "done",
        "Read column types and null rates",
        payload={
            "event": "step",
            "id": f"types_{upload_id}",
            "tool": "read_types",
            "status": "done",
            "label": "Read column types and null rates",
        },
    )

    cached = get_cached_proposal(workspace_id, header_hash)
    if cached:
        proposal_dict = cached
    else:
        data_rows = []
        for line_num, cells in raw_rows:
            if line_num <= header_line:
                continue
            data_rows.append({
                headers[i]: cells[i].strip() if i < len(cells) else ""
                for i in range(len(headers))
            })
        df = pd.DataFrame(data_rows)

        label = path.stem.replace("_", " ").title()
        proposal_obj, tool_calls, lat, model_id = run_schema_architect(
            df,
            table_label=label,
            progress_callback=progress_callback,
        )
        proposal_dict = proposal_obj.model_dump()

    up_uuid = to_uuid(upload_id)
    with session_scope() as session:
        up = session.get(Upload, up_uuid)
        if up:
            up.schema_proposal = proposal_dict
            up.status = "needs_schema_review"

    record_upload_event(
        upload_id,
        "propose",
        "done",
        "Named table and documented schema",
        payload={
            "event": "step",
            "id": f"name_{upload_id}",
            "tool": "name_table",
            "status": "done",
            "label": "Named table and documented schema",
        },
    )

    review_payload = {
        "event": "done",
        "final": "needs_schema_review",
        "status": "needs_schema_review",
        "proposal": proposal_dict,
    }
    record_upload_event(
        upload_id,
        "review",
        "done",
        "Schema proposal ready for review",
        payload=review_payload,
    )
    return proposal_dict


def get_upload_schema(upload_id: str) -> dict:
    """GET /uploads/{id}/schema -> proposal, validation, and preview rows."""
    upload, raw_rows, header_line, headers, df = _get_upload_df_and_rows(upload_id)
    proposal = upload.schema_proposal

    if not proposal:
        raise HTTPException(status_code=404, detail="No schema proposal found for this upload")

    v_result = validate_schema_proposal(proposal)

    preview_rows = []
    for line_num, cells in raw_rows:
        if line_num <= header_line:
            continue
        row_dict = {
            headers[i]: cells[i].strip() if i < len(cells) else ""
            for i in range(len(headers))
        }
        preview_rows.append(row_dict)
        if len(preview_rows) >= 10:
            break

    return {
        "upload_id": upload_id,
        "file_name": upload.original_name,
        "status": upload.status,
        "proposal": proposal,
        "validation": v_result.model_dump(),
        "preview_rows": preview_rows,
        "row_count": max(0, len(raw_rows) - header_line - 1),
    }


def initiate_upload_schema(upload_id: str) -> dict:
    """POST /uploads/{id}/schema/initiate -> Trigger Schema Architect manually."""
    up_uuid = to_uuid(upload_id)
    with session_scope() as session:
        up = session.get(Upload, up_uuid)
        if not up:
            raise HTTPException(status_code=404, detail="upload not found")
        path = UPLOAD_DIR / up.stored_name
        ws_id = up.workspace_id

    _init_schema_proposal(upload_id, path, ws_id)
    return get_upload_schema(upload_id)


def update_upload_schema(upload_id: str, edits: dict[str, Any]) -> dict:
    """PUT /uploads/{id}/schema -> validate and persist user edits to schema proposal."""
    up_uuid = to_uuid(upload_id)
    with session_scope() as session:
        up = session.get(Upload, up_uuid)
        if not up:
            raise HTTPException(status_code=404, detail="upload not found")
        current_proposal = dict(up.schema_proposal or {})
        current_proposal.update(edits)

        v_result = validate_schema_proposal(current_proposal)
        up.schema_proposal = current_proposal

    return {
        "status": "updated",
        "proposal": current_proposal,
        "validation": v_result.model_dump(),
    }


def approve_upload_schema(upload_id: str, thread_id: str | None = None) -> dict:
    """POST /uploads/{id}/schema/approve -> create custom table, COPY rows, emit handoff."""
    upload, raw_rows, header_line, headers, df = _get_upload_df_and_rows(upload_id)
    proposal = upload.schema_proposal
    if not proposal:
        raise HTTPException(status_code=400, detail="No schema proposal to approve")

    v_result = validate_schema_proposal(proposal)
    if not v_result.valid:
        raise HTTPException(
            status_code=422,
            detail=f"Schema proposal has validation errors: {'; '.join(v_result.errors)}",
        )

    header_hash = compute_headers_hash(headers)
    table_lbl = (proposal.get("table_label") or "").strip()
    clean_orig = upload.original_name.rsplit(".", 1)[0].replace("_", " ").title()
    friendly_label = table_lbl or clean_orig or f"Dataset {upload_id}"
    if friendly_label.lower().endswith((".csv", ".xlsx", ".xls", ".tsv")):
        friendly_label = friendly_label.rsplit(".", 1)[0]

    loaded, quarantined, table_name = create_and_load_custom_table(
        upload_id=upload_id,
        workspace_id=upload.workspace_id,
        table_label=friendly_label,
        grain=proposal.get("grain", ""),
        grain_key_columns=proposal.get("grain_key_columns", []),
        columns=proposal.get("columns", []),
        raw_rows=raw_rows,
        header_line=header_line,
        header_hash=header_hash,
        proposal_json=proposal,
    )

    up_uuid = to_uuid(upload_id)
    ws_uuid = to_uuid(upload.workspace_id)
    with session_scope() as session:
        up = session.get(Upload, up_uuid)
        if up:
            up.status = "loaded"

        # Auto-check newly approved dataset in active thread if one exists
        ds = session.execute(
            select(Dataset.id).where(Dataset.upload_id == up_uuid).limit(1)
        ).scalar_one_or_none()
        new_ds_id = str(ds) if ds else None

        if new_ds_id:
            latest_thread = session.execute(
                select(Thread)
                .where(Thread.workspace_id == ws_uuid)
                .order_by(Thread.updated_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest_thread and new_ds_id not in latest_thread.selected_dataset_ids:
                latest_thread.selected_dataset_ids = list(latest_thread.selected_dataset_ids) + [new_ds_id]
                latest_thread.updated_at = func.now()

    questions = generate_suggested_questions(proposal)

    clean_thread = (thread_id or "").strip()
    if not clean_thread:
        with session_scope() as session:
            latest_t = session.execute(
                select(Thread.id)
                .where(Thread.workspace_id == ws_uuid)
                .order_by(Thread.updated_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            clean_thread = latest_t if latest_t else "default"

    get_or_create_thread(upload.workspace_id, clean_thread)

    clean_gr = clean_grain(proposal.get("grain", ""))
    handoff_text = f"I've loaded {friendly_label} ({clean_gr}, {loaded:,} rows). Here's what you can ask:"
    orig_name = upload.original_name or f"{friendly_label}.csv"
    question_text = f"Uploaded dataset: {orig_name}"
    checker_payload = {
        "thread_id": clean_thread,
        "kind": "upload",
        "verified": True,
        "table_name": table_name,
        "table_label": friendly_label,
        "grain": clean_gr,
        "row_count": loaded,
        "quarantined_count": quarantined,
        "suggested_questions": questions,
        "handoff_data": {
            "tableLabel": friendly_label,
            "tableName": table_name,
            "grain": clean_gr,
            "rowCount": loaded,
            "quarantinedCount": quarantined,
            "suggestedQuestions": questions,
        },
        "upload_id": str(upload_id),
    }

    with session_scope() as session:
        stale_runs = session.execute(
            select(Run).where(
                Run.workspace_id == ws_uuid,
                Run.checker_result.op("->>")("upload_id") == str(upload_id),
            )
        ).scalars().all()
        for r in stale_runs:
            session.delete(r)

        run = Run(
            workspace_id=ws_uuid,
            upload_id=up_uuid,
            question=question_text,
            answer=handoff_text,
            checker_result=checker_payload,
            latency_ms=0,
        )
        session.add(run)

    _emit_handoff(
        upload_id=str(upload_id),
        table_name=table_name,
        table_label=friendly_label,
        grain=proposal.get("grain", ""),
        loaded=loaded,
        quarantined=quarantined,
        proposal=proposal,
    )

    record_upload_event(
        upload_id,
        "load",
        "done",
        f"Loaded {loaded} rows into {table_name}",
        payload={
            "event": "done",
            "final": "loaded",
            "status": "loaded",
            "loaded_rows": loaded,
            "quarantined_rows": quarantined,
            "table_name": table_name,
            "table_label": friendly_label,
        },
    )

    return {
        "status": "loaded",
        "dataset_id": new_ds_id,
        "table_name": table_name,
        "table_label": friendly_label,
        "grain": clean_gr,
        "loaded_rows": loaded,
        "quarantined_rows": quarantined,
        "suggested_questions": questions,
    }


def reject_upload_schema(upload_id: str) -> dict:
    """POST /uploads/{id}/schema/reject -> mark rejected, no table created."""
    up_uuid = to_uuid(upload_id)
    with session_scope() as session:
        up = session.get(Upload, up_uuid)
        if up:
            up.status = "rejected"

    record_upload_event(
        upload_id,
        "review",
        "error",
        "Rejected by user during schema review",
        payload={
            "event": "done",
            "final": "rejected",
            "status": "rejected",
            "reason": "Rejected by user during schema review.",
        },
    )
    return {"status": "rejected", "message": "Schema rejected. No table was created."}


def regenerate_upload_schema(upload_id: str, user_hint: str | None = None) -> dict:
    """POST /uploads/{id}/schema/regenerate -> re-run architect (capped at 3 runs)."""
    upload, raw_rows, header_line, headers, df = _get_upload_df_and_rows(upload_id)
    up_uuid = to_uuid(upload_id)

    with session_scope() as session:
        runs_count = session.execute(
            select(func.count(Run.id)).where(Run.upload_id == up_uuid)
        ).scalar() or 0
        if runs_count >= 3:
            raise HTTPException(status_code=429, detail="Maximum 3 regeneration runs reached for this upload.")

    from agent.architect import run_schema_architect
    label = upload.original_name.rsplit(".", 1)[0].replace("_", " ").title()

    def progress_callback(payload: dict) -> None:
        PROGRESS.setdefault(str(upload_id), []).append(payload)

    proposal_obj, tool_calls, lat, model_id = run_schema_architect(
        df,
        table_label=label,
        user_hint=user_hint,
        progress_callback=progress_callback,
    )
    proposal_dict = proposal_obj.model_dump()

    with session_scope() as session:
        up = session.get(Upload, up_uuid)
        if up:
            up.schema_proposal = proposal_dict

    PROGRESS.setdefault(str(upload_id), []).append({
        "event": "architect_proposed",
        "proposal": proposal_dict,
        "regenerated": True,
    })

    return {
        "status": "regenerated",
        "run_count": runs_count + 1,
        "proposal": proposal_dict,
    }


def get_upload_status_for_rehydration(upload_id: str) -> dict:
    """GET /uploads/{id}/status — returns upload status, proposal, table metadata and suggested questions."""
    up_uuid = to_uuid(upload_id)
    with session_scope() as session:
        up = session.get(Upload, up_uuid)
        if not up:
            raise HTTPException(status_code=404, detail="upload not found")

        ds = session.execute(
            select(Dataset).where(Dataset.upload_id == up_uuid).limit(1)
        ).scalar_one_or_none()

        q_count = session.execute(
            select(func.count(Quarantine.id)).where(Quarantine.upload_id == up_uuid)
        ).scalar() or 0

        proposal = up.schema_proposal
        suggested_questions: list[dict] = []
        if proposal and up.status == "loaded":
            suggested_questions = generate_suggested_questions(proposal)

        return {
            "upload_id": str(up.id),
            "file_name": up.original_name,
            "status": up.status,
            "table_name": ds.table_name if ds else up.custom_table_name,
            "table_label": ds.table_label if ds else None,
            "grain": ds.grain if ds else None,
            "loaded_rows": int(ds.row_count or 0) if ds else 0,
            "quarantined_rows": int(q_count),
            "proposal": proposal,
            "suggested_questions": suggested_questions,
        }


def get_upload_quarantine_csv(upload_id: str) -> Response:
    """Stream quarantine CSV download for an upload."""
    up_uuid = to_uuid(upload_id)
    with session_scope() as session:
        rows = session.execute(
            select(Quarantine.row_number, Quarantine.reason, Quarantine.raw_json)
            .where(Quarantine.upload_id == up_uuid)
            .order_by(Quarantine.row_number.asc())
        ).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["row_number", "reason", "raw_json"])
    for r in rows:
        writer.writerow([r.row_number, make_inert(r.reason), make_inert(json.dumps(r.raw_json))])

    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=quarantine.csv"},
    )
