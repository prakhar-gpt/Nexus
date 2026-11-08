"""Reject anything that is not one read-only SELECT against sales_clean,
and reject arithmetic between aggregates / cross-subquery math with instructions to call run_python."""

from __future__ import annotations

import re
import sqlglot
from sqlglot import exp


class SqlRejected(ValueError):
    pass


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

    # Verify statement root is Select or With (Union is also acceptable if sub-selects are safe)
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


def guard_sql(sql: str) -> str:
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
        raise SqlRejected("Statement calls a forbidden function.")
    if _SCHEMA.search(masked):
        raise SqlRejected("Schema-qualified names are not allowed.")

    scan = _EXTRACT_FROM.sub(" ", masked)
    cte_names = {match.group(1).lower() for match in _CTE_NAME.finditer(scan)}
    relations = {match.group(1).lower() for match in _RELATION.finditer(scan)}
    allowed = cte_names | {"sales_clean"}
    unexpected = relations - allowed
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise SqlRejected(f"Query may read only sales_clean, not {names}.")
    if "sales_clean" not in relations:
        raise SqlRejected("Query must read sales_clean.")

    # AST checks with sqlglot
    _check_ast(cleaned)

    return cleaned
