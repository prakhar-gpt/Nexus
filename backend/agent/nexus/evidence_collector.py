"""Evidence collection and structured query recording for provenance."""

from __future__ import annotations

from decimal import Decimal
from sqlalchemy import select

from agent.nexus.extraction import normalize_raw_number
from agent.nexus.provenance import EvidenceRecord, derive_column_kind


def lookup_table_metadata(
    workspace_id: str | int,
    table_name: str | None,
) -> tuple[str | None, str | None, dict[str, str]]:
    """Return (dataset_id, table_label, {column_name: role}) for relation name."""
    if not table_name:
        return None, None, {}
    if table_name.lower() == "sales_clean":
        return "sales_clean", "sales_clean", {}

    try:
        from db.models import Dataset, DatasetColumn
        from db.session import session_scope
        from utils import to_uuid

        ws_uuid = to_uuid(workspace_id)
        with session_scope() as session:
            ds = session.execute(
                select(Dataset).where(
                    Dataset.workspace_id == ws_uuid,
                    Dataset.table_name == table_name,
                )
            ).scalar_one_or_none()
            if ds:
                cols = session.execute(
                    select(DatasetColumn).where(DatasetColumn.dataset_id == ds.id)
                ).scalars().all()
                roles = {c.column_name: c.role for c in cols}
                return str(ds.id), ds.table_label, roles
    except Exception:
        pass
    return None, table_name, {}


def collect_sql_evidence(
    workspace_id: str | int,
    query_id: int,
    sql: str,
    found: list[dict],
    truncated: bool = False,
    table_name: str | None = None,
) -> tuple[dict, list[EvidenceRecord]]:
    """Build structured query dict and typed EvidenceRecords for one SQL execution."""
    dataset_id, table_label, roles = lookup_table_metadata(workspace_id, table_name)
    columns = list(found[0].keys()) if found else []
    query_info = {
        "query_id": query_id,
        "sql": sql,
        "dataset_id": dataset_id,
        "table_label": table_label or (table_name or f"Query {query_id}"),
        "columns": columns,
        "row_count": len(found),
        "truncated": bool(truncated),
        "preview_rows": found[:25],
    }

    records: list[EvidenceRecord] = []
    for r_idx, row in enumerate(found):
        for col_name, val in row.items():
            if val is None or str(val).strip() == "":
                continue
            norm = normalize_raw_number(str(val))
            if norm is not None:
                kind = derive_column_kind(str(col_name), catalog_role=roles.get(str(col_name)))
                records.append(
                    EvidenceRecord(
                        query_id=query_id,
                        dataset_id=dataset_id,
                        table_label=table_label,
                        column=str(col_name),
                        kind=kind,
                        row_index=r_idx,
                        value=norm,
                        raw_string=str(val).strip(),
                    )
                )

    if found:
        records.append(
            EvidenceRecord(
                query_id=query_id,
                dataset_id=dataset_id,
                table_label=table_label,
                column="row_count",
                kind="count",
                row_index=0,
                value=Decimal(len(found)),
                raw_string=str(len(found)),
            )
        )

    return query_info, records


def collect_python_evidence(
    query_id: int | str,
    code: str,
    inputs: list,
    py_results: dict,
) -> tuple[dict, list[EvidenceRecord]]:
    """Build structured query dict and typed EvidenceRecords for Python calculation."""
    query_info = {
        "query_id": query_id,
        "type": "python",
        "code": code,
        "inputs": inputs,
        "result": py_results,
    }
    records: list[EvidenceRecord] = []
    for label, val in py_results.items():
        if val is None or str(val).strip() == "":
            continue
        norm = normalize_raw_number(str(val))
        if norm is not None:
            records.append(
                EvidenceRecord(
                    query_id=query_id,
                    dataset_id=None,
                    table_label="python",
                    column=str(label),
                    kind="python",
                    row_index=0,
                    value=norm,
                    raw_string=str(val).strip(),
                )
            )
    return query_info, records

