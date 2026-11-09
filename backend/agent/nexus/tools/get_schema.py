"""get_schema tool: dynamically inspects table schemas, column roles, types, and grains."""

from __future__ import annotations

from langchain_core.tools import tool
from sqlalchemy import select

from db.models import Dataset, DatasetColumn, Upload
from db.session import session_scope
from utils import to_uuid


@tool
def get_schema() -> str:
    """Inspect all available table schemas, column names, data types, analytical roles, and grains for this data room."""


def execute_schema(workspace_id: int | str, allowed_dataset_ids: list[str | int] | None = None) -> str:
    """Inspect registered dataset schemas, column catalogs, and grains dynamically."""
    lines: list[str] = []

    try:
        ws_uuid = to_uuid(workspace_id)
        with session_scope() as session:
            # Query custom datasets for this workspace
            stmt = select(Dataset).where(Dataset.workspace_id == ws_uuid)
            if allowed_dataset_ids is not None:
                if not allowed_dataset_ids:
                    datasets = []
                else:
                    allowed_uuids = [to_uuid(i) for i in allowed_dataset_ids]
                    stmt = stmt.where(Dataset.id.in_(allowed_uuids))
                    datasets = session.execute(stmt.order_by(Dataset.id.asc())).scalars().all()
            else:
                datasets = session.execute(stmt.order_by(Dataset.id.asc())).scalars().all()

            if datasets:
                lines.append("Approved Datasets (query directly without schema prefix):")
                for ds in datasets:
                    r_count = ds.row_count or 0
                    lines.append(f"- Table `{ds.table_name}`: {ds.table_label} ({r_count} rows)")
                    if ds.grain:
                        lines.append(f"  Grain: \"{ds.grain}\"")

                    col_objs = session.execute(
                        select(DatasetColumn)
                        .where(DatasetColumn.dataset_id == ds.id)
                        .order_by(DatasetColumn.id.asc())
                    ).scalars().all()

                    if col_objs:
                        lines.append("  Columns:")
                        for cr in col_objs:
                            cunit = f", unit={cr.unit}" if cr.unit else ""
                            cnr = f", null_rate={cr.null_rate}" if cr.null_rate is not None else ""
                            lines.append(
                                f"    * `{cr.column_name}` ({cr.type}, role={cr.role}{cunit}{cnr}): {cr.description or ''}"
                            )

            latest_upload = session.execute(
                select(Upload.capabilities)
                .where(Upload.workspace_id == ws_uuid)
                .order_by(Upload.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest_upload:
                lines.append(f"\nCapabilities: {latest_upload}")

    except Exception:
        pass

    # Fallback only when workspace has no custom datasets (e.g. standalone Superstore benchmark)
    if not lines or (not datasets and allowed_dataset_ids is None):
        try:
            from agent.nexus.tools.run_sql import execute_sql
            rows = execute_sql("SELECT count(*) AS rows FROM sales_clean", workspace_id)
            if rows and int(rows[0].get("rows") or 0) > 0:
                lines.insert(0, f"Benchmark Dataset: `sales_clean` ({rows[0]['rows']} rows)")
        except Exception:
            pass

    return "\n".join(lines) if lines else "0 datasets available in this workspace."
