"""Evaluation score tracking and execution services."""

from __future__ import annotations

import json
import uuid

from eval.runner import THRESHOLDS, evaluate
from packages.ingest.store import execute, sql_literal


def list_eval_runs() -> dict:
    """Retrieve the latest summary evaluation run."""
    rows = execute(
        "SELECT metrics_json, created_at FROM eval_results "
        "WHERE question_id = 'summary' ORDER BY id DESC LIMIT 1"
    )
    if not rows:
        return {"scores": None}
    return {"scores": json.loads(rows[0]["metrics_json"]), "created_at": rows[0]["created_at"]}


def create_eval_run() -> dict:
    """Trigger the golden set evaluation suite and persist results."""
    result = evaluate()
    scores = {name: result["scores"][name] for name in THRESHOLDS}
    passed = result["exit_code"] == 0
    payload = json.dumps({"scores": scores, "problems": result["problems"]})
    eval_run_id = uuid.uuid4().hex[:12]
    execute(
        "INSERT INTO eval_results (eval_run_id, question_id, passed, metrics_json) "
        f"VALUES ({sql_literal(eval_run_id)}, 'summary', "
        f"{'true' if passed else 'false'}, {sql_literal(payload)}::jsonb)"
    )
    return {"eval_run_id": eval_run_id, "passed": passed, "scores": scores}

