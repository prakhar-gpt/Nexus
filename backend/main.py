"""Nexus FastAPI application entry point.

Assembles routers, security middleware, and application lifecycle.
Run with: uvicorn main:app --reload
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Ensure backend root is on sys.path
_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from api.middleware import CSRFMiddleware, RateLimitMiddleware
from api.routers import auth_router, provenance_router, runs_router, uploads_router, users_router, workspaces_router
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
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run database migrations on startup to guarantee schema alignment."""
    try:
        from db.migrate import run_migrations
        run_migrations()
    except Exception as exc:
        import logging
        logging.getLogger("nexus.main").error(f"Startup migration check: {exc}")
    yield


app = FastAPI(
    title="Nexus",
    description="Retail Data Room Copilot with guarded SQL and deterministic number checking.",
    version="1.0.0",
    lifespan=lifespan,
)

# 1. CORS with credentials enabled for session cookies
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Rate limiting & request size bounds
app.add_middleware(RateLimitMiddleware)

# 3. CSRF state-changing header & origin protection
app.add_middleware(CSRFMiddleware)

# Routers
app.include_router(auth_router)
app.include_router(workspaces_router)
app.include_router(uploads_router)
app.include_router(runs_router)
app.include_router(provenance_router)
app.include_router(users_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/ping", methods=["GET", "POST", "HEAD"])
async def ping_endpoint(request: Request) -> dict[str, str]:
    """Lightweight keep-alive ping endpoint to prevent cold start spin-down."""
    return {"status": "ok", "ping": "pong"}

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
