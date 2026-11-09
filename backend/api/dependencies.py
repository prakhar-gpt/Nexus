"""FastAPI dependencies for user authentication and workspace authorization."""

from __future__ import annotations

import logging
import uuid
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import or_, select

from auth.session_store import get_active_session
from config import settings
from db.models import Run, Session as DbSession, Upload, User, Workspace, WorkspaceMember
from db.session import session_scope
from utils import to_uuid

logger = logging.getLogger(__name__)


def get_current_user(
    request: Request,
    nexus_session: str | None = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
    authorization: str | None = Header(default=None),
) -> User:
    """Extract and validate session token from HttpOnly cookie or Authorization header.
    
    Raises 401 with generic message on missing, expired, or invalid session.
    """
    token = nexus_session
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    if not token:
        token = (
            request.query_params.get("token")
            or request.query_params.get("session")
            or request.query_params.get("access_token")
        )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    with session_scope() as session:
        active = get_active_session(session, token)
        if not active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session",
            )
        db_session, user = active
        # Detach/copy essential fields so user object is usable outside session scope
        user_copy = User(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        request.state.current_user = user_copy
        request.state.current_session_id = db_session.id
        return user_copy


def require_workspace_access(
    workspace_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Workspace:
    """Enforce workspace ownership or explicit membership.
    
    Returns 404 on nonexistent workspace or unauthorized access to prevent existence probing.
    """
    try:
        ws_uuid = to_uuid(workspace_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    with session_scope() as session:
        # Check ownership or membership
        stmt = (
            select(Workspace)
            .outerjoin(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(
                Workspace.id == ws_uuid,
                or_(
                    Workspace.owner_id == current_user.id,
                    WorkspaceMember.user_id == current_user.id,
                ),
            )
        )
        ws = session.execute(stmt).scalar_one_or_none()
        if not ws:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

        # Detached copy
        ws_copy = Workspace(
            id=ws.id,
            name=ws.name,
            owner_id=ws.owner_id,
            created_at=ws.created_at,
        )
        request.state.workspace = ws_copy
        return ws_copy


def require_upload_access(
    upload_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Upload:
    """Validate user has access to the workspace that owns the upload."""
    try:
        up_uuid = to_uuid(upload_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")

    with session_scope() as session:
        up = session.get(Upload, up_uuid)
        if not up:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
        ws_id = up.workspace_id

    # Enforce workspace access check
    require_workspace_access(str(ws_id), request, current_user)
    return up


def require_run_access(
    run_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Run:
    """Validate user has access to the workspace that owns the execution run."""
    try:
        run_uuid = to_uuid(run_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    with session_scope() as session:
        run_obj = session.get(Run, run_uuid)
        if not run_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
        ws_id = run_obj.workspace_id

    if ws_id:
        require_workspace_access(str(ws_id), request, current_user)
    return run_obj
