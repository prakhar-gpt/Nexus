"""Workspace data access, thread management, and health check services."""

from __future__ import annotations

import json
import re
import uuid
from fastapi import HTTPException

from agent.nexus.tools import SqlRejected, run_sql
from ingest.store import execute, sql_id, sql_literal

HEALTH_SQL = (
    "SELECT count(*) AS rows, min(order_date)::text AS first_order, "
    "max(order_date)::text AS last_order, "
    "coalesce(round(sum(revenue), 2)::text, '') AS revenue "
    "FROM sales_clean"
)


def get_workspace_meta(workspace_id: int | str) -> dict | None:
    """Return basic workspace record or None if absent or archived."""
    rows = execute(
        "SELECT id, name FROM workspaces "
        f"WHERE id = {sql_id(workspace_id)} AND NOT (name LIKE '[archived]%')"
    )
    return rows[0] if rows else None


def list_workspaces() -> list[dict]:
    """List all active (non-archived) workspaces with file and run counts."""
    sql = (
        "SELECT w.id, w.name, w.created_at, "
        "count(DISTINCT u.id) AS upload_count, "
        "count(DISTINCT r.id) AS run_count "
        "FROM workspaces w "
        "LEFT JOIN uploads u ON u.workspace_id = w.id "
        "LEFT JOIN runs r ON r.workspace_id = w.id "
        "WHERE NOT (w.name LIKE '[archived]%') "
        "GROUP BY w.id, w.name, w.created_at "
        "ORDER BY w.id"
    )
    return execute(sql)


def create_workspace(name: str, workspace_id: str | None = None, owner_id: str | None = None) -> dict:
    """Create a new data room workspace with UUID."""
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="name is required")
    target_id = workspace_id or str(uuid.uuid4())
    try:
        rows = execute(
            "INSERT INTO workspaces (id, name) "
            f"VALUES ({sql_id(target_id)}, {sql_literal(clean_name)}) RETURNING id"
        )
    except Exception:
        # Fallback if DB column is still legacy identity sequence
        rows = execute(
            "INSERT INTO workspaces (name) "
            f"VALUES ({sql_literal(clean_name)}) RETURNING id"
        )
    created_id = str(rows[0]["id"])
    effective_owner = owner_id or "00000000-0000-0000-0000-000000000001"
    try:
        execute(
            f"INSERT INTO workspace_members (workspace_id, user_id, role) "
            f"VALUES ({sql_id(created_id)}, {sql_id(effective_owner)}, 'owner') "
            f"ON CONFLICT DO NOTHING"
        )
    except Exception:
        pass
    return {"id": created_id, "name": clean_name}


