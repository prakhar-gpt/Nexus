"""Workspace data access, thread management, and health check services using SQLAlchemy ORM."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any
from fastapi import HTTPException
from sqlalchemy import distinct, func, select, text

from db.models import Dataset, DatasetColumn, Quarantine, Run, Thread, Upload, Workspace, WorkspaceMember
from db.session import session_scope
from utils import clean_grain, parse_dataset_ids, to_uuid

HEALTH_SQL = ""


def get_workspace_meta(workspace_id: int | str) -> dict | None:
    """Return basic workspace record or None if absent or archived."""
    try:
        ws_uuid = to_uuid(workspace_id)
    except HTTPException:
        return None
    with session_scope() as session:
        ws = session.execute(
            select(Workspace).where(
                Workspace.id == ws_uuid,
                ~Workspace.name.startswith("[archived]"),
            )
        ).scalar_one_or_none()
        if not ws:
            return None
        return {"id": str(ws.id), "name": ws.name}


def list_workspaces() -> list[dict]:
    """List all active (non-archived) workspaces with file and run counts."""
    with session_scope() as session:
        stmt = (
            select(
                Workspace.id,
                Workspace.name,
                Workspace.created_at,
                func.count(distinct(Upload.id)).label("upload_count"),
                func.count(distinct(Run.id)).label("run_count"),
            )
            .outerjoin(Upload, Upload.workspace_id == Workspace.id)
            .outerjoin(Run, Run.workspace_id == Workspace.id)
            .where(~Workspace.name.startswith("[archived]"))
            .group_by(Workspace.id, Workspace.name, Workspace.created_at)
            .order_by(Workspace.id)
        )
        rows = session.execute(stmt).all()
        return [
            {
                "id": str(r.id),
                "name": r.name,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "upload_count": r.upload_count,
                "run_count": r.run_count,
            }
            for r in rows
        ]


def create_workspace(name: str, workspace_id: str | None = None, owner_id: str | None = None) -> dict:
    """Create a new data room workspace with UUID and owner membership."""
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="name is required")
    target_uuid = to_uuid(workspace_id) if workspace_id else uuid.uuid4()
    owner_uuid = to_uuid(owner_id or "00000000-0000-0000-0000-000000000001")

    with session_scope() as session:
        ws = Workspace(id=target_uuid, name=clean_name, owner_id=owner_uuid)
        session.add(ws)
        member = WorkspaceMember(workspace_id=target_uuid, user_id=owner_uuid, role="owner")
        session.add(member)
        session.flush()
        return {"id": str(ws.id), "name": ws.name}


def delete_workspace(workspace_id: int | str) -> dict:
    """Soft-delete / archive a workspace."""
    ws_uuid = to_uuid(workspace_id)
    with session_scope() as session:
        ws = session.get(Workspace, ws_uuid)
        if not ws or ws.name.startswith("[archived]"):
            raise HTTPException(status_code=404, detail="workspace not found")
        ws.name = f"[archived] {ws.name}"
    return {"ok": True, "id": str(workspace_id)}


def list_threads(workspace_id: int | str) -> list[dict]:
    """List active conversation threads for a workspace from the threads table."""
    ws_uuid = to_uuid(workspace_id)
    with session_scope() as session:
        stmt = (
            select(
                Thread.id,
                Thread.title,
                Thread.created_at,
                Thread.selected_dataset_ids,
                func.count(Run.id).label("turn_count"),
            )
            .outerjoin(
                Run,
                (Run.workspace_id == Thread.workspace_id)
                & (func.coalesce(Run.checker_result.op("->>")("thread_id"), "default") == Thread.id)
                & (Run.checker_result.op("->>")("deleted").is_(None))
                & (Run.question != "Schema Analysis"),
            )
            .where(Thread.workspace_id == ws_uuid)
            .group_by(Thread.id, Thread.workspace_id, Thread.title, Thread.created_at, Thread.selected_dataset_ids)
            .order_by(Thread.created_at.desc())
        )
        rows = session.execute(stmt).all()
        threads = []
        for r in rows:
            title = (r.title or "New Conversation").strip()
            if len(title) > 40:
                title = title[:37] + "..."
            threads.append(
                {
                    "id": r.id,
                    "title": title,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                    "turn_count": int(r.turn_count or 0),
                    "selected_dataset_ids": parse_dataset_ids(r.selected_dataset_ids),
                }
            )
        return threads


def get_or_create_thread(workspace_id: int | str, thread_id: str) -> dict:
    """Get thread record or create it server-side on first interaction with all current workspace datasets."""
    ws_uuid = to_uuid(workspace_id)
    clean_thread = (thread_id or "default").strip()

    with session_scope() as session:
        thread = session.get(Thread, (ws_uuid, clean_thread))
        if thread:
            return {
                "id": thread.id,
                "workspace_id": str(thread.workspace_id),
                "title": thread.title,
                "selected_dataset_ids": parse_dataset_ids(thread.selected_dataset_ids),
            }

        # First interaction: initialize with all active datasets for this workspace
        ds_ids = session.execute(
            select(Dataset.id).where(Dataset.workspace_id == ws_uuid).order_by(Dataset.created_at.asc())
        ).scalars().all()
        all_ds = [str(i) for i in ds_ids]

        new_thread = Thread(
            workspace_id=ws_uuid,
            id=clean_thread,
            title="New Conversation",
            selected_dataset_ids=all_ds,
        )
        session.add(new_thread)
        session.flush()
        return {
            "id": new_thread.id,
            "workspace_id": str(new_thread.workspace_id),
            "title": new_thread.title,
            "selected_dataset_ids": all_ds,
        }


def update_thread_datasets(workspace_id: int | str, thread_id: str, dataset_ids: list[str | int]) -> dict:
    """Update selected dataset IDs for a specific chat thread, strictly validating workspace ownership."""
    ws_uuid = to_uuid(workspace_id)
    clean_thread = (thread_id or "default").strip()
    get_or_create_thread(workspace_id, clean_thread)

    with session_scope() as session:
        thread = session.get(Thread, (ws_uuid, clean_thread))
        if not thread:
            raise HTTPException(status_code=404, detail="thread not found")

        # Validate dataset IDs belong to this workspace
        clean_uuids = []
        for i in dataset_ids:
            try:
                clean_uuids.append(to_uuid(i))
            except HTTPException:
                continue

        valid_ds = session.execute(
            select(Dataset.id).where(Dataset.workspace_id == ws_uuid, Dataset.id.in_(clean_uuids))
        ).scalars().all()
        valid_set = {str(v) for v in valid_ds}
        clean_ids = [str(i) for i in dataset_ids if str(i) in valid_set]

        thread.selected_dataset_ids = clean_ids
        thread.updated_at = func.now()
        session.flush()
        return {"ok": True, "thread_id": clean_thread, "selected_dataset_ids": clean_ids}


def delete_thread(workspace_id: int | str, thread_id: str) -> dict:
    """Delete a conversation thread from threads table and flag runs."""
    ws_uuid = to_uuid(workspace_id)
    clean_thread = (thread_id or "default").strip()

    with session_scope() as session:
        thread = session.get(Thread, (ws_uuid, clean_thread))
        if thread:
            session.delete(thread)

        runs = session.execute(
            select(Run).where(
                Run.workspace_id == ws_uuid,
                func.coalesce(Run.checker_result.op("->>")("thread_id"), "default") == clean_thread,
            )
        ).scalars().all()
        for r in runs:
            curr = dict(r.checker_result or {})
            curr["deleted"] = True
            r.checker_result = curr
        session.flush()
        return {"ok": True, "deleted_turns": len(runs)}


def list_workspace_datasets(workspace_id: int | str) -> list[dict]:
    """Retrieve all approved datasets for a workspace with row count, quarantine count, grain, and table label."""
    ws_uuid = to_uuid(workspace_id)
    with session_scope() as session:
        q_count_subq = (
            select(func.count(Quarantine.id))
            .where(Quarantine.upload_id == Dataset.upload_id)
            .scalar_subquery()
        )
        stmt = (
            select(
                Dataset.id,
                Dataset.upload_id,
                Dataset.table_name,
                Dataset.table_label,
                Dataset.grain,
                Dataset.row_count,
                Dataset.created_at,
                func.coalesce(q_count_subq, 0).label("quarantine_count"),
            )
            .where(Dataset.workspace_id == ws_uuid)
            .order_by(Dataset.created_at.asc())
        )
        rows = session.execute(stmt).all()
        datasets = []
        for r in rows:
            datasets.append(
                {
                    "id": str(r.id),
                    "upload_id": str(r.upload_id) if r.upload_id else None,
                    "table_name": r.table_name,
                    "table_label": r.table_label,
                    "grain": clean_grain(r.grain),
                    "row_count": int(r.row_count or 0),
                    "quarantine_count": int(r.quarantine_count or 0),
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
            )
        return datasets


def rename_dataset(workspace_id: int | str, dataset_id: int | str, new_label: str) -> dict:
    """Rename a dataset's friendly table label."""
    ws_uuid = to_uuid(workspace_id)
    ds_uuid = to_uuid(dataset_id)
    clean_label = new_label.strip()

    with session_scope() as session:
        ds = session.execute(
            select(Dataset).where(Dataset.id == ds_uuid, Dataset.workspace_id == ws_uuid)
        ).scalar_one_or_none()
        if not ds:
            raise HTTPException(status_code=404, detail="dataset not found in this workspace")
        ds.table_label = clean_label
    return {"ok": True, "dataset_id": str(dataset_id), "table_label": clean_label}


