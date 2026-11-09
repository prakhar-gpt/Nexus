"""run_sql tool: AST-guarded, read-only SQL query execution under nexus_reader with RLS."""

from __future__ import annotations

import csv
import io
import re
from langchain_core.tools import tool
import sqlglot
from sqlglot import exp

from agent.db import DATABASE, READER_USER, DatabaseError, psql, reader_password

try:
    from config import settings
    ROW_LIMIT = settings.NEXUS_TOOL_SQL_ROW_LIMIT
    TIMEOUT_MS = settings.NEXUS_TOOL_SQL_TIMEOUT_MS
    PREVIEW_LIMIT = settings.NEXUS_TOOL_SQL_PREVIEW_LIMIT
except Exception:
    ROW_LIMIT = 200
    TIMEOUT_MS = 5000
    PREVIEW_LIMIT = 25


class SqlRejected(ValueError):
    """Raised when a SQL query is rejected by syntax, security, or math-guard rules."""
    pass


# ---------------------------------------------------------------------------
# Declarative Tool Definition for LangChain / LangGraph
# ---------------------------------------------------------------------------

@tool("run_sql")
def run_sql_tool(sql: str) -> str:
    """Run one read-only SELECT against approved workspace tables for data extraction and basic aggregations (GROUP BY, SUM, COUNT, AVG, MIN, MAX).
    Pass only the SQL text.
    STRICTLY FORBIDDEN: Do NOT calculate differences, percentages, growth rates, or ratios in SQL. Use run_python for all math."""


# ---------------------------------------------------------------------------
# SQL Guard (AST inspection with sqlglot)
# ---------------------------------------------------------------------------

_FORBIDDEN = re.compile(
    r"(?is)\b("
    r"insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|"
    r"comment|vacuum|call|do|execute|prepare|set|reset|listen|notify|lock|"
    r"checkpoint|reindex|cluster|discard|load|into|merge|refresh|reassign|"
    r"import|security|table|analyze|explain|show"
    r")\b"
)

_DANGEROUS_FN = re.compile(
    r"(?is)\b("
    r"pg_read_file|pg_read_binary_file|pg_ls_dir|pg_stat_file|pg_write_file|"
    r"pg_reload_conf|lo_import|lo_export|lo_get|lo_put|dblink|dblink_exec|"
    r"pg_sleep|pg_terminate_backend|pg_cancel_backend|set_config"
    r")\s*\("
)

_SCHEMA = re.compile(r"(?is)\b(public|pg_catalog|information_schema|pg_temp)\b")
_EXTRACT_FROM = re.compile(r"(?is)\b(?:extract|trim|substring|overlay)\s*\([^)]*\)")
_CTE_NAME = re.compile(r"(?is)\b([a-z_][a-z0-9_]*)\s+as\s*\(")
_RELATION = re.compile(r"(?is)\b(?:from|join)\s+(?:only\s+|lateral\s+)?([a-z_][a-z0-9_]*)")

_COMMENT_LINE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING = re.compile(r"'(?:''|[^'])*'")


def _check_ast(cleaned_sql: str) -> None:
    """Parse with sqlglot to detect arithmetic between aggregates or across subquery rows."""
    try:
        parsed = sqlglot.parse(cleaned_sql, read="postgres")
    except Exception as exc:
        raise SqlRejected(f"SQL parsing error: {exc}") from exc

    if not parsed or len(parsed) != 1 or parsed[0] is None:
        raise SqlRejected("Only one valid SQL statement is allowed.")

    tree = parsed[0]

    if not isinstance(tree, (exp.Select, exp.Union)):
        raise SqlRejected("Only a SELECT statement is allowed.")

    # 1. Direct arithmetic between or on aggregate functions
    for node in tree.find_all(exp.Binary):
        left_aggs = list(node.left.find_all(exp.AggFunc))
        right_aggs = list(node.right.find_all(exp.AggFunc))
        if left_aggs or right_aggs:
            raise SqlRejected(
                "Arithmetic between aggregate expressions or percent formulas (such as max(x)-min(x), "
                "differences of sums, or ratios of aggregates) is not allowed in SQL. "
                "Run a simple SELECT/GROUP BY query and call run_python to calculate differences, ratios, and percentages."
            )

    # 2. Arithmetic in an outer query across an aggregate subquery
    for subquery in tree.find_all(exp.Subquery):
        if list(subquery.find_all(exp.AggFunc)):
            parent_select = subquery.find_ancestor(exp.Select)
            if parent_select:
                for select_expr in parent_select.expressions:
                    if list(select_expr.find_all(exp.Binary)):
                        raise SqlRejected(
                            "Arithmetic across subquery aggregate rows or percent formulas is not allowed in SQL. "
                            "Run a simple SELECT/GROUP BY query and call run_python to calculate differences, ratios, and percentages."
                        )


