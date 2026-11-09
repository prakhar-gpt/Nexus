"""Users and workspace membership management endpoints with authentication."""

from __future__ import annotations

import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.dependencies import get_current_user, require_workspace_access
from db.models import User, Workspace, WorkspaceMember
from db.session import session_scope

router = APIRouter()


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="analyst", max_length=100)


class WorkspaceMemberAdd(BaseModel):
    user_id: str
    role: Literal["owner", "editor", "viewer"] = "editor"


@router.get("/users/me")
def get_current_user_endpoint(user: User = Depends(get_current_user)):
    """Return authenticated user profile."""
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else "",
    }


@router.get("/users")
def list_users_endpoint(current_user: User = Depends(get_current_user)):
    """List all registered users (authenticated)."""
    with session_scope() as session:
        users = session.execute(select(User).order_by(User.created_at.asc())).scalars().all()
        return [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "created_at": u.created_at.isoformat() if u.created_at else "",
            }
            for u in users
        ]


@router.post("/users")
def create_user_endpoint(body: UserCreate, current_user: User = Depends(get_current_user)):
    """Create or update a user (authenticated)."""
    clean_email = body.email.strip().lower()
    clean_name = body.name.strip()
    clean_role = body.role.strip()
    with session_scope() as session:
        existing = session.execute(
            select(User).where(User.email.ilike(clean_email))
        ).scalar_one_or_none()
        if existing:
            existing.name = clean_name
            existing.role = clean_role
            session.flush()
            user = existing
        else:
            user = User(email=clean_email, name=clean_name, role=clean_role)
            session.add(user)
            session.flush()
        return {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else "",
        }


@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members_endpoint(
    workspace_id: str,
    ws: Workspace = Depends(require_workspace_access),
):
    """List all members of a workspace."""
    try:
        ws_uuid = uuid.UUID(workspace_id)
    except ValueError:
        return []
    with session_scope() as session:
        stmt = (
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == ws_uuid)
            .order_by(WorkspaceMember.joined_at.asc())
        )
        results = session.execute(stmt).all()
        return [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.name,
                "user_role": u.role,
                "workspace_role": wm.role,
                "joined_at": wm.joined_at.isoformat() if wm.joined_at else "",
            }
            for wm, u in results
        ]


@router.post("/workspaces/{workspace_id}/members")
def add_workspace_member_endpoint(
    workspace_id: str,
    body: WorkspaceMemberAdd,
    ws: Workspace = Depends(require_workspace_access),
):
    """Add or update member role in a workspace."""
    try:
        ws_uuid = uuid.UUID(workspace_id)
        user_uuid = uuid.UUID(body.user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID")
    with session_scope() as session:
        member = session.get(WorkspaceMember, (ws_uuid, user_uuid))
        if member:
            member.role = body.role
        else:
            member = WorkspaceMember(workspace_id=ws_uuid, user_id=user_uuid, role=body.role)
            session.add(member)
    return {"ok": True, "workspace_id": workspace_id, "user_id": body.user_id, "role": body.role}
