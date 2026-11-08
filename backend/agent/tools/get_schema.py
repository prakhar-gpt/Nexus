"""get_schema tool: inspects canonical columns, capabilities, and dynamic JSONB attributes."""

from __future__ import annotations

from langchain_core.tools import tool

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


@tool
def get_schema() -> str:
    """See which canonical sales columns, capabilities, and dynamic attributes have values in this data room."""


def execute_schema(workspace_id: int) -> str:
    """Inspect canonical columns, capabilities, and dynamic attributes for a workspace."""
    from agent.tools.run_sql import SqlRejected, execute_sql

    try:
        rows = execute_sql(SCHEMA_SQL, workspace_id)
    except SqlRejected as exc:
        return f"rejected: {exc}"
    if not rows:
        return "0 rows"

    canonical_summary = ", ".join(f"{key}={value}" for key, value in rows[0].items())
    lines = [f"Canonical columns: {canonical_summary}"]

    try:
        from ingest.store import execute as store_execute
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
