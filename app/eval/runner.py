"""Run the Week 1 golden set. Exit 1 when a score is below its target.

This scores verified SQL, the number checker, and refusals. It does not call a model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))

from eval.questions import QUESTIONS  # noqa: E402
from packages.agent.checker import (  # noqa: E402
    check_answer,
    draft_from_rows,
    extract_numbers,
    refusal_text,
)
from packages.agent.run_sql import populated_count, run_sql  # noqa: E402
from packages.agent.sql_guard import SqlRejected, guard_sql  # noqa: E402

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_set.json"
WORKSPACE_ID = 1
THRESHOLDS = {
    "sql_correctness": 0.85,
    "numeric_faithfulness": 0.98,
    "refusal_accuracy": 0.90,
}

GUARD_CASES = [
    ("SELECT sum(revenue) AS revenue FROM sales_clean", True),
    ("INSERT INTO sales_clean (revenue) VALUES (1)", False),
    ("SELECT sum(revenue) FROM sales_clean; DROP TABLE sales_clean", False),
    ("SELECT * FROM public.sales_clean", False),
    ("SELECT pg_read_file('secrets') FROM sales_clean", False),
    ("SELECT set_config('app.workspace_id', '2', true) FROM sales_clean", False),
    ("UPDATE sales_clean SET revenue = 0", False),
]


def _load_golden() -> dict:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def _guard_failures() -> list[str]:
    failures = []
    for sql, should_allow in GUARD_CASES:
        try:
            guard_sql(sql)
            allowed = True
        except SqlRejected:
            allowed = False
        if allowed != should_allow:
            failures.append(sql)
    return failures


def _score(passed: int, total: int) -> float:
    if total == 0:
        return 1.0
    return passed / total


def run() -> int:
    golden = _load_golden()
    expected = {item["id"]: item.get("expected_rows") for item in golden["questions"]}
    guard_failures = _guard_failures()

    other_workspace = run_sql("SELECT count(*) AS row_count FROM sales_clean", 999)
    if other_workspace != [{"row_count": "0"}]:
        problems_prefix = ["workspace filter returned rows for an empty workspace"]
    else:
        problems_prefix = []

    sql_passed = 0
    sql_total = 0
    faith_passed = 0
    faith_total = 0
    refusal_passed = 0
    refusal_total = 0
    problems = list(problems_prefix)

    for question in QUESTIONS:
        if question["kind"] == "sql":
            sql_total += 1
            rows = run_sql(question["sql"], WORKSPACE_ID)
            if rows == expected.get(question["id"]):
                sql_passed += 1
            else:
                problems.append(f"{question['id']} SQL result drifted")

            draft = draft_from_rows(rows)
            faith_total += 1
            if check_answer(draft, rows)["verified"]:
                faith_passed += 1
            else:
                problems.append(f"{question['id']} checker rejected a faithful draft")

            faith_total += 1
            tampered = draft + "\nextra=999999"
            if not check_answer(tampered, rows)["verified"]:
                faith_passed += 1
            else:
                problems.append(f"{question['id']} checker accepted a bad number")
            continue

        refusal_total += 1
        absent = [
            column
            for column in question["missing"]
            if populated_count(WORKSPACE_ID, column) == 0
        ]
        answer = refusal_text(" and ".join(question["missing"]))
        if absent == question["missing"] and extract_numbers(answer) == []:
            refusal_passed += 1
        else:
            problems.append(f"{question['id']} refusal failed")

    scores = {
        "sql_correctness": _score(sql_passed, sql_total),
        "numeric_faithfulness": _score(faith_passed, faith_total),
        "refusal_accuracy": _score(refusal_passed, refusal_total),
    }
    print(f"questions={len(QUESTIONS)} guard_failures={len(guard_failures)}")
    for name, score in scores.items():
        target = THRESHOLDS[name]
        print(f"{name}={score:.2%} target={target:.0%}")
    for problem in problems:
        print(problem)
    for failure in guard_failures:
        print(f"guard failed: {failure}")

    below = [name for name, score in scores.items() if score < THRESHOLDS[name]]
    if guard_failures or below or problems:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())
