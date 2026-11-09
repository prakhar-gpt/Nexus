"""Users, workspace membership, and authentication endpoints using SQLAlchemy ORM."""

from __future__ import annotations

import uuid
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from db.models import User, WorkspaceMember
from db.session import session_scope

router = APIRouter()


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="Consulting Analyst", max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    name: str | None = Field(default=None, max_length=255)


class WorkspaceMemberAdd(BaseModel):
    user_id: str
    role: Literal["owner", "editor", "viewer"] = "editor"


@router.get("/users/me")
def get_current_user_endpoint(email: str | None = Query(default=None)):
    """Return current authenticated user profile, defaulting to seeded analyst."""
    target_email = (email or "prakhar@nexus.ai").strip().lower()
    with session_scope() as session:
        user = session.execute(
            select(User).where(User.email.ilike(target_email))
        ).scalar_one_or_none()
        if user:
            return {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "created_at": user.created_at.isoformat() if user.created_at else "",
            }
        # Fallback to first user in system if available
        first_user = session.execute(
            select(User).order_by(User.created_at.asc())
        ).scalars().first()
        if first_user:
            return {
                "id": str(first_user.id),
                "email": first_user.email,
                "name": first_user.name,
                "role": first_user.role,
                "created_at": first_user.created_at.isoformat() if first_user.created_at else "",
            }
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": target_email,
        "name": "Prakhar Gupta",
        "role": "Consulting Analyst",
        "created_at": "",
    }


@router.get("/users")
def list_users_endpoint():
    """List all registered users."""
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
def create_user_endpoint(body: UserCreate):
    """Create a new user or update role/name if exists."""
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


@router.post("/auth/login")
def login_endpoint(body: LoginRequest):
    """Login or auto-provision user by email."""
    clean_email = body.email.strip().lower()
    clean_name = (body.name or clean_email.split("@")[0].replace(".", " ").title()).strip()
    with session_scope() as session:
        user = session.execute(
            select(User).where(User.email.ilike(clean_email))
        ).scalar_one_or_none()
        if not user:
            user = User(email=clean_email, name=clean_name, role="Consulting Analyst")
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
def list_workspace_members_endpoint(workspace_id: str):
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
def add_workspace_member_endpoint(workspace_id: str, body: WorkspaceMemberAdd):
    """Add or update member role in a workspace."""
    try:
        ws_uuid = uuid.UUID(workspace_id)
        user_uuid = uuid.UUID(body.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    with session_scope() as session:
        member = session.get(WorkspaceMember, (ws_uuid, user_uuid))
        if member:
            member.role = body.role
        else:
            member = WorkspaceMember(workspace_id=ws_uuid, user_id=user_uuid, role=body.role)
            session.add(member)
    return {"ok": True, "workspace_id": workspace_id, "user_id": body.user_id, "role": body.role}
