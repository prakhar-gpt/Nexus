"""API routers package."""

from api.routers.auth import router as auth_router
from api.routers.provenance import router as provenance_router
from api.routers.runs import router as runs_router
from api.routers.uploads import router as uploads_router
from api.routers.users import router as users_router
from api.routers.workspaces import router as workspaces_router

__all__ = [
    "auth_router",
    "workspaces_router",
    "uploads_router",
    "runs_router",
    "provenance_router",
    "users_router",
]


