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


def execute_schema(workspace_id: int | str, allowed_dataset_ids: list[str | int] | None = None) -> str:
    """Inspect canonical columns, capabilities, and dynamic attributes for a workspace."""
    from agent.nexus.tools.run_sql import SqlRejected, execute_sql

    try:
        rows = execute_sql(SCHEMA_SQL, workspace_id, allowed_dataset_ids=allowed_dataset_ids)
    except SqlRejected as exc:
        return f"rejected: {exc}"
    if not rows:
        return "0 rows"

    canonical_summary = ", ".join(f"{key}={value}" for key, value in rows[0].items())
    lines = [f"Canonical columns: {canonical_summary}"]

    try:
        from ingest.store import execute as store_execute, sql_id
        upload_rows = store_execute(
            f"SELECT id, capabilities FROM uploads WHERE workspace_id = {sql_id(workspace_id)} ORDER BY id DESC LIMIT 1"
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
                f"SELECT key, inferred_type, sample_values FROM upload_attribute_schema WHERE upload_id = {sql_id(upload_id)} ORDER BY key"
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

    # List all approved custom datasets allowed for this workspace / thread
    try:
        from ingest.store import execute as store_execute, sql_id
        sql = (
            f"SELECT id, table_name, table_label, grain, grain_key_columns, row_count "
            f"FROM datasets WHERE workspace_id = {sql_id(workspace_id)}"
        )
        if allowed_dataset_ids is not None:
            if not allowed_dataset_ids:
                dataset_rows = []
            else:
                id_list = ",".join(sql_id(i) for i in allowed_dataset_ids)
                dataset_rows = store_execute(sql + f" AND id IN ({id_list}) ORDER BY id")
        else:
            dataset_rows = store_execute(sql + " ORDER BY id")
    except Exception:
        dataset_rows = []

    if dataset_rows:
        lines.append("\nCustom Datasets (user_data schema, accessible directly without schema prefix):")
        for ds in dataset_rows:
            ds_id = ds["id"]
            t_name = ds["table_name"]
            t_label = ds["table_label"]
            grain = ds["grain"]
            r_count = ds.get("row_count", 0)
            lines.append(f"- Table `{t_name}`: {t_label} ({r_count} rows)")
            lines.append(f"  Grain: \"{grain}\"")

            try:
                col_rows = store_execute(
                    f"SELECT column_name, type, role, description, unit, null_rate "
                    f"FROM dataset_columns WHERE dataset_id = {sql_id(ds_id)} ORDER BY id"
                )
            except Exception:
                col_rows = []

            if col_rows:
                lines.append("  Columns:")
                for cr in col_rows:
                    cn = cr["column_name"]
                    ct = cr["type"]
                    crole = cr["role"]
                    cdesc = cr.get("description") or ""
                    cunit = f", unit={cr['unit']}" if cr.get("unit") else ""
                    cnr = f", null_rate={cr.get('null_rate', 0)}"
                    lines.append(f"    * `{cn}` ({ct}, role={crole}{cunit}{cnr}): {cdesc}")

    return "\n".join(lines)
