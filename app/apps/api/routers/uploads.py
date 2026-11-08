"""Upload status, mapping confirmation, and quarantine routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from apps.api.schemas import MappingUpdate
from apps.api.services.upload_service import (
    get_upload_health_summary,
    stream_upload_events,
    update_column_mappings,
)
from apps.api.services.workspace_service import get_mappings

router = APIRouter()


@router.get("/uploads/{upload_id}/events")
async def upload_events_endpoint(upload_id: int):
    """Stream real-time ingestion events for an uploaded file."""
    return StreamingResponse(
        stream_upload_events(upload_id),
        media_type="text/event-stream",
    )


@router.get("/uploads/{upload_id}/mapping")
def get_mapping_endpoint(upload_id: int):
    """Retrieve column mapping proposals for an upload."""
    return {"mappings": get_mappings(upload_id)}


@router.put("/uploads/{upload_id}/mapping")
def put_mapping_endpoint(upload_id: int, body: MappingUpdate):
    """Confirm or update column mapping choices for an upload."""
    return update_column_mappings(upload_id, body.decisions)


@router.get("/uploads/{upload_id}/health")
def upload_health_endpoint(upload_id: int, download: str | None = None):
    """Retrieve upload summary or download quarantine report CSV."""
    return get_upload_health_summary(upload_id, download=download)