def get_allowed_tables(workspace_id: int | str | None = None, allowed_dataset_ids: list[str | int] | None = None) -> set[str]:
    """Fetch allowed query tables dynamically from datasets catalog (+ sales_clean fallback)."""
    allowed = set()
    if workspace_id is not None:
        try:
            from sqlalchemy import select
            from db.models import Dataset
            from db.session import session_scope
            from utils import to_uuid

            ws_uuid = to_uuid(workspace_id)
            with session_scope() as session:
                stmt = select(Dataset.id, Dataset.table_name).where(Dataset.workspace_id == ws_uuid)
                if allowed_dataset_ids is not None:
                    allowed_uuids = [to_uuid(i) for i in allowed_dataset_ids]
                    stmt = stmt.where(Dataset.id.in_(allowed_uuids))
                for ds_id, t_name in session.execute(stmt).all():
                    if t_name:
                        allowed.add(t_name.lower())
        except Exception:
            pass
    if not allowed or workspace_id is None:
        allowed.add("sales_clean")
    return allowed


def guard_sql(sql: str, workspace_id: int | str | None = None, allowed_dataset_ids: list[str | int] | None = None) -> str:
    """Validate that query is a single, safe SELECT query against allowed tables without aggregate arithmetic or joins."""
    if sql is None or not str(sql).strip():
        raise SqlRejected("SQL is empty.")
    if len(sql) > 8000:
        raise SqlRejected("SQL is longer than 8000 characters.")

    cleaned = _COMMENT_BLOCK.sub(" ", sql)
    cleaned = _COMMENT_LINE.sub(" ", cleaned).strip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()
    if ";" in cleaned:
        raise SqlRejected("Only one statement is allowed.")

    masked = _STRING.sub("''", cleaned)
    if not re.match(r"(?is)\s*(select|with)\b", masked):
        raise SqlRejected("Only a SELECT statement is allowed.")
    if _FORBIDDEN.search(masked):
        raise SqlRejected("Statement contains a forbidden keyword.")
    if _DANGEROUS_FN.search(masked):
        raise SqlRejected("Statement calls a dangerous function.")
    if _SCHEMA.search(masked):
        raise SqlRejected("Schema qualification is not allowed.")

    _check_ast(cleaned)

    stripped = _EXTRACT_FROM.sub("", masked)
    ctes = {match.group(1).lower() for match in _CTE_NAME.finditer(stripped)}
    all_workspace_tables = get_allowed_tables(workspace_id, allowed_dataset_ids=None)
    allowed_tables = get_allowed_tables(workspace_id, allowed_dataset_ids=allowed_dataset_ids)
    allowed = ctes | allowed_tables

    referenced_tables: list[str] = []
    for match in _RELATION.finditer(stripped):
        relation = match.group(1).lower()
        if relation not in allowed:
            if relation in all_workspace_tables:
                raise SqlRejected("That dataset is not enabled for this chat")
            raise SqlRejected(f"Table '{relation}' is not accessible or does not exist.")
        if relation not in ctes:
            referenced_tables.append(relation)

    # Multi-table queries, joins, and self-joins are forbidden in v1
    if len(referenced_tables) > 1:
        raise SqlRejected("Multi-table queries and joins are not supported. Query one table at a time.")

    return cleaned


# ---------------------------------------------------------------------------
# Execution Handlers
# ---------------------------------------------------------------------------

def execute_sql(sql: str, workspace_id: int | str, allowed_dataset_ids: list[str | int] | None = None) -> list[dict[str, str]]:
    """Execute raw SQL under reader role with RLS local isolation."""
    if workspace_id is None or str(workspace_id).strip() == "":
        raise SqlRejected("workspace_id cannot be empty.")
    ws_str = str(workspace_id).strip()
    cleaned = guard_sql(sql, workspace_id=ws_str, allowed_dataset_ids=allowed_dataset_ids)
    script = f"""
    BEGIN;
    SET LOCAL app.workspace_id = '{ws_str}';
    SET LOCAL search_path = user_data, public;
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


run_sql = execute_sql


def execute_query(sql: str, workspace_id: int | str, allowed_dataset_ids: list[str | int] | None = None) -> tuple[str, list[dict], str | None]:
    """Execute a read-only query and return prompt preview, raw rows, and validated SQL."""
    text = str(sql or "").strip()
    if not text:
        return "rejected: sql is empty", [], None
    try:
        rows = execute_sql(text, workspace_id, allowed_dataset_ids=allowed_dataset_ids)
    except SqlRejected as exc:
        return f"rejected: {exc}", [], None
    if not rows:
        return "0 rows", [], text

    header = list(rows[0].keys())
    lines = [", ".join(header)]

    # Token optimization: Preview cap covers categorical breakdowns without prompt bloat
    max_preview = PREVIEW_LIMIT
    for row in rows[:max_preview]:
        lines.append(", ".join("" if row.get(col) is None else str(row.get(col)) for col in header))
    if len(rows) > max_preview:
        lines.append(f"... ({len(rows) - max_preview} more rows available to run_python)")

    return "\n".join(lines), rows, text


def populated_count(workspace_id: int | str, column: str, table_name: str = "sales_clean") -> int:
    """Helper returning count of populated values for a column."""
    clean_col = column.strip().lower()
    if not clean_col.isidentifier():
        raise SqlRejected(f"Invalid column name: {column}")
    rows = execute_sql(
        f"SELECT count({clean_col}) AS populated FROM {table_name}",
        workspace_id,
    )
    if not rows:
        return 0
    return int(rows[0]["populated"])
