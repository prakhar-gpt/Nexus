"""Nexus FastAPI application entry point.

Assembles routers, middleware, and application lifecycle.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import eval_router, runs_router, uploads_router, workspaces_router
from apps.api.services.chat_service import save_run as _save_run
from apps.api.services.upload_service import PROGRESS
from apps.api.services.workspace_service import (
    HEALTH_SQL,
    get_health as _health,
    get_mappings as _mappings,
    get_turns as _turns,
    get_workspace_meta as _workspace,
)
from apps.api.sse import format_sse as _sse
from packages.agent.loop import stream

app = FastAPI(
    title="Nexus",
    description="Retail Data Room Copilot with guarded SQL and deterministic number checking.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workspaces_router)
app.include_router(uploads_router)
app.include_router(runs_router)
app.include_router(eval_router)

__all__ = [
    "app",
    "stream",
    "PROGRESS",
    "HEALTH_SQL",
    "_workspace",
    "_mappings",
    "_health",
    "_turns",
    "_sse",
    "_save_run",
]
