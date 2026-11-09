"""Evaluation score tracking and execution services."""

from __future__ import annotations

import json
import uuid

from eval.runner import THRESHOLDS, evaluate
from ingest.store import execute, sql_literal


def list_eval_runs() -> dict:
    """Retrieve the latest summary evaluation run."""
    try:
        rows = execute(
            "SELECT metrics_json, created_at FROM eval_results "
            "WHERE question_id = 'summary' ORDER BY id DESC LIMIT 1"
        )
        if not rows:
            return {"scores": None}
        return {"scores": json.loads(rows[0]["metrics_json"]), "created_at": rows[0]["created_at"]}
    except Exception:
        return {"scores": None}


def create_eval_run() -> dict:
    """Trigger the golden set evaluation suite."""
    result = evaluate()
    scores = {name: result["scores"][name] for name in THRESHOLDS}
    passed = result["exit_code"] == 0
    eval_run_id = uuid.uuid4().hex[:12]
    return {"eval_run_id": eval_run_id, "passed": passed, "scores": scores}

