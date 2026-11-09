"""Provenance inspection, stored call records, and AST row rewrite service."""

from __future__ import annotations

import csv
import io
import re
from typing import Any
from fastapi import HTTPException, Response
import sqlglot
from sqlglot import exp

from agent.nexus.tools.run_sql import execute_sql, guard_sql
from db.models import Dataset, Run
from db.session import session_scope
from ingest.schema_validation import SYSTEM_RESERVED_COLUMNS
from utils import make_inert, to_uuid

# Columns we add when a file is loaded. They are not part of the upload.
INTERNAL_ROW_COLUMNS = SYSTEM_RESERVED_COLUMNS | {"source_row"}


def get_source_record(
    run: Run,
    query_id: int | str,
    claim_index: int | None = None,
) -> dict[str, Any]:
    """Retrieve stored call record for a given run and query_id. Executes no queries."""
    cr = run.checker_result or {}
    queries = cr.get("queries") or []
    target_qid = str(query_id).strip()

    q_record: dict[str, Any] | None = None
    for q in queries:
        if str(q.get("query_id")).strip() == target_qid:
            q_record = q
            break

    if not q_record:
        # Fallback: if query_id is 1 and sql is stored on run, synthesize record
        if target_qid in ("1", "sql") and (run.sql_list or cr.get("sql")):
            stored_sql = run.sql_list or cr.get("sql")
            q_record = {
                "query_id": 1,
                "tool": "sql",
                "type": "sql",
                "sql": stored_sql,
                "dataset_id": None,
                "table_label": "From your data",
                "columns": list(cr.get("rows", [{}])[0].keys()) if cr.get("rows") else [],
                "row_count": len(cr.get("rows", [])),
                "truncated": False,
                "preview_rows": cr.get("rows", []),
            }
        else:
            raise HTTPException(status_code=404, detail="Query record not found")

    tool = q_record.get("tool") or q_record.get("type") or "sql"
    is_python = str(tool).lower() == "python"

    # Claim context if claim_index provided
    claim_item = None
    matched_row = None
    prov_list = cr.get("provenance") or []
    if claim_index is not None and 0 <= claim_index < len(prov_list):
        claim_item = prov_list[claim_index]
        r_idx = claim_item.get("row_index")
        p_rows = q_record.get("preview_rows") or []
        if r_idx is not None and 0 <= r_idx < len(p_rows):
            matched_row = p_rows[r_idx]

    if is_python:
        derived_from = q_record.get("derived_from") or []
        inputs = q_record.get("inputs") or []

        upstream_qids = set(str(d) for d in derived_from)
        for inp in inputs:
            if inp.get("query_id") is not None:
                upstream_qids.add(str(inp["query_id"]))

        upstream_queries = []
        for q in queries:
            qid_str = str(q.get("query_id")).strip()
            if qid_str in upstream_qids:
                ds_id = q.get("dataset_id")
                lbl = q.get("table_label") or "Your data"
                if ds_id and ds_id != "sales_clean":
                    try:
                        with session_scope() as session:
                            ds = session.get(Dataset, to_uuid(ds_id))
                            if ds and ds.workspace_id == run.workspace_id:
                                lbl = ds.table_label or lbl
                    except Exception:
                        pass
                upstream_queries.append({
                    "query_id": qid_str,
                    "tool": q.get("tool") or "sql",
                    "sql": q.get("sql") or "",
                    "dataset_id": ds_id,
                    "dataset_label": lbl,
                    "columns": q.get("columns") or [],
                    "rows": q.get("preview_rows") or [],
                    "row_count": q.get("row_count", len(q.get("preview_rows") or [])),
                    "truncated": bool(q.get("truncated", False)),
                })

        return {
            "run_id": str(run.id),
            "query_id": target_qid,
            "origin_type": "python",
            "origin_label": "Calculated by Python",
            "code": q_record.get("code") or "",
            "inputs": inputs,
            "result": q_record.get("result") or {},
            "derived_from": derived_from,
            "upstream_queries": upstream_queries,
            "claim": claim_item,
        }

    # SQL Origin
    dataset_id = q_record.get("dataset_id")
    stored_label = q_record.get("table_label") or "Your data"
    dataset_status = "active"
    dataset_removed = False

    if dataset_id and dataset_id != "sales_clean":
        try:
            with session_scope() as session:
                ds = session.get(Dataset, to_uuid(dataset_id))
                if not ds or ds.workspace_id != run.workspace_id:
                    dataset_status = "removed"
                    dataset_removed = True
                elif not stored_label or stored_label == "Your data":
                    stored_label = ds.table_label
        except Exception:
            dataset_status = "removed"
            dataset_removed = True

    return {
        "run_id": str(run.id),
        "query_id": target_qid,
        "origin_type": "data",
        "origin_label": "From your data",
        "sql": q_record.get("sql") or "",
        "dataset_id": dataset_id,
        "dataset_label": stored_label,
        "dataset_status": dataset_status,
        "dataset_removed": dataset_removed,
        "columns": q_record.get("columns") or [],
        "rows": q_record.get("preview_rows") or [],
        "matched_row": matched_row,
        "row_count": q_record.get("row_count", len(q_record.get("preview_rows") or [])),
        "truncated": bool(q_record.get("truncated", False)),
        "claim": claim_item,
    }


