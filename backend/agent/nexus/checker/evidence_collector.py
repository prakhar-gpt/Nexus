"""Evidence collection, call records, and Python lineage for provenance."""

from __future__ import annotations

import ast
import re
from decimal import Decimal
from sqlalchemy import select

from agent.nexus.checker.extraction import normalize_raw_number
from agent.nexus.checker.matching import match_target_value
from agent.nexus.checker.provenance import EvidenceRecord, derive_column_kind


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


def _bound_cell(val: object) -> object:
    """Cap cell string length to 200 chars to strictly bound JSONB size."""
    if val is None:
        return None
    s = str(val)
    return s[:200] if len(s) > 200 else val


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

    bounded_rows = [
        {k: _bound_cell(v) for k, v in row.items()}
        for row in found[:25]
    ]

    query_info = {
        "query_id": query_id,
        "tool": "sql",
        "type": "sql",
        "sql": (sql or "")[:4000],
        "dataset_id": dataset_id,
        "table_label": table_label or (table_name or f"Query {query_id}"),
        "columns": columns,
        "row_count": len(found),
        "truncated": bool(truncated),
        "preview_rows": bounded_rows,
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


def _find_entity_in_row(row: dict, target_col: str, roles: dict[str, str] | None = None) -> str | None:
    """Find the dimension or identifier entity in a row based on catalog schema roles or text columns."""
    if not row:
        return None

    # First: use schema roles from the architect proposal if present
    if roles:
        for k, v in row.items():
            if k != target_col and v is not None and str(v).strip():
                role = roles.get(k)
                if role in ("dimension", "identifier"):
                    return str(v).strip()

    # Second: find any non-target string column (dimensions / group keys)
    for k, v in row.items():
        if k != target_col and v is not None and str(v).strip() and not isinstance(v, (int, float)):
            # Ensure it's not a numeric string
            raw_str = str(v).strip()
            if not re.match(r"^-?[\d,]+(\.\d+)?%?$", raw_str):
                return raw_str

    # Fallback to any non-target column with value
    for k, v in row.items():
        if k != target_col and v is not None and str(v).strip():
            return str(v).strip()

    return None


def extract_python_input_lineage(
    code: str,
    inputs: list,
    prior_evidence: list[EvidenceRecord] | None = None,
    sql_results: dict[str, list[dict]] | None = None,
    variables: dict[str, Any] | None = None,
) -> tuple[list[dict], list[int | str]]:
    """Extract numeric parameters/inputs from Python code, runtime variables, and inputs, linking each to SQL evidence."""
    prior = [r for r in (prior_evidence or []) if r.kind != "python"]
    candidates: list[tuple[str | None, Decimal, str]] = []

    # 1. Parse numeric inputs in args.get("inputs")
    for item in inputs or []:
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            norm = normalize_raw_number(str(item))
            if norm is not None:
                candidates.append((None, norm, str(item)))
        elif isinstance(item, str):
            norm = normalize_raw_number(item)
            if norm is not None:
                candidates.append((None, norm, item))

    # 2. Extract numeric literals from Python code AST
    if code:
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                # Variable assignments like west = 450000 or diff = -120
                if isinstance(node, ast.Assign):
                    var_name = None
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_name = target.id
                            break
                    val_node = node.value
                    sign = 1
                    if isinstance(val_node, ast.UnaryOp) and isinstance(val_node.op, ast.USub):
                        sign = -1
                        val_node = val_node.operand
                    if isinstance(val_node, ast.Constant) and isinstance(val_node.value, (int, float)) and not isinstance(val_node.value, bool):
                        num_val = val_node.value * sign
                        norm = normalize_raw_number(str(num_val))
                        if norm is not None:
                            candidates.append((var_name, norm, str(num_val)))
                # Skip bare constants inside expressions (round digits, iloc[0], * 100).
                # Those are formula mechanics. Named assignments above stay visible.
        except Exception:
            pass

    # 3. Extract evaluated runtime variables (e.g. best_val = data['val'].max())
    for var_name, var_val in (variables or {}).items():
        if isinstance(var_val, (int, float)) and not isinstance(var_val, bool):
            norm = normalize_raw_number(str(var_val))
            if norm is not None:
                candidates.append((var_name, norm, str(var_val)))

    # Deduplicate candidates by value and name
    seen = set()
    unique_candidates = []
    for name, dec_val, raw in candidates:
        key = (name, dec_val)
        if key not in seen:
            seen.add(key)
            unique_candidates.append((name, dec_val, raw))

    input_records: list[dict] = []
    derived_from_set: set[int | str] = set()

    def _query_sort_key(qid: int | str) -> int:
        try:
            return int(qid)
        except Exception:
            return 9999

    # Cache row lookup by query_id for entity identification
    sql_rows_by_qid: dict[int | str, list[dict]] = {}
    if sql_results:
        for k, rows_list in sql_results.items():
            qid_match = re.search(r"\d+", str(k))
            if qid_match:
                sql_rows_by_qid[int(qid_match.group(0))] = rows_list
                sql_rows_by_qid[str(qid_match.group(0))] = rows_list

    for name, dec_val, raw in unique_candidates:
        # Match candidate against SQL evidence using checker tolerance rules
        matches: list[EvidenceRecord] = [
            rec for rec in prior
            if match_target_value(dec_val, raw, rec.value)
        ]

        if matches:
            # Pick earliest query_id and sort remaining
            matches.sort(key=lambda r: _query_sort_key(r.query_id))
            best = matches[0]
            also_in = list(dict.fromkeys([m.query_id for m in matches[1:] if m.query_id != best.query_id]))
            derived_from_set.add(best.query_id)

            # Discover entity from matched row if available (e.g. 'Phones' or 'Fasteners')
            entity_label = None
            q_rows = sql_rows_by_qid.get(best.query_id) or []
            if 0 <= best.row_index < len(q_rows):
                entity_label = _find_entity_in_row(q_rows[best.row_index], best.column)

            input_records.append({
                "name": name or raw,
                "value": float(dec_val) if dec_val % 1 != 0 else int(dec_val),
                "raw": raw,
                "query_id": best.query_id,
                "row_index": best.row_index,
                "dataset": best.table_label or best.dataset_id,
                "column": best.column,
                "entity": entity_label,
                "also_in": also_in,
                "literal_in_code": False,
            })
        else:
            input_records.append({
                "name": name or raw,
                "value": float(dec_val) if dec_val % 1 != 0 else int(dec_val),
                "raw": raw,
                "query_id": None,
                "row_index": None,
                "dataset": None,
                "column": None,
                "entity": None,
                "also_in": [],
                "literal_in_code": True,
            })

    # Inherit lineage from dataframes passed via inputs (e.g. ["data"] or ["sql_1"])
    if not derived_from_set and prior:
        # If no literals matched but dataframes were passed, link to the first SQL query
        first_sql_qid = min((r.query_id for r in prior), key=_query_sort_key, default=1)
        derived_from_set.add(first_sql_qid)

    sorted_derived_from = sorted(list(derived_from_set), key=_query_sort_key)
    return input_records[:50], sorted_derived_from


def collect_python_evidence(
    query_id: int | str,
    code: str,
    inputs: list,
    py_results: dict,
    prior_evidence: list[EvidenceRecord] | None = None,
    sql_results: dict[str, list[dict]] | None = None,
    variables: dict[str, Any] | None = None,
) -> tuple[dict, list[EvidenceRecord]]:
    """Build structured query dict and typed EvidenceRecords for Python calculation with input lineage."""
    input_lineage, derived_from = extract_python_input_lineage(
        code=code,
        inputs=inputs,
        prior_evidence=prior_evidence,
        sql_results=sql_results,
        variables=variables,
    )

    clean_code = (code or "").strip()[:4000]

    query_info = {
        "query_id": query_id,
        "tool": "python",
        "type": "python",
        "code": clean_code,
        "inputs": input_lineage,
        "result": py_results,
        "derived_from": derived_from,
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
                    table_label="Calculated by Python",
                    column=str(label),
                    kind="python",
                    row_index=0,
                    value=norm,
                    raw_string=str(val).strip(),
                    derived_from=derived_from,
                )
            )

    return query_info, records