def remove_dataset(workspace_id: int | str, dataset_id: int | str) -> dict:
    """Remove a dataset in one atomic transaction: table, catalog rows, quarantine rows, and threads array_remove."""
    ws_uuid = to_uuid(workspace_id)
    ds_uuid = to_uuid(dataset_id)

    with session_scope() as session:
        ds = session.execute(
            select(Dataset).where(Dataset.id == ds_uuid, Dataset.workspace_id == ws_uuid)
        ).scalar_one_or_none()
        if not ds:
            raise HTTPException(status_code=404, detail="dataset not found in this workspace")
        table_name = ds.table_name
        upload_id = ds.upload_id

        if upload_id:
            up = session.get(Upload, upload_id)
            if up and up.status in ("received", "processing", "uploading", "profiling"):
                raise HTTPException(status_code=400, detail="Cannot remove dataset while upload is running")
            # Remove quarantine rows
            quars = session.execute(
                select(Quarantine).where(Quarantine.upload_id == upload_id)
            ).scalars().all()
            for q in quars:
                session.delete(q)

        # Drop dynamic table in user_data schema
        session.execute(text(f'DROP TABLE IF EXISTS user_data."{table_name}" CASCADE;'))
        session.delete(ds)

        # Remove from thread selected_dataset_ids
        threads = session.execute(
            select(Thread).where(Thread.workspace_id == ws_uuid)
        ).scalars().all()
        for t in threads:
            if t.selected_dataset_ids and str(dataset_id) in t.selected_dataset_ids:
                t.selected_dataset_ids = [i for i in t.selected_dataset_ids if i != str(dataset_id)]
                t.updated_at = func.now()

    return {"ok": True, "dataset_id": str(dataset_id), "table_name": table_name}


