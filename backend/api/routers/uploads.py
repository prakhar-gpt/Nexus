"""Upload status, mapping confirmation, and quarantine routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.services.upload_service import (
    get_upload_health_summary,
    get_upload_mapping_detail,
    stream_upload_events,
    update_column_mappings,
)
from api.services.workspace_service import get_mappings

router = APIRouter()


class MappingUpdate(BaseModel):
    decisions: dict[str, str]


@router.get("/uploads/{upload_id}/events")
async def upload_events_endpoint(upload_id: int):
    """Stream real-time ingestion events for an uploaded file."""
    return StreamingResponse(
        stream_upload_events(upload_id),
        media_type="text/event-stream",
    )


@router.get("/uploads/{upload_id}/mapping")
def get_upload_mapping_endpoint(upload_id: int):
    """Fetch column mappings, preview, capabilities, and dynamic attributes for an upload."""
    return get_upload_mapping_detail(upload_id)


@router.post("/uploads/{upload_id}/mapping")
@router.put("/uploads/{upload_id}/mapping")
def update_mapping_endpoint(upload_id: int, body: MappingUpdate):
    """Confirm user column mappings and transition upload to active status."""
    return update_column_mappings(upload_id, body.decisions)


@router.get("/uploads/{upload_id}/quarantine")
def get_upload_quarantine_endpoint(upload_id: int):
    """Fetch quarantined rows and reason breakdown for an upload."""
    return get_upload_health_summary(upload_id)
