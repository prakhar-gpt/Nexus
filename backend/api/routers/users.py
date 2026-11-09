"""Users, workspace membership, and authentication endpoints."""

from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ingest.store import execute, sql_id, sql_literal

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
    rows = execute(
        f"SELECT id, email, name, role, created_at::text FROM users WHERE lower(email) = {sql_literal(target_email)} LIMIT 1"
    )
    if rows:
        return rows[0]
    # Fallback to first user in system if available
    first_user = execute("SELECT id, email, name, role, created_at::text FROM users ORDER BY created_at ASC LIMIT 1")
    if first_user:
        return first_user[0]
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
    try:
        return execute("SELECT id, email, name, role, created_at::text FROM users ORDER BY created_at ASC")
    except Exception:
        return []


@router.post("/users")
def create_user_endpoint(body: UserCreate):
    """Create a new user."""
    clean_email = body.email.strip().lower()
    clean_name = body.name.strip()
    clean_role = body.role.strip()
    rows = execute(
        f"INSERT INTO users (email, name, role) "
        f"VALUES ({sql_literal(clean_email)}, {sql_literal(clean_name)}, {sql_literal(clean_role)}) "
        f"ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name, role = EXCLUDED.role "
        f"RETURNING id, email, name, role, created_at::text"
    )
    return rows[0]


@router.post("/auth/login")
def login_endpoint(body: LoginRequest):
    """Login or auto-provision user by email."""
    clean_email = body.email.strip().lower()
    clean_name = (body.name or clean_email.split("@")[0].replace(".", " ").title()).strip()
    rows = execute(
        f"SELECT id, email, name, role, created_at::text FROM users WHERE lower(email) = {sql_literal(clean_email)} LIMIT 1"
    )
    if rows:
        return rows[0]
    created = execute(
        f"INSERT INTO users (email, name, role) "
        f"VALUES ({sql_literal(clean_email)}, {sql_literal(clean_name)}, 'Consulting Analyst') "
        f"RETURNING id, email, name, role, created_at::text"
    )
    return created[0]


@router.get("/workspaces/{workspace_id}/members")
def list_workspace_members_endpoint(workspace_id: str):
    """List all members of a workspace."""
    sql = (
        "SELECT u.id, u.email, u.name, u.role AS user_role, wm.role AS workspace_role, wm.joined_at::text "
        "FROM workspace_members wm "
        "JOIN users u ON u.id = wm.user_id "
        f"WHERE wm.workspace_id = {sql_id(workspace_id)} "
        "ORDER BY wm.joined_at ASC"
    )
    try:
        return execute(sql)
    except Exception:
        return []


@router.post("/workspaces/{workspace_id}/members")
def add_workspace_member_endpoint(workspace_id: str, body: WorkspaceMemberAdd):
    """Add or update member role in a workspace."""
    execute(
        f"INSERT INTO workspace_members (workspace_id, user_id, role) "
        f"VALUES ({sql_id(workspace_id)}, {sql_id(body.user_id)}, {sql_literal(body.role)}) "
        f"ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = EXCLUDED.role"
    )
    return {"ok": True, "workspace_id": workspace_id, "user_id": body.user_id, "role": body.role}

