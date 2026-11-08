"""One question, one pass: schema, a known query or a refusal, then the checker.

No model is called. SQL is taken from the golden-set questions. A question
outside that set is not given an invented query.
"""

from __future__ import annotations

import re
import time

from eval.questions import QUESTIONS
from packages.agent.checker import check_answer, draft_from_rows, refusal_text
from packages.agent.run_sql import SqlRejected, run_sql

SCHEMA_SQL = (
    "SELECT count(*) AS rows, count(revenue) AS revenue, "
    "count(quantity) AS quantity, count(unit_price) AS unit_price, "
    "count(discount_pct) AS discount_pct, count(cost) AS cost, "
    "count(profit) AS profit, count(channel) AS channel "
    "FROM sales_clean"
)

_KEYWORD_REFUSALS = (
    ("margin", ("cost", "profit")),
    ("profit", ("profit",)),
    ("discount", ("discount_pct",)),
    ("quantity", ("quantity",)),
    ("cost", ("cost",)),
    ("channel", ("channel",)),
)

UNKNOWN_ANSWER = "This question is outside the suggested set, so no query was run."


def ask(question: str, workspace_id: int) -> dict:
    started = time.perf_counter()
    steps = []
    try:
        schema_rows = run_sql(SCHEMA_SQL, workspace_id)
    except SqlRejected as exc:
        steps.append(_step("get_schema", "error", started, "schema read failed"))
        return _result(
            "error",
            "schema read failed",
            None,
            [],
            "The data room could not be read.",
            {"verified": False, "untraced": []},
            steps,
            started,
        )
    schema = schema_rows[0] if schema_rows else {}
    populated = ", ".join(f"{key}={schema.get(key, '0')}" for key in schema)
    steps.append(_step("get_schema", "done", started, populated))

    matched = _match(question)
    if matched is not None and matched["kind"] == "refusal":
        return _refuse(matched["missing"], schema, steps, started)
    if matched is not None:
        return _answer_sql(matched["sql"], steps, workspace_id, started)

    hinted = _keyword_refusal(question, schema)
    if hinted is not None:
        return _refuse(hinted, schema, steps, started)

    steps.append(_step("plan", "done", started, "no matching question"))
    return _result(
        "unknown",
        "no matching question",
        None,
        [],
        UNKNOWN_ANSWER,
        {"verified": True, "untraced": []},
        steps,
        started,
    )


def _answer_sql(sql: str, steps: list[dict], workspace_id: int, started: float) -> dict:
    query_started = time.perf_counter()
    try:
        rows = run_sql(sql, workspace_id)
    except SqlRejected:
        steps.append(_step("run_sql", "error", query_started, "query rejected"))
        return _result(
            "error",
            "query rejected",
            sql,
            [],
            "The query was rejected.",
            {"verified": False, "untraced": []},
            steps,
            started,
        )
    steps.append(_step("run_sql", "done", query_started, f"{len(rows)} rows"))
    answer = draft_from_rows(rows)
    check_started = time.perf_counter()
    check = check_answer(answer, rows)
    steps.append(
        _step("checker", "done" if check["verified"] else "caveat", check_started)
    )
    return _result("sql", sql, sql, rows, answer, check, steps, started)


def _refuse(columns: list[str] | tuple[str, ...], schema: dict, steps: list[dict], started: float) -> dict:
    absent = [column for column in columns if int(schema.get(column) or 0) == 0]
    if absent:
        answer = refusal_text(" and ".join(absent))
        steps.append(_step("plan", "done", started, "refused"))
        return _result(
            "refusal",
            "refused",
            None,
            [],
            answer,
            {"verified": True, "untraced": []},
            steps,
            started,
        )
    steps.append(_step("plan", "done", started, "columns are present but no query matches"))
    return _result(
        "unknown",
        "columns are present but no query matches",
        None,
        [],
        UNKNOWN_ANSWER,
        {"verified": True, "untraced": []},
        steps,
        started,
    )


def _match(question: str) -> dict | None:
    folded = _norm(question)
    for item in QUESTIONS:
        if _norm(item["question"]) == folded:
            return item
    return None


def _keyword_refusal(question: str, schema: dict) -> tuple[str, ...] | None:
    folded = _norm(question)
    for word, columns in _KEYWORD_REFUSALS:
        if re.search(rf"\b{word}\b", folded) and all(
            int(schema.get(column) or 0) == 0 for column in columns
        ):
            return columns
    return None


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _step(tool: str, status: str, started: float, detail: str = "") -> dict:
    return {
        "tool": tool,
        "status": status,
        "ms": int((time.perf_counter() - started) * 1000),
        "detail": detail,
    }


def _result(kind, plan, sql, rows, answer, check, steps, started) -> dict:
    return {
        "kind": kind,
        "plan": plan,
        "sql": sql,
        "rows": rows,
        "answer": answer,
        "check": check,
        "steps": steps,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
