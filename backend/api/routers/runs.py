"""Feedback and export endpoints for conversation runs."""

from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.dependencies import require_run_access
from api.services.chat_service import export_result_csv, record_feedback
from db.models import Run

router = APIRouter()


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    reason: str | None = None


@router.post("/runs/{run_id}/feedback")
def add_feedback_endpoint(
    run_id: str,
    body: FeedbackRequest,
    _run: Run = Depends(require_run_access),
):
    """Save feedback rating and optional comment for a run."""
    return record_feedback(run_id, body.rating, body.reason)


@router.get("/results/{run_id}/export")
def export_result_endpoint(
    run_id: str,
    _run: Run = Depends(require_run_access),
):
    """Export query output rows as a sanitized CSV file."""
    return export_result_csv(run_id)
