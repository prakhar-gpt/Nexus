"""Workspace data access, thread management, and health check services."""

from __future__ import annotations

import json
from fastapi import HTTPException

from agent.tools import SqlRejected, run_sql
from ingest.store import execute, sql_literal

HEALTH_SQL = (
    "SELECT count(*) AS rows, min(order_date)::text AS first_order, "
    "max(order_date)::text AS last_order, "
    "coalesce(round(sum(revenue), 2)::text, '') AS revenue "
    "FROM sales_clean"
)


def get_workspace_meta(workspace_id: int) -> dict | None:
    """Return basic workspace record or None if absent or archived."""
    rows = execute(
        "SELECT id, name FROM workspaces "
        f"WHERE id = {int(workspace_id)} AND NOT (name LIKE '[archived]%')"
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


def create_workspace(name: str) -> dict:
    """Create a new workspace."""
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="name is required")
    rows = execute(
        "INSERT INTO workspaces (name) "
        f"VALUES ({sql_literal(clean_name)}) RETURNING id"
    )
    return {"id": int(rows[0]["id"]), "name": clean_name}


def delete_workspace(workspace_id: int) -> dict:
    """Soft-delete / archive a workspace."""
    ws = get_workspace_meta(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")
    archived_name = f"[archived] {ws['name']}"
    execute(
        f"UPDATE workspaces SET name = {sql_literal(archived_name)} "
        f"WHERE id = {int(workspace_id)}"
    )
    return {"ok": True, "id": workspace_id}


def list_threads(workspace_id: int) -> list[dict]:
    """List active (non-deleted) conversation threads for a workspace derived from runs."""
    sql = (
        "SELECT coalesce(checker_result->>'thread_id', 'default') AS id, "
        "min(created_at)::text AS created_at, "
        "min(question) AS title, "
        "count(*) AS turn_count "
        f"FROM runs WHERE workspace_id = {int(workspace_id)} "
        "AND (checker_result->>'deleted') IS NULL "
        "GROUP BY coalesce(checker_result->>'thread_id', 'default') "
        "ORDER BY min(created_at) DESC"
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
            }
        )
    return threads


def delete_thread(workspace_id: int, thread_id: str) -> dict:
    """Soft-delete a conversation thread by flagging runs in its json audit record."""
    clean_thread = (thread_id or "default").strip()
    patch = json.dumps({"deleted": True})
    sql = (
        f"UPDATE runs SET checker_result = checker_result || {sql_literal(patch)}::jsonb "
        f"WHERE workspace_id = {int(workspace_id)} "
        f"AND coalesce(checker_result->>'thread_id', 'default') = {sql_literal(clean_thread)} "
        "RETURNING id"
    )
    updated = execute(sql)
    return {"ok": True, "deleted_turns": len(updated)}


def get_mappings(upload_id: int) -> list[dict]:
    """Retrieve column mapping proposals and statuses for an upload."""
    saved = execute(
        "SELECT source_column, canonical_column, confidence, method, confirmed_by_user "
        f"FROM column_mapping WHERE upload_id = {int(upload_id)} ORDER BY id"
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


def get_health(workspace_id: int) -> dict:
    """Compute table health stats and count quarantined rows for a workspace."""
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


def get_turns(workspace_id: int, thread_id: str | None = None) -> list[dict]:
    """Fetch conversation turns for a workspace, optionally filtered by thread_id, excluding deleted."""
    where_clauses = [
        f"workspace_id = {int(workspace_id)}",
        "(checker_result->>'deleted') IS NULL",
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
                "steps": check.get("steps") or [],
                "tools_used": check.get("tools_used") or [],
                "python_results": check.get("python_results") or [],
                "thread_id": check.get("thread_id") or "default",
            }
        )
    return turns


def get_workspace_detail(workspace_id: int, thread_id: str | None = None) -> dict:
    """Assemble complete data room view: uploads, health, quarantine, mappings, threads, turns."""
    room = get_workspace_meta(workspace_id)
    if room is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    uploads = execute(
        "SELECT id, original_name, status FROM uploads "
        f"WHERE workspace_id = {int(workspace_id)} ORDER BY id DESC"
    )
    latest = uploads[0]["id"] if uploads else None
    capabilities = {}
    if latest:
        cap_rows = execute(
            f"SELECT capabilities FROM uploads WHERE id = {int(latest)}"
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
        f"WHERE u.workspace_id = {int(workspace_id)} "
        "ORDER BY q.id DESC LIMIT 20"
    )
    return {
        "id": int(room["id"]),
        "name": room["name"],
        "uploads": uploads,
        "capabilities": capabilities,
        "health": get_health(workspace_id),
        "quarantine": quarantine,
        "mappings": get_mappings(int(latest)) if latest else [],
        "threads": list_threads(workspace_id),
        "turns": get_turns(workspace_id, thread_id),
    }