def is_sql_rewritable_for_rows(sql: str) -> tuple[bool, str | None]:
    """Check whitelist for single-table aggregate queries rewritable into raw rows."""
    if not sql or not sql.strip():
        return False, "SQL is empty"

    try:
        parsed = sqlglot.parse(sql, read="postgres")
    except Exception as exc:
        return False, f"parse error: {exc}"

    if not parsed or len(parsed) != 1 or parsed[0] is None:
        return False, "only one statement allowed"

    tree = parsed[0]
    if not isinstance(tree, exp.Select):
        return False, "only SELECT statements are supported"

    # Whitelist rejections: CTE, window, subquery, HAVING, DISTINCT aggregate, join, set ops
    if tree.args.get("with"):
        return False, "CTE queries cannot be expanded"
    if tree.args.get("joins"):
        return False, "Join queries cannot be expanded"
    if list(tree.find_all(exp.Subquery)):
        return False, "Subqueries cannot be expanded"
    if list(tree.find_all(exp.Window)):
        return False, "Window functions cannot be expanded"
    if tree.args.get("having"):
        return False, "HAVING queries cannot be expanded"
    if list(tree.find_all((exp.Union, exp.Intersect, exp.Except))):
        return False, "Set operations cannot be expanded"

    if list(tree.find_all(exp.Distinct)):
        return False, "DISTINCT queries cannot be expanded"

    # Must reference exactly one table
    tables = list(tree.find_all(exp.Table))
    if len(tables) != 1:
        return False, "Must reference exactly one table"

    return True, None


def rewrite_sql_for_rows(sql: str, matched_row: dict | None = None) -> tuple[str, str | None]:
    """Rewrite a whitelisted aggregate SQL query to retrieve raw underlying rows, filtering by matched dimension if available."""
    allowed, reason = is_sql_rewritable_for_rows(sql)
    if not allowed:
        raise ValueError(f"not_rewritable: {reason}")

    tree = sqlglot.parse(sql, read="postgres")[0]
    table = tree.find(exp.Table)
    table_name = table.name if table else ""

    where_predicates: list[str] = []

    # Retain existing WHERE clause
    where_clause = tree.args.get("where")
    if where_clause:
        where_predicates.append(where_clause.this.sql(dialect="postgres"))

    matched_entity_desc = None
    group = tree.args.get("group")
    if group and matched_row:
        filter_parts = []
        for group_expr in group.expressions:
            col_name = group_expr.name if isinstance(group_expr, exp.Column) else str(group_expr)
            if col_name in matched_row and matched_row[col_name] is not None:
                val = str(matched_row[col_name]).replace("'", "''")
                where_predicates.append(f"{col_name} = '{val}'")
                filter_parts.append(f"{col_name} = '{val}'")
        if filter_parts:
            matched_entity_desc = ", ".join(filter_parts)

    where_sql = f"WHERE {' AND '.join(where_predicates)}" if where_predicates else ""
    rewritten = f"SELECT * FROM {table_name} {where_sql}".strip()
    return rewritten, matched_entity_desc


