"""Nexus FastAPI application entry point.

Assembles routers, middleware, and application lifecycle.
Run with: uvicorn main:app --reload
"""

from __future__ import annotations

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure backend root is on sys.path
_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from api.routers import runs_router, uploads_router, users_router, workspaces_router
from api.services.chat_service import format_sse as _sse, save_run as _save_run
from api.services.upload_service import PROGRESS
from api.services.workspace_service import (
    HEALTH_SQL,
    get_health as _health,
    get_mappings as _mappings,
    get_turns as _turns,
    get_workspace_meta as _workspace,
)
from agent import stream

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
app.include_router(users_router)

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
