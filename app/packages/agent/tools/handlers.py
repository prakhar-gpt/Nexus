"""Tool handlers that execute database queries, schema inspections, and KB lookups."""

from __future__ import annotations

import json
from pathlib import Path

from packages.agent.run_sql import SqlRejected
from packages.agent.run_sql import run_sql as execute_sql
from packages.agent.sql_guard import SqlRejected as GuardRejected

KB_ROOT = Path(__file__).resolve().parents[3] / "kb"

SCHEMA_SQL = (
    "SELECT count(*) AS rows, count(order_date) AS order_date, "
    "count(customer_id) AS customer_id, count(product_id) AS product_id, "
    "count(segment) AS segment, count(region) AS region, "
    "count(category) AS category, count(sub_category) AS sub_category, "
    "count(revenue) AS revenue, count(quantity) AS quantity, "
    "count(unit_price) AS unit_price, count(discount_pct) AS discount_pct, "
    "count(cost) AS cost, count(profit) AS profit, count(channel) AS channel "
    "FROM sales_clean"
)


def parse_tool_args(call: dict) -> dict:
    """Safely parse tool call arguments into a dictionary."""
    raw = call.get("args") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def execute_schema(workspace_id: int) -> str:
    """Inspect columns and populated counts for a workspace."""
    try:
        rows = execute_sql(SCHEMA_SQL, workspace_id)
    except (SqlRejected, GuardRejected) as exc:
        return f"rejected: {exc}"
    if not rows:
        return "0 rows"
    return ", ".join(f"{key}={value}" for key, value in rows[0].items())


def execute_query(sql: str, workspace_id: int) -> tuple[str, list[dict], str | None]:
    """Execute a read-only query under the reader role with row-level security."""
    text = str(sql or "").strip()
    if not text:
        return "rejected: sql is empty", [], None
    try:
        rows = execute_sql(text, workspace_id)
    except (SqlRejected, GuardRejected) as exc:
        return f"rejected: {exc}", [], None
    if not rows:
        return "0 rows", [], text
    header = list(rows[0].keys())
    lines = [", ".join(header)]
    for row in rows:
        lines.append(", ".join("" if row.get(col) is None else str(row.get(col)) for col in header))
    return "\n".join(lines), rows, text


def execute_kb(path: str) -> str:
    """Safely read a knowledge base markdown file within app/kb/."""
    root = KB_ROOT.resolve()
    name = str(path or "").replace("\\", "/").strip().lstrip("/")
    if not name or ".." in name.split("/"):
        return "rejected: path is outside the knowledge base"
    candidate = (root / name).resolve()
    if candidate != root and root not in candidate.parents:
        return "rejected: path is outside the knowledge base"
    if not candidate.is_file():
        return "rejected: file not found"
    return candidate.read_text(encoding="utf-8")[:6000]
