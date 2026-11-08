"""Read-only SQL against one workspace's sales_clean rows."""

from __future__ import annotations

import csv
import io

from packages.agent.db import DATABASE, READER_USER, DatabaseError, psql, reader_password
from packages.agent.sql_guard import guard_sql

ROW_LIMIT = 200
TIMEOUT_MS = 5000

MEASURE_COLUMNS = frozenset(
    {
        "quantity",
        "unit_price",
        "discount_pct",
        "cost",
        "profit",
        "channel",
        "revenue",
    }
)


class SqlRejected(ValueError):
    pass


def run_sql(sql: str, workspace_id: int) -> list[dict[str, str]]:
    if isinstance(workspace_id, bool) or not isinstance(workspace_id, int):
        raise SqlRejected("workspace_id must be an integer.")
    if workspace_id < 1:
        raise SqlRejected("workspace_id must be positive.")
    cleaned = guard_sql(sql)
    script = f"""
    BEGIN;
    SET LOCAL app.workspace_id = '{workspace_id}';
    SET LOCAL statement_timeout = '{TIMEOUT_MS}';
    SET LOCAL transaction_read_only = on;
    SELECT * FROM (
    {cleaned}
    ) AS agent_result
    LIMIT {ROW_LIMIT};
    COMMIT;
    """
    try:
        output = psql(
            script,
            user=READER_USER,
            password=reader_password(),
            database=DATABASE,
        )
    except DatabaseError as exc:
        raise SqlRejected(str(exc)) from exc
    if not output.strip():
        return []
    return list(csv.DictReader(io.StringIO(output)))


def populated_count(workspace_id: int, column: str) -> int:
    if column not in MEASURE_COLUMNS:
        raise SqlRejected(f"{column} is not a measure column.")
    rows = run_sql(
        f"SELECT count({column}) AS populated FROM sales_clean",
        workspace_id,
    )
    if not rows:
        return 0
    return int(rows[0]["populated"])
