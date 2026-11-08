"""Workspace and chat routing endpoints."""

from __future__ import annotations

import sys
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from apps.api.schemas import ChatRequest, WorkspaceCreate
from apps.api.services.chat_service import generate_chat_events
from apps.api.services.upload_service import handle_file_upload
from apps.api.services.workspace_service import (
    create_workspace,
    get_workspace_detail,
    get_workspace_meta,
    list_workspaces,
)
from packages.agent.loop import stream as default_stream

router = APIRouter()


def _get_stream_callable():
    main_mod = sys.modules.get("apps.api.main")
    if main_mod and hasattr(main_mod, "stream"):
        return getattr(main_mod, "stream")
    return default_stream


@router.get("/workspaces")
def get_workspaces_endpoint():
    """List all workspaces."""
    return list_workspaces()


@router.post("/workspaces")
def create_workspace_endpoint(body: WorkspaceCreate):
    """Create a new workspace."""
    return create_workspace(body.name)


@router.get("/workspaces/{workspace_id}")
def get_workspace_endpoint(workspace_id: int):
    """Retrieve full data room view for a workspace."""
    return get_workspace_detail(workspace_id)


@router.post("/workspaces/{workspace_id}/uploads")
async def create_upload_endpoint(
    workspace_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a spreadsheet to a workspace and start ingestion."""
    data = await file.read()
    return handle_file_upload(workspace_id, file.filename or "upload.csv", data, background)


@router.post("/workspaces/{workspace_id}/chat")
def chat_endpoint(workspace_id: int, body: ChatRequest):
    """Execute an agent query against a workspace and stream SSE events."""
    if get_workspace_meta(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    stream_func = _get_stream_callable()
    return StreamingResponse(
        generate_chat_events(workspace_id, question, stream_func),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

