"""Feedback and export endpoints for conversation runs."""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas import FeedbackRequest
from api.services.chat_service import export_result_csv, record_feedback

router = APIRouter()


@router.post("/runs/{run_id}/feedback")
def add_feedback_endpoint(run_id: int, body: FeedbackRequest):
    """Save feedback rating and optional comment for a run."""
    return record_feedback(run_id, body.rating, body.reason)


@router.get("/results/{run_id}/export")
def export_result_endpoint(run_id: int):
    """Export query output rows as a sanitized CSV file."""
    return export_result_csv(run_id)

