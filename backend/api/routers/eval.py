"""Golden set evaluation triggers and score history endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from api.services.eval_service import create_eval_run, list_eval_runs

router = APIRouter()


@router.get("/eval/runs")
def list_eval_runs_endpoint():
    """Get the latest evaluation scorecard."""
    return list_eval_runs()


@router.post("/eval/runs")
def create_eval_run_endpoint():
    """Trigger an evaluation run against the golden set."""
    return create_eval_run()

