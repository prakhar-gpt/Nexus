"""Upload status, mapping confirmation, and quarantine routes."""

from __future__ import annotations

from fastapi import APIRouter, Query
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
async def upload_events_endpoint(
    upload_id: str,
    since: int = 0,
    last_event_id: int | None = None,
):
    """Stream real-time ingestion events for an uploaded file with sequence replay."""
    since_seq = last_event_id if last_event_id is not None else since
    return StreamingResponse(
        stream_upload_events(upload_id, since_seq=since_seq),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/uploads/{upload_id}/mapping")
def get_upload_mapping_endpoint(upload_id: str):
    """Fetch column mappings, preview, capabilities, and dynamic attributes for an upload."""
    return get_upload_mapping_detail(upload_id)


@router.post("/uploads/{upload_id}/mapping")
@router.put("/uploads/{upload_id}/mapping")
def update_mapping_endpoint(upload_id: str, body: MappingUpdate):
    """Confirm user column mappings and transition upload to active status."""
    return update_column_mappings(upload_id, body.decisions)


@router.get("/uploads/{upload_id}/quarantine")
@router.get("/uploads/{upload_id}/health")
def get_upload_quarantine_endpoint(upload_id: str, download: str | None = None):
    """Fetch quarantined rows and reason breakdown for an upload, or stream CSV download."""
    return get_upload_health_summary(upload_id, download=download)


# ---------------------------------------------------------------------------
# Schema Architect Endpoints
# ---------------------------------------------------------------------------

class SchemaProposalUpdate(BaseModel):
    table_label: str
    grain: str
    grain_key_columns: list[str] = []
    columns: list[dict]
    warnings: list[str] = []
    analysis_hints: list[str] = []


class SchemaRegenerateRequest(BaseModel):
    hint: str | None = None


@router.get("/uploads/{upload_id}/schema")
def get_schema_endpoint(upload_id: str):
    """Fetch Schema Architect proposal, deterministic validation result, and 10-row preview."""
    from api.services.upload_service import get_upload_schema
    return get_upload_schema(upload_id)


@router.post("/uploads/{upload_id}/schema/initiate")
def initiate_schema_endpoint(upload_id: str):
    """Trigger Schema Architect manually (e.g. from 'Or load as custom table instead')."""
    from api.services.upload_service import initiate_upload_schema
    return initiate_upload_schema(upload_id)


@router.put("/uploads/{upload_id}/schema")
def update_schema_endpoint(upload_id: str, body: SchemaProposalUpdate):
    """Save user edits to schema proposal and re-run deterministic validation."""
    from api.services.upload_service import update_upload_schema
    return update_upload_schema(upload_id, body.model_dump())


@router.post("/uploads/{upload_id}/schema/approve")
def approve_schema_endpoint(upload_id: str, thread_id: str | None = Query(default=None)):
    """Approve schema and execute deterministic table creation and COPY row load."""
    from api.services.upload_service import approve_upload_schema
    return approve_upload_schema(upload_id, thread_id=thread_id)


@router.post("/uploads/{upload_id}/schema/reject")
def reject_schema_endpoint(upload_id: str):
    """Reject schema proposal. Upload is marked rejected and no table is created."""
    from api.services.upload_service import reject_upload_schema
    return reject_upload_schema(upload_id)


@router.post("/uploads/{upload_id}/schema/regenerate")
def regenerate_schema_endpoint(upload_id: str, body: SchemaRegenerateRequest = SchemaRegenerateRequest()):
    """Re-run the Schema Architect with an optional user context hint (capped at 3 runs)."""
    from api.services.upload_service import regenerate_upload_schema
    return regenerate_upload_schema(upload_id, user_hint=body.hint)


@router.get("/uploads/{upload_id}/status")
def get_upload_status_endpoint(upload_id: str):
    """Lightweight status + schema proposal for rehydrating the chat timeline without streaming."""
    from api.services.upload_service import get_upload_status_for_rehydration
    return get_upload_status_for_rehydration(upload_id)
