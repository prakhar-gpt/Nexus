"""API routers package."""

from api.routers.eval import router as eval_router
from api.routers.runs import router as runs_router
from api.routers.uploads import router as uploads_router
from api.routers.users import router as users_router
from api.routers.workspaces import router as workspaces_router

__all__ = [
    "workspaces_router",
    "uploads_router",
    "runs_router",
    "eval_router",
    "users_router",
]

