"""Workspace and chat routing endpoints."""

from __future__ import annotations

import sys
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from pydantic import BaseModel, Field

class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(default=None, max_length=100)

class ThreadDatasetsUpdate(BaseModel):
    dataset_ids: list[int] = Field(default_factory=list)

from api.services.chat_service import generate_chat_events
from api.services.upload_service import handle_file_upload
from api.services.workspace_service import (
    create_workspace,
    delete_thread,
    delete_workspace,
    get_or_create_thread,
    get_turns,
    get_workspace_detail,
    get_workspace_meta,
    list_threads,
    list_workspace_datasets,
    list_workspaces,
    remove_dataset,
    update_thread_datasets,
)
from ingest.store import execute
from agent import stream as default_stream

router = APIRouter()


def _get_stream_callable():
    main_mod = sys.modules.get("main") or sys.modules.get("api.main")
    if main_mod and hasattr(main_mod, "stream"):
        return getattr(main_mod, "stream")
    return default_stream


@router.get("/workspaces")
def get_workspaces_endpoint():
    """List all active workspaces."""
    return list_workspaces()


@router.post("/workspaces")
def create_workspace_endpoint(body: WorkspaceCreate):
    """Create a new workspace."""
    return create_workspace(body.name)


@router.delete("/workspaces/{workspace_id}")
def delete_workspace_endpoint(workspace_id: int):
    """Delete / archive a workspace."""
    return delete_workspace(workspace_id)


@router.get("/workspaces/{workspace_id}")
def get_workspace_endpoint(workspace_id: int, thread_id: str | None = Query(default=None)):
    """Retrieve full data room view for a workspace, optionally filtered to a thread."""
    return get_workspace_detail(workspace_id, thread_id)


@router.get("/workspaces/{workspace_id}/threads")
def get_threads_endpoint(workspace_id: int):
    """List all chat threads in a workspace."""
    if get_workspace_meta(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return list_threads(workspace_id)


@router.get("/workspaces/{workspace_id}/threads/{thread_id}/turns")
def get_thread_turns_endpoint(workspace_id: int, thread_id: str):
    """Fetch message turns for a specific thread."""
    if get_workspace_meta(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return get_turns(workspace_id, thread_id)


@router.delete("/workspaces/{workspace_id}/threads/{thread_id}")
def delete_thread_endpoint(workspace_id: int, thread_id: str):
    """Delete a conversation thread in a workspace."""
    if get_workspace_meta(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return delete_thread(workspace_id, thread_id)


@router.patch("/workspaces/{workspace_id}/threads/{thread_id}/datasets")
def update_thread_datasets_endpoint(workspace_id: int, thread_id: str, body: ThreadDatasetsUpdate):
    """Update allowed dataset selection for a specific chat thread."""
    if get_workspace_meta(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return update_thread_datasets(workspace_id, thread_id, body.dataset_ids)


@router.get("/workspaces/{workspace_id}/datasets")
def get_datasets_endpoint(workspace_id: int):
    """List all approved datasets for a workspace."""
    if get_workspace_meta(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return list_workspace_datasets(workspace_id)


@router.delete("/workspaces/{workspace_id}/datasets/{dataset_id}")
def delete_dataset_endpoint(workspace_id: int, dataset_id: int):
    """Delete an approved dataset, its catalog entries, quarantine, and references."""
    if get_workspace_meta(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return remove_dataset(workspace_id, dataset_id)


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

    thread_id = (body.thread_id or "default").strip()
    # Resolve thread and allowed dataset IDs strictly on server side
    thread = get_or_create_thread(workspace_id, thread_id)
    allowed_dataset_ids = thread.get("selected_dataset_ids") or []

    # Block send if zero datasets are checked (when custom datasets exist in workspace)
    has_custom = bool(execute(f"SELECT 1 FROM datasets WHERE workspace_id = {int(workspace_id)} LIMIT 1"))
    if has_custom and len(allowed_dataset_ids) == 0:
        raise HTTPException(status_code=400, detail="Select a dataset to ask about")

    stream_func = _get_stream_callable()
    return StreamingResponse(
        generate_chat_events(
            workspace_id,
            question,
            stream_func,
            thread_id=thread_id,
            allowed_dataset_ids=allowed_dataset_ids,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