def get_mappings(upload_id: int | str) -> list[dict]:
    """Retrieve column mapping proposals (legacy stub returning empty list)."""
    return []


def get_health(workspace_id: int | str) -> dict:
    """Compute table health stats and count quarantined rows dynamically for a workspace."""
    ws_uuid = to_uuid(workspace_id)
    with session_scope() as session:
        datasets = session.execute(
            select(Dataset).where(Dataset.workspace_id == ws_uuid)
        ).scalars().all()

        total_ds_rows = sum(d.row_count or 0 for d in datasets)

        counted_quarantine = session.execute(
            select(func.count(Quarantine.id))
            .join(Upload, Upload.id == Quarantine.upload_id)
            .where(Upload.workspace_id == ws_uuid)
        ).scalar() or 0

    return {
        "rows": str(total_ds_rows),
        "first_order": "",
        "last_order": "",
        "revenue": "",
        "quarantine": str(counted_quarantine),
        "datasets_count": len(datasets),
    }


def get_turns(workspace_id: int | str, thread_id: str | None = None) -> list[dict]:
    """Fetch conversation turns for a workspace, optionally filtered by thread_id, using SQLAlchemy ORM."""
    ws_uuid = to_uuid(workspace_id)
    with session_scope() as session:
        stmt = (
            select(Run)
            .where(
                Run.workspace_id == ws_uuid,
                Run.checker_result.op("->>")("deleted").is_(None),
                Run.question != "Schema Analysis",
                ~Run.answer.startswith('{"table_label"'),
                ~Run.answer.startswith('{"table_name"'),
            )
        )
        if thread_id:
            clean_thread = thread_id.strip()
            stmt = stmt.where(
                func.coalesce(Run.checker_result.op("->>")("thread_id"), "default") == clean_thread
            )
        stmt = stmt.order_by(Run.created_at.desc()).limit(50)
        runs = session.execute(stmt).scalars().all()

        turns = []
        for r in reversed(runs):
            check = r.checker_result or {}
            turns.append(
                {
                    "run_id": str(r.id),
                    "question": r.question,
                    "answer": r.answer or "",
                    "sql": r.sql_list or None,
                    "kind": check.get("kind"),
                    "verified": check.get("verified"),
                    "rows": check.get("rows") or [],
                    "steps": check.get("steps") or [],
                    "tools_used": check.get("tools_used") or [],
                    "python_results": check.get("python_results") or [],
                    "thread_id": check.get("thread_id") or "default",
                    "checker_result": check,
                }
            )
        return turns