def uploaded_data_slice(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the columns that came from the uploaded file."""
    return [
        {key: value for key, value in row.items() if key not in INTERNAL_ROW_COLUMNS}
        for row in rows
    ]


def get_rows_behind_query(
    run: Run,
    query_id: int | str,
    limit: int = 50,
    claim_index: int | None = None,
    row_index: int | None = None,
) -> dict[str, Any]:
    """Execute rewritten row query through standard read-only path under nexus_reader."""
    cr = run.checker_result or {}
    queries = cr.get("queries") or []
    target_qid = str(query_id).strip()

    q_record = next((q for q in queries if str(q.get("query_id")).strip() == target_qid), None)
    if not q_record and target_qid in ("1", "sql") and run.sql_list:
        q_record = {"sql": run.sql_list, "tool": "sql", "dataset_id": None}

    if not q_record or str(q_record.get("tool") or q_record.get("type")).lower() == "python":
        return {
            "rewritable": False,
            "reason": "not_rewritable",
            "message": "This query can't be expanded into rows. Showing its result instead.",
        }

    original_sql = q_record.get("sql") or ""
    allowed, reason = is_sql_rewritable_for_rows(original_sql)
    if not allowed:
        return {
            "rewritable": False,
            "reason": "not_rewritable",
            "message": "This query can't be expanded into rows. Showing its result instead.",
        }

    matched_row = None
    p_rows = q_record.get("preview_rows") or []
    if row_index is not None and 0 <= row_index < len(p_rows):
        matched_row = p_rows[row_index]
    elif claim_index is not None:
        prov_list = cr.get("provenance") or []
        if 0 <= claim_index < len(prov_list):
            c_item = prov_list[claim_index]
            r_idx = c_item.get("row_index")
            if r_idx is not None and 0 <= r_idx < len(p_rows):
                matched_row = p_rows[r_idx]

    rewritten, entity_filter = rewrite_sql_for_rows(original_sql, matched_row=matched_row)

    # Guard and execute rewritten query with exact same safety as run_sql
    guarded = guard_sql(rewritten, workspace_id=run.workspace_id)
    rows = uploaded_data_slice(
        execute_sql(f"{guarded} LIMIT {min(limit, 100)}", workspace_id=run.workspace_id)
    )
    total_count_res = execute_sql(f"SELECT count(*) as total_rows FROM ({guarded}) as subq", workspace_id=run.workspace_id)
    total_rows = int(total_count_res[0]["total_rows"]) if total_count_res else len(rows)

    return {
        "rewritable": True,
        "rows": rows[:50],
        "total_rows": total_rows,
        "entity_filter": entity_filter,
    }


def export_rows_behind_query_csv(
    run: Run,
    query_id: int | str,
    hard_row_cap: int = 5000,
    claim_index: int | None = None,
    row_index: int | None = None,
) -> Response:
    """Stream all raw rows behind an aggregate claim as a formula-neutralized CSV."""
    cr = run.checker_result or {}
    queries = cr.get("queries") or []
    target_qid = str(query_id).strip()

    q_record = next((q for q in queries if str(q.get("query_id")).strip() == target_qid), None)
    if not q_record and target_qid in ("1", "sql") and run.sql_list:
        q_record = {"sql": run.sql_list, "tool": "sql"}

    if not q_record or str(q_record.get("tool") or q_record.get("type")).lower() == "python":
        raise HTTPException(status_code=400, detail="Cannot export rows for non-SQL query")

    original_sql = q_record.get("sql") or ""
    allowed, reason = is_sql_rewritable_for_rows(original_sql)
    if not allowed:
        raise HTTPException(status_code=400, detail=f"Query is not rewritable into rows: {reason}")

    matched_row = None
    p_rows = q_record.get("preview_rows") or []
    if row_index is not None and 0 <= row_index < len(p_rows):
        matched_row = p_rows[row_index]
    elif claim_index is not None:
        prov_list = cr.get("provenance") or []
        if 0 <= claim_index < len(prov_list):
            c_item = prov_list[claim_index]
            r_idx = c_item.get("row_index")
            if r_idx is not None and 0 <= r_idx < len(p_rows):
                matched_row = p_rows[r_idx]

    rewritten, _ = rewrite_sql_for_rows(original_sql, matched_row=matched_row)
    guarded = guard_sql(rewritten, workspace_id=run.workspace_id)
    rows = uploaded_data_slice(
        execute_sql(f"{guarded} LIMIT {hard_row_cap}", workspace_id=run.workspace_id)
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    if rows:
        headers = list(rows[0].keys())
        writer.writerow(headers)
        for r in rows:
            writer.writerow([make_inert(str(r.get(h, ""))) for h in headers])
    else:
        writer.writerow(["result"])
        writer.writerow(["No matching rows"])

    filename_suffix = f"-q{query_id}"
    if matched_row:
        # Include first non-metric value in filename for clarity
        for k, v in matched_row.items():
            if v and not isinstance(v, (int, float)):
                clean_v = re.sub(r"[^a-zA-Z0-9_-]", "", str(v).strip())
                if clean_v:
                    filename_suffix += f"-{clean_v}"
                    break

    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=source-rows-run-{run.id}{filename_suffix}.csv"},
    )