def delete_workspace(workspace_id: int | str) -> dict:
    """Soft-delete / archive a workspace."""
    ws = get_workspace_meta(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")
    archived_name = f"[archived] {ws['name']}"
    execute(
        f"UPDATE workspaces SET name = {sql_literal(archived_name)} "
        f"WHERE id = {sql_id(workspace_id)}"
    )
    return {"ok": True, "id": workspace_id}


def _parse_dataset_ids(raw: any) -> list[str]:
    """Parse postgres text[], uuid[], bigint[] or list into clean list of string IDs."""
    if isinstance(raw, str):
        clean_s = raw.strip("{}").strip()
        if not clean_s:
            return []
        return [x.strip().strip('"') for x in clean_s.split(",") if x.strip()]
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return []


def list_threads(workspace_id: int | str) -> list[dict]:
    """List active conversation threads for a workspace from the threads table."""
    sql = (
        "SELECT t.id, t.title, t.created_at::text AS created_at, "
        "t.selected_dataset_ids, "
        "count(r.id) AS turn_count "
        "FROM threads t "
        "LEFT JOIN runs r ON r.workspace_id = t.workspace_id "
        "                AND coalesce(r.checker_result->>'thread_id', 'default') = t.id "
        "                AND (r.checker_result->>'deleted') IS NULL "
        "                AND NOT (r.question = 'Schema Analysis') "
        f"WHERE t.workspace_id = {sql_id(workspace_id)} "
        "GROUP BY t.id, t.workspace_id, t.title, t.created_at, t.selected_dataset_ids "
        "ORDER BY t.created_at DESC"
    )
    rows = execute(sql)
    threads = []
    for row in rows:
        title = (row.get("title") or "New Conversation").strip()
        if len(title) > 40:
            title = title[:37] + "..."
        threads.append(
            {
                "id": row["id"],
                "title": title,
                "created_at": row.get("created_at") or "",
                "turn_count": int(row.get("turn_count") or 0),
                "selected_dataset_ids": _parse_dataset_ids(row.get("selected_dataset_ids")),
            }
        )
    return threads


def get_or_create_thread(workspace_id: int | str, thread_id: str) -> dict:
    """Get thread record or create it server-side on first interaction with all current workspace datasets."""
    clean_thread = (thread_id or "default").strip()
    found = execute(
        "SELECT id, workspace_id, title, selected_dataset_ids "
        f"FROM threads WHERE workspace_id = {sql_id(workspace_id)} AND id = {sql_literal(clean_thread)}"
    )
    if found:
        row = found[0]
        return {
            "id": row["id"],
            "workspace_id": str(row["workspace_id"]),
            "title": row["title"],
            "selected_dataset_ids": _parse_dataset_ids(row.get("selected_dataset_ids")),
        }

    # First interaction: initialize with all active datasets for this workspace
    ds_rows = execute(f"SELECT id FROM datasets WHERE workspace_id = {sql_id(workspace_id)} ORDER BY id")
    all_ds = [str(r["id"]) for r in ds_rows]
    arr_literal = f"ARRAY[{','.join(sql_literal(i) for i in all_ds)}]::text[]" if all_ds else "'{}'::text[]"
    inserted = execute(
        "INSERT INTO threads (id, workspace_id, title, selected_dataset_ids) "
        f"VALUES ({sql_literal(clean_thread)}, {sql_id(workspace_id)}, 'New Conversation', {arr_literal}) "
        "ON CONFLICT (workspace_id, id) DO NOTHING "
        "RETURNING id, workspace_id, title, selected_dataset_ids"
    )
    if inserted:
        return {
            "id": inserted[0]["id"],
            "workspace_id": str(inserted[0]["workspace_id"]),
            "title": inserted[0]["title"],
            "selected_dataset_ids": all_ds,
        }
    return get_or_create_thread(workspace_id, clean_thread)


def update_thread_datasets(workspace_id: int | str, thread_id: str, dataset_ids: list[str | int]) -> dict:
    """Update selected dataset IDs for a specific chat thread, strictly validating workspace ownership."""
    clean_thread = (thread_id or "default").strip()
    # Verify thread belongs to this workspace
    get_or_create_thread(workspace_id, clean_thread)

    # Strictly validate dataset IDs belong to this workspace
    clean_ids: list[str] = []
    if dataset_ids:
        id_list = ",".join(sql_id(i) for i in dataset_ids)
        valid = execute(
            f"SELECT id FROM datasets WHERE workspace_id = {sql_id(workspace_id)} AND id IN ({id_list})"
        )
        valid_set = {str(r["id"]) for r in valid}
        clean_ids = [str(i) for i in dataset_ids if str(i) in valid_set]

    arr_literal = f"ARRAY[{','.join(sql_literal(i) for i in clean_ids)}]::text[]" if clean_ids else "'{}'::text[]"
    execute(
        f"UPDATE threads SET selected_dataset_ids = {arr_literal}, updated_at = now() "
        f"WHERE workspace_id = {sql_id(workspace_id)} AND id = {sql_literal(clean_thread)}"
    )
    return {"ok": True, "thread_id": clean_thread, "selected_dataset_ids": clean_ids}


def delete_thread(workspace_id: int | str, thread_id: str) -> dict:
    """Delete a conversation thread from threads table and flag runs."""
    clean_thread = (thread_id or "default").strip()
    execute(
        f"DELETE FROM threads WHERE workspace_id = {sql_id(workspace_id)} AND id = {sql_literal(clean_thread)}"
    )
    patch = json.dumps({"deleted": True})
    sql = (
        f"UPDATE runs SET checker_result = checker_result || {sql_literal(patch)}::jsonb "
        f"WHERE workspace_id = {sql_id(workspace_id)} "
        f"AND coalesce(checker_result->>'thread_id', 'default') = {sql_literal(clean_thread)} "
        "RETURNING id"
    )
    updated = execute(sql)
    return {"ok": True, "deleted_turns": len(updated)}


def list_workspace_datasets(workspace_id: int | str) -> list[dict]:
    """Retrieve all approved datasets for a workspace with row count, quarantine count, grain, and table label."""
    sql = (
        "SELECT d.id, d.upload_id, d.table_name, d.table_label, d.grain, d.row_count, d.created_at::text, "
        "coalesce((SELECT count(*) FROM quarantine q WHERE q.upload_id = d.upload_id), 0) AS quarantine_count "
        f"FROM datasets d WHERE d.workspace_id = {sql_id(workspace_id)} ORDER BY d.id"
    )
    rows = execute(sql)
    datasets = []
    for r in rows:
        clean_grain = (r.get("grain") or "").strip()
        clean_grain = re.sub(r"^[\s*#_-]*(?:grain|table grain|one row represents)[\s*#_:-]*", "", clean_grain, flags=re.I).strip()
        datasets.append({
            "id": r["id"],
            "upload_id": r.get("upload_id") if r.get("upload_id") else None,
            "table_name": r["table_name"],
            "table_label": r["table_label"],
            "grain": clean_grain,
            "row_count": int(r.get("row_count") or 0),
            "quarantine_count": int(r.get("quarantine_count") or 0),
            "created_at": r.get("created_at") or "",
        })
    return datasets


def rename_dataset(workspace_id: int | str, dataset_id: int | str, new_label: str) -> dict:
    """Rename a dataset's friendly table label."""
    clean_label = new_label.strip()
    found = execute(
        f"SELECT id FROM datasets WHERE id = {sql_id(dataset_id)} AND workspace_id = {sql_id(workspace_id)}"
    )
    if not found:
        raise HTTPException(status_code=404, detail="dataset not found in this workspace")
    execute(
        f"UPDATE datasets SET table_label = {sql_literal(clean_label)} "
        f"WHERE id = {sql_id(dataset_id)} AND workspace_id = {sql_id(workspace_id)}"
    )
    return {"ok": True, "dataset_id": dataset_id, "table_label": clean_label}


def remove_dataset(workspace_id: int | str, dataset_id: int | str) -> dict:
    """Remove a dataset in one atomic transaction: table, catalog rows, quarantine rows, and threads array_remove."""
    found = execute(
        f"SELECT id, table_name, upload_id FROM datasets WHERE id = {sql_id(dataset_id)} AND workspace_id = {sql_id(workspace_id)}"
    )
    if not found:
        raise HTTPException(status_code=404, detail="dataset not found in this workspace")
    ds = found[0]
    table_name = ds["table_name"]
    upload_id = ds["upload_id"]

    if upload_id:
        up = execute(f"SELECT status FROM uploads WHERE id = {sql_id(upload_id)}")
        if up and up[0]["status"] in ("received", "processing", "uploading", "profiling"):
            raise HTTPException(status_code=400, detail="Cannot remove dataset while upload is running")

    sql = f"""
    DROP TABLE IF EXISTS user_data.{table_name} CASCADE;
    DELETE FROM dataset_columns WHERE dataset_id = {sql_id(dataset_id)};
    DELETE FROM datasets WHERE id = {sql_id(dataset_id)};
    DELETE FROM quarantine WHERE upload_id = {sql_id(upload_id)};
    UPDATE threads 
    SET selected_dataset_ids = array_remove(selected_dataset_ids, {sql_literal(str(dataset_id))}),
        updated_at = now()
    WHERE workspace_id = {sql_id(workspace_id)};
    """
    execute(sql)
    return {"ok": True, "dataset_id": dataset_id, "table_name": table_name}


def get_mappings(upload_id: int | str) -> list[dict]:
    """Retrieve column mapping proposals and statuses for an upload."""
    saved = execute(
        "SELECT source_column, canonical_column, confidence, method, confirmed_by_user "
        f"FROM column_mapping WHERE upload_id = {sql_id(upload_id)} ORDER BY id"
    )
    mappings = []
    for item in saved:
        confirmed = str(item["confirmed_by_user"]).lower() in {"t", "true"}
        canonical = item["canonical_column"] or None
        role = canonical if canonical else "attribute"
        mappings.append(
            {
                "source": item["source_column"],
                "canonical": canonical,
                "confidence": float(item["confidence"] or 0),
                "method": item["method"],
                "needs_confirmation": item["method"] == "llm" and not confirmed,
                "confirmed_by_user": confirmed,
                "detected_role": role,
            }
        )
    return mappings


def get_health(workspace_id: int | str) -> dict:
    """Compute table health stats and count quarantined rows for a workspace."""
    try:
        rows = run_sql(HEALTH_SQL, workspace_id)
    except SqlRejected:
        rows = []
    health = rows[0] if rows else {}
    
    # If legacy sales_clean has no rows, compute total rows from custom datasets
    health_rows = health.get("rows") or "0"
    if health_rows == "0":
        try:
            ds_count = execute(f"SELECT coalesce(sum(row_count), 0) AS total FROM datasets WHERE workspace_id = {sql_id(workspace_id)}")
            if ds_count and int(ds_count[0].get("total", 0)) > 0:
                health_rows = str(ds_count[0]["total"])
        except Exception:
            pass

    counted = execute(
        "SELECT count(*) AS quarantine FROM quarantine q "
        "JOIN uploads u ON u.id = q.upload_id "
        f"WHERE u.workspace_id = {sql_id(workspace_id)}"
    )
    return {
        "rows": health_rows,
        "first_order": health.get("first_order") or "",
        "last_order": health.get("last_order") or "",
        "revenue": health.get("revenue") or "",
        "quarantine": counted[0]["quarantine"] if counted else "0",
    }


def get_turns(workspace_id: int | str, thread_id: str | None = None) -> list[dict]:
    """Fetch conversation turns for a workspace, optionally filtered by thread_id, excluding deleted and ghost architect runs."""
    where_clauses = [
        f"workspace_id = {sql_id(workspace_id)}",
        "(checker_result->>'deleted') IS NULL",
        "NOT (question = 'Schema Analysis')",
        "NOT (answer LIKE '{\"table_label\"%')",
        "NOT (answer LIKE '{\"table_name\"%')",
    ]
    if thread_id:
        clean_thread = thread_id.strip()
        where_clauses.append(f"coalesce(checker_result->>'thread_id', 'default') = {sql_literal(clean_thread)}")
    where_sql = " AND ".join(where_clauses)

    rows = execute(
        f"SELECT id, question, answer, sql_list, checker_result FROM runs "
        f"WHERE {where_sql} ORDER BY id DESC LIMIT 50"
    )
    turns = []
    for row in reversed(rows):
        q = (row.get("question") or "").strip()
        ans = (row.get("answer") or "").strip()
        if q == "Schema Analysis" or ans.startswith('{"table_label"') or ans.startswith('{"table_name"'):
            continue  # Defensive skip against any stray legacy payload
        raw = row.get("checker_result") or "{}"
        try:
            check = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            check = {}
        turns.append(
            {
                "run_id": row["id"],
                "question": q,
                "answer": ans,
                "sql": row.get("sql_list") or None,
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
    """Assemble complete data room view: uploads, health, quarantine, mappings, threads, turns, and datasets."""
    room = get_workspace_meta(workspace_id)
    if room is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    uploads = execute(
        "SELECT id, original_name, status FROM uploads "
        f"WHERE workspace_id = {sql_id(workspace_id)} ORDER BY id DESC"
    )
    latest = uploads[0]["id"] if uploads else None
    capabilities = {}
    if latest:
        cap_rows = execute(
            f"SELECT capabilities FROM uploads WHERE id = {sql_id(latest)}"
        )
        if cap_rows and cap_rows[0].get("capabilities"):
            raw_cap = cap_rows[0]["capabilities"]
            try:
                capabilities = json.loads(raw_cap) if isinstance(raw_cap, str) else raw_cap
            except Exception:
                capabilities = {}
    quarantine = execute(
        "SELECT q.row_number, q.reason FROM quarantine q "
        "JOIN uploads u ON u.id = q.upload_id "
        f"WHERE u.workspace_id = {sql_id(workspace_id)} "
        "ORDER BY q.id DESC LIMIT 20"
    )
    return {
        "id": room["id"],
        "name": room["name"],
        "uploads": uploads,
        "capabilities": capabilities,
        "datasets": list_workspace_datasets(workspace_id),
        "health": get_health(workspace_id),
        "quarantine": quarantine,
        "mappings": get_mappings(latest) if latest else [],
        "threads": list_threads(workspace_id),
        "turns": get_turns(workspace_id, thread_id),
    }