def get_workspace_detail(workspace_id: int | str, thread_id: str | None = None) -> dict:
    """Assemble complete data room view using SQLAlchemy ORM: uploads, health, quarantine, threads, turns, and datasets."""
    room = get_workspace_meta(workspace_id)
    if room is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    ws_uuid = to_uuid(workspace_id)

    with session_scope() as session:
        upload_rows = session.execute(
            select(Upload.id, Upload.original_name, Upload.status, Upload.capabilities)
            .where(Upload.workspace_id == ws_uuid)
            .order_by(Upload.created_at.desc())
        ).all()
        uploads = [
            {"id": str(u.id), "original_name": u.original_name, "status": u.status}
            for u in upload_rows
        ]
        capabilities = upload_rows[0].capabilities if upload_rows and upload_rows[0].capabilities else {}

        quarantine_rows = session.execute(
            select(Quarantine.row_number, Quarantine.reason)
            .join(Upload, Upload.id == Quarantine.upload_id)
            .where(Upload.workspace_id == ws_uuid)
            .order_by(Quarantine.row_number.asc())
            .limit(20)
        ).all()
        quarantine = [
            {"row_number": q.row_number, "reason": q.reason}
            for q in quarantine_rows
        ]

    return {
        "id": room["id"],
        "name": room["name"],
        "uploads": uploads,
        "capabilities": capabilities,
        "datasets": list_workspace_datasets(workspace_id),
        "health": get_health(workspace_id),
        "quarantine": quarantine,
        "mappings": [],
        "threads": list_threads(workspace_id),
        "turns": get_turns(workspace_id, thread_id),
    }
