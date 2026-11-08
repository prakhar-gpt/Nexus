"""Workspace data access and health check services."""

from __future__ import annotations

import json
from fastapi import HTTPException

from packages.agent.run_sql import SqlRejected, run_sql
from packages.ingest.store import execute, sql_literal

HEALTH_SQL = (
    "SELECT count(*) AS rows, min(order_date)::text AS first_order, "
    "max(order_date)::text AS last_order, "
    "coalesce(round(sum(revenue), 2)::text, '') AS revenue "
    "FROM sales_clean"
)


def get_workspace_meta(workspace_id: int) -> dict | None:
    """Return basic workspace record or None if absent."""
    rows = execute(
        "SELECT id, name FROM workspaces "
        f"WHERE id = {int(workspace_id)}"
    )
    return rows[0] if rows else None


def list_workspaces() -> list[dict]:
    """List all available workspaces."""
    return execute("SELECT id, name, created_at FROM workspaces ORDER BY id")


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


def get_mappings(upload_id: int) -> list[dict]:
    """Retrieve column mapping proposals and statuses for an upload."""
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


def get_turns(workspace_id: int) -> list[dict]:
    """Fetch the latest 20 conversation turns for a workspace."""
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


def get_workspace_detail(workspace_id: int) -> dict:
    """Assemble complete data room view: uploads, health, quarantine, mappings, turns."""
    room = get_workspace_meta(workspace_id)
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
        "health": get_health(workspace_id),
        "quarantine": quarantine,
        "mappings": get_mappings(int(latest)) if latest else [],
        "turns": get_turns(workspace_id),
    }

