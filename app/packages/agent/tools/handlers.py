"""Execution handlers implementing each agent tool's runtime behavior."""

from __future__ import annotations

import json
import re
from pathlib import Path

from packages.agent.run_sql import run_sql as execute_sql
from packages.agent.sandbox import execute_sandboxed
from packages.agent.sql_guard import SqlRejected

SCHEMA_SQL = (
    "SELECT count(*) AS rows, "
    "count(order_date) AS order_date, "
    "count(customer_id) AS customer_id, "
    "count(product_id) AS product_id, "
    "count(segment) AS segment, "
    "count(region) AS region, "
    "count(category) AS category, "
    "count(sub_category) AS sub_category, "
    "count(revenue) AS revenue, "
    "count(quantity) AS quantity, "
    "count(unit_price) AS unit_price, "
    "count(discount_pct) AS discount_pct, "
    "count(cost) AS cost, "
    "count(profit) AS profit, "
    "count(channel) AS channel "
    "FROM sales_clean"
)

KB_ROOT = Path(__file__).resolve().parents[3] / "kb"


def parse_tool_args(call: dict) -> dict:
    raw = call.get("args") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def execute_schema(workspace_id: int) -> str:
    """Inspect canonical columns, capabilities, and dynamic attributes for a workspace."""
    try:
        rows = execute_sql(SCHEMA_SQL, workspace_id)
    except SqlRejected as exc:
        return f"rejected: {exc}"
    if not rows:
        return "0 rows"

    canonical_summary = ", ".join(f"{key}={value}" for key, value in rows[0].items())
    lines = [f"Canonical columns: {canonical_summary}"]

    from packages.ingest.store import execute as store_execute
    try:
        upload_rows = store_execute(
            f"SELECT id, capabilities FROM uploads WHERE workspace_id = {int(workspace_id)} ORDER BY id DESC LIMIT 1"
        )
    except Exception:
        upload_rows = []

    if upload_rows:
        upload_id = upload_rows[0]["id"]
        caps = upload_rows[0].get("capabilities")
        if caps:
            lines.append(f"Capabilities: {caps}")

        try:
            attr_rows = store_execute(
                f"SELECT key, inferred_type, sample_values FROM upload_attribute_schema WHERE upload_id = {int(upload_id)} ORDER BY key"
            )
        except Exception:
            attr_rows = []

        if attr_rows:
            lines.append("Attributes (stored in sales_clean.attributes JSONB):")
            for ar in attr_rows:
                k = ar["key"]
                t = ar["inferred_type"]
                samples = ar.get("sample_values") or "[]"
                if t == "numeric":
                    sql_expr = f"(attributes->>'{k}')::numeric"
                elif t == "date":
                    sql_expr = f"(attributes->>'{k}')::date"
                else:
                    sql_expr = f"(attributes->>'{k}')"
                lines.append(f"  - {k} ({t}): exact SQL expression `{sql_expr}`, samples={samples}")

    return "\n".join(lines)


def execute_query(sql: str, workspace_id: int) -> tuple[str, list[dict], str | None]:
    """Execute a read-only query under the reader role with row-level security."""
    text = str(sql or "").strip()
    if not text:
        return "rejected: sql is empty", [], None
    try:
        rows = execute_sql(text, workspace_id)
    except SqlRejected as exc:
        return f"rejected: {exc}", [], None
    if not rows:
        return "0 rows", [], text
    header = list(rows[0].keys())
    lines = [", ".join(header)]

    # Token optimization: truncate prompt row dump if query returns many rows
    max_preview = 25
    for row in rows[:max_preview]:
        lines.append(", ".join("" if row.get(col) is None else str(row.get(col)) for col in header))
    if len(rows) > max_preview:
        lines.append(f"... ({len(rows) - max_preview} more rows available to run_python)")

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


def execute_python(
    code: str,
    inputs: list[str] | None = None,
    rows: list[dict] | None = None,
    sql_results: dict[str, list[dict]] | None = None,
) -> tuple[str, dict]:
    """Execute sandboxed Python with multiple DataFrame support and token safety.

    Parameters
    ----------
    code:
        Python source that assigns a dict named ``result`` of {label: number}.
    inputs:
        List of SQL result aliases requested by the model (e.g. ['sql_1', 'sql_2']).
    rows:
        All accumulated SQL result rows from the current turn.
    sql_results:
        Dictionary mapping query IDs and aliases ('sql_1', 'sql_2') to row lists.
    """
    dataframes: dict[str, list[dict]] = {}
    inputs = list(inputs or [])
    sql_results = sql_results or {}
    rows = rows or []

    # Map requested inputs to DataFrames
    for inp in inputs:
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", str(inp).strip())
        if inp in sql_results and sql_results[inp]:
            dataframes[clean_name] = sql_results[inp]
        elif clean_name in sql_results and sql_results[clean_name]:
            dataframes[clean_name] = sql_results[clean_name]

    # If specific inputs were not resolved but rows are available, map 'data'
    if not dataframes and rows:
        dataframes["data"] = rows
    elif rows and "data" not in dataframes:
        dataframes["data"] = rows

    # Also map all available sql_results as fallback aliases (e.g. sql_1, sql_2)
    for k, v in sql_results.items():
        clean_k = re.sub(r"[^a-zA-Z0-9_]", "_", k)
        if clean_k not in dataframes and v:
            dataframes[clean_k] = v

    # If no data at all is available, provide a clear actionable error
    total_rows = sum(len(v) for v in dataframes.values())
    if total_rows == 0:
        return (
            "rejected: No SQL query data is available in this turn yet. "
            "You must first run run_sql to retrieve the required data before calling run_python.",
            {},
        )

    result = execute_sandboxed(code, dataframes)

    if not result["ok"]:
        return f"rejected: {result['error']}", {}

    parts = ", ".join(f"{k}={v}" for k, v in result["results"].items())
    summary = f"result: {parts}" if parts else "result: (empty)"
    return summary, result["results"]
