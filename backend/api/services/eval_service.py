"""Evaluation score tracking and execution services."""

from __future__ import annotations

import uuid

from eval.runner import THRESHOLDS, evaluate


def list_eval_runs() -> dict:
    """Retrieve the latest summary evaluation run."""
    return {"scores": None}


def create_eval_run() -> dict:
    """Trigger the golden set evaluation suite."""
    result = evaluate()
    scores = {name: result["scores"][name] for name in THRESHOLDS}
    passed = result["exit_code"] == 0
    eval_run_id = uuid.uuid4().hex[:12]
    return {"eval_run_id": eval_run_id, "passed": passed, "scores": scores}

