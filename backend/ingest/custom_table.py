"""Deterministic creation, row loading, and RLS management for approved custom tables."""

from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from db.models import Dataset, DatasetColumn, Upload
from db.session import session_scope
from ingest.schema_validation import (
    COLUMN_NAME_PATTERN,
    POSTGRES_RESERVED,
    SYSTEM_RESERVED_COLUMNS,
)
from ingest.store import execute, get_writer_connection
from utils import esc_tsv, to_uuid

TYPE_TO_PG = {
    "text": "text",
    "integer": "bigint",
    "numeric": "numeric(18, 4)",
    "date": "date",
    "boolean": "boolean",
}


def compute_headers_hash(headers: list[str]) -> str:
    """Compute normalized SHA256 fingerprint for caching schema proposals."""
    norm = [re.sub(r"\s+", " ", h.strip().lower()) for h in headers]
    norm.sort()
    blob = "|".join(norm).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def get_cached_proposal(workspace_id: int | str, header_hash: str) -> dict[str, Any] | None:
    """Lookup previously approved schema for identical normalized header set in workspace."""
    try:
        ws_uuid = to_uuid(workspace_id)
        with session_scope() as session:
            proposal = session.execute(
                select(Dataset.proposal_json)
                .where(Dataset.workspace_id == ws_uuid, Dataset.header_hash == header_hash)
                .order_by(Dataset.approved_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if proposal:
                return proposal if isinstance(proposal, dict) else json.loads(proposal)
    except Exception:
        pass
    return None


def sanitize_column_name(name: str) -> str:
    """Safe identifier quoting helper. Raises ValueError on invalid identifier."""
    clean = name.strip().lower()
    if not COLUMN_NAME_PATTERN.match(clean):
        raise ValueError(f"Invalid column identifier: '{name}'")
    if clean in POSTGRES_RESERVED or clean in SYSTEM_RESERVED_COLUMNS:
        raise ValueError(f"Reserved identifier: '{name}'")
    return f'"{clean}"'


def build_create_table_ddl(
    table_name: str,
    columns: list[dict[str, Any]],
) -> str:
    """Build deterministic CREATE TABLE DDL strictly in user_data schema with safe identifier quoting."""
    if not re.match(r"^ds_[a-z0-9_]{1,63}$", table_name):
        raise ValueError(f"Invalid table name format: '{table_name}'")

    col_defs = [
        "row_id bigserial PRIMARY KEY",
        "workspace_id uuid NOT NULL",
        "upload_id uuid NOT NULL",
    ]

    for col in columns:
        if col.get("excluded", False):
            continue
        c_name = col["column_name"].strip().lower()
        quoted_name = sanitize_column_name(c_name)
        c_type = col["type"].strip().lower()
        pg_type = TYPE_TO_PG.get(c_type, "text")
        col_defs.append(f"{quoted_name} {pg_type}")

    cols_joined = ",\n    ".join(col_defs)
    ddl = (
        f"CREATE TABLE IF NOT EXISTS user_data.{table_name} (\n"
        f"    {cols_joined}\n"
        f");\n"
        f"ALTER TABLE user_data.{table_name} ENABLE ROW LEVEL SECURITY;\n"
        f"ALTER TABLE user_data.{table_name} FORCE ROW LEVEL SECURITY;\n"
        f"DROP POLICY IF EXISTS {table_name}_reader_workspace ON user_data.{table_name};\n"
        f"CREATE POLICY {table_name}_reader_workspace ON user_data.{table_name}\n"
        f"    FOR SELECT TO nexus_reader\n"
        f"    USING (workspace_id = (NULLIF(current_setting('app.workspace_id', true), ''))::uuid);\n"
        f"DROP POLICY IF EXISTS {table_name}_writer_all ON user_data.{table_name};\n"
        f"CREATE POLICY {table_name}_writer_all ON user_data.{table_name}\n"
        f"    FOR ALL TO nexus_writer USING (true) WITH CHECK (true);\n"
        f"DROP POLICY IF EXISTS {table_name}_ingest_all ON user_data.{table_name};\n"
        f"CREATE POLICY {table_name}_ingest_all ON user_data.{table_name}\n"
        f"    FOR ALL TO nexus_ingest USING (true) WITH CHECK (true);\n"
        f"GRANT SELECT ON user_data.{table_name} TO nexus_reader;\n"
        f"GRANT ALL ON user_data.{table_name} TO nexus_writer;\n"
        f"GRANT ALL ON user_data.{table_name} TO nexus_ingest;\n"
    )
    return ddl


def create_and_load_custom_table(
    upload_id: int | str,
    workspace_id: int | str,
    table_label: str,
    grain: str,
    grain_key_columns: list[str],
    columns: list[dict[str, Any]],
    raw_rows: list[tuple[int, list[str]]],
    header_line: int,
    header_hash: str | None = None,
    approved_by: str = "user",
    proposal_json: dict[str, Any] | None = None,
    progress_callback=None,
) -> tuple[str, int, str]:
    """Execute DDL, register dataset, and stream COPY rows into user_data.<table_name>."""
    sanitized_up_id = str(upload_id).replace("-", "_")
    table_name = f"ds_{sanitized_up_id}"
    active_cols = [c for c in columns if not c.get("excluded", False)]

    # 1. Generate & execute DDL
    ddl = build_create_table_ddl(table_name, active_cols)
    execute(ddl)

    # 2. Register dataset in datasets and dataset_columns catalogs using SQLAlchemy ORM
    up_uuid = to_uuid(upload_id)
    ws_uuid = to_uuid(workspace_id)

    with session_scope() as session:
        # Remove any existing dataset for this upload
        existing = session.execute(
            select(Dataset).where(Dataset.upload_id == up_uuid)
        ).scalar_one_or_none()
        if existing:
            session.delete(existing)
            session.flush()

        ds = Dataset(
            workspace_id=ws_uuid,
            upload_id=up_uuid,
            table_name=table_name,
            table_label=table_label,
            grain=grain,
            grain_key_columns=grain_key_columns,
            header_hash=header_hash,
            approved_by=approved_by,
            proposal_json=proposal_json or {},
        )
        session.add(ds)
        session.flush()

        up = session.get(Upload, up_uuid)
        if up:
            up.custom_table_name = table_name

        dataset_id = ds.id

        # Register columns
        for col in active_cols:
            c_name = str(col.get("column_name") or "").strip().lower()
            if not c_name:
                continue
            s_name = str(col.get("source_name") or c_name).strip()
            c_type = str(col.get("type") or "text").strip().lower()
            c_role = str(col.get("role") or "dimension").strip().lower()
            c_desc = str(col.get("description") or "").strip()
            c_unit = col.get("unit")
            c_nullable = bool(col.get("nullable", True))
            try:
                c_null_rate = float(col.get("null_rate") or 0.0)
            except (ValueError, TypeError):
                c_null_rate = 0.0

            col_obj = DatasetColumn(
                dataset_id=dataset_id,
                column_name=c_name,
                source_name=s_name,
                type=c_type,
                role=c_role,
                description=c_desc,
                unit=c_unit,
                nullable=c_nullable,
                null_rate=c_null_rate,
            )
            session.add(col_obj)

    # 3. Clean and parse rows for COPY
    hdr_idx = next((i for i, r in enumerate(raw_rows) if r[0] == header_line), 0)
    headers = [h.strip() for h in raw_rows[hdr_idx][1]]
    source_to_idx = {h: i for i, h in enumerate(headers)}
    col_mapping = [
        (c["column_name"], c["type"], source_to_idx.get(c["source_name"]), c.get("date_format"))
        for c in active_cols
        if c["source_name"] in source_to_idx
    ]

    loaded = 0
    quarantined = 0
    data_buf = io.StringIO()
    quar_buf = io.StringIO()

    for line_number, cells in raw_rows:
        if line_number <= header_line:
            continue

        row_vals = []
        is_bad = False
        bad_reason = ""

        raw_dict = {
            headers[i]: cells[i] if i < len(cells) else ""
            for i in range(len(headers))
        }

        for col_name, c_type, src_idx, dt_fmt in col_mapping:
            cell_val = cells[src_idx].strip() if src_idx is not None and src_idx < len(cells) else ""
            if not cell_val:
                row_vals.append(r"\N")
                continue

            if c_type == "text":
                row_vals.append(esc_tsv(cell_val))
            elif c_type == "integer":
                try:
                    num = int(cell_val.replace(",", "").split(".")[0])
                    row_vals.append(str(num))
                except Exception:
                    is_bad = True
                    bad_reason = f"Invalid integer for {col_name}: '{cell_val}'"
                    break
            elif c_type == "numeric":
                try:
                    dec = Decimal(cell_val.replace(",", "").replace("$", "").replace("%", ""))
                    row_vals.append(str(dec))
                except Exception:
                    is_bad = True
                    bad_reason = f"Invalid numeric for {col_name}: '{cell_val}'"
                    break
            elif c_type == "date":
                parsed = None
                formats = [dt_fmt] if dt_fmt else ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]
                for fmt in formats:
                    if not fmt:
                        continue
                    try:
                        parsed = datetime.strptime(cell_val, fmt).date()
                        break
                    except ValueError:
                        continue
                if parsed:
                    row_vals.append(str(parsed))
                else:
                    is_bad = True
                    bad_reason = f"Invalid date for {col_name}: '{cell_val}'"
                    break
            elif c_type == "boolean":
                low = cell_val.lower()
                if low in {"true", "t", "1", "yes", "y"}:
                    row_vals.append("true")
                elif low in {"false", "f", "0", "no", "n"}:
                    row_vals.append("false")
                else:
                    is_bad = True
                    bad_reason = f"Invalid boolean for {col_name}: '{cell_val}'"
                    break

        if is_bad:
            quar_buf.write(f"{upload_id}\t{line_number}\t{esc_tsv(bad_reason)}\t{esc_tsv(json.dumps(raw_dict))}\n")
            quarantined += 1
            continue

        loaded += 1
        line_tsv = f"{workspace_id}\t{upload_id}\t" + "\t".join(row_vals) + "\n"
        data_buf.write(line_tsv)

        if loaded % 5000 == 0 and progress_callback:
            progress_callback({"event": "load_progress", "loaded": loaded, "quarantined": quarantined})

    data_buf.seek(0)
    quar_buf.seek(0)

    # 4. Stream via COPY into staging table, then INSERT into RLS table
    conn = get_writer_connection()
    with conn:
        with conn.cursor() as cur:
            if loaded > 0:
                quoted_cols = [sanitize_column_name(c[0]) for c in col_mapping]
                cols_sql = ", ".join(["workspace_id", "upload_id"] + quoted_cols)
                cur.execute(f"CREATE TEMP TABLE staging_custom_table AS SELECT {cols_sql} FROM user_data.{table_name} WITH NO DATA;")
                copy_sql = f"COPY staging_custom_table ({cols_sql}) FROM STDIN WITH (FORMAT text, NULL '\\N')"
                cur.copy_expert(copy_sql, data_buf)
                cur.execute(f"INSERT INTO user_data.{table_name} ({cols_sql}) SELECT {cols_sql} FROM staging_custom_table; TRUNCATE staging_custom_table;")

            if quarantined > 0:
                cur.execute("""
                    CREATE TEMP TABLE IF NOT EXISTS staging_quarantine AS SELECT * FROM quarantine WITH NO DATA;
                    ALTER TABLE staging_quarantine DROP COLUMN IF EXISTS id;
                """)
                cur.copy_expert(
                    "COPY staging_quarantine (upload_id, row_number, reason, raw_row) FROM STDIN WITH (FORMAT text, NULL '\\N')",
                    quar_buf,
                )
                cur.execute("""
                    INSERT INTO quarantine (upload_id, row_number, reason, raw_row)
                    SELECT upload_id, row_number, reason, raw_row FROM staging_quarantine;
                    TRUNCATE staging_quarantine;
                """)

    # Update row count in catalog via SQLAlchemy ORM
    with session_scope() as session:
        ds = session.get(Dataset, dataset_id)
        if ds:
            ds.row_count = loaded

    return loaded, quarantined, table_name
