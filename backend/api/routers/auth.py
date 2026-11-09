"""Dedicated authentication endpoints: signup, login, logout, me, password change, and sessions."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from api.dependencies import get_current_user
from api.services.auth_service import (
    change_user_password,
    list_sessions_for_user,
    login_user,
    logout_user,
    revoke_single_session,
    signup_user,
)
from config import settings
from db.models import User
from utils import to_uuid

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=10, max_length=72)
    name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=72)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=10, max_length=72)


class UserProfileResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    created_at: str


class SessionInfoResponse(BaseModel):
    id: str
    created_at: str
    last_seen_at: str
    expires_at: str
    user_agent: str
    ip: str
    is_current: bool


def _get_client_ip(request: Request) -> str:
    if settings.TRUSTED_PROXY_HEADERS:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def _set_session_cookie(response: Response, raw_token: str) -> None:
    max_age_seconds = settings.SESSION_EXPIRY_DAYS * 86400
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=max_age_seconds,
        expires=max_age_seconds,
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
    )


@router.post("/signup", response_model=UserProfileResponse)
def signup_endpoint(body: SignupRequest, request: Request, response: Response):
    """Register a new user account with secure session cookie."""
    ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    raw_token, user = signup_user(body.email, body.password, body.name, user_agent=user_agent, ip=ip)
    _set_session_cookie(response, raw_token)
    return UserProfileResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.post("/login", response_model=UserProfileResponse)
def login_endpoint(body: LoginRequest, request: Request, response: Response):
    """Authenticate credentials, lock brute-force attempts, and issue session cookie."""
    ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    raw_token, user = login_user(body.email, body.password, user_agent=user_agent, ip=ip)
    _set_session_cookie(response, raw_token)
    return UserProfileResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.post("/logout")
def logout_endpoint(
    request: Request,
    response: Response,
    nexus_session: str | None = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
):
    """Revoke active session and delete session cookie."""
    token = nexus_session or request.cookies.get(settings.SESSION_COOKIE_NAME)
    logout_user(token)
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
    )
    return {"ok": True}


@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(user: User = Depends(get_current_user)):
    """Return the authenticated user profile."""
    return UserProfileResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.post("/change-password")
def change_password_endpoint(
    body: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Change user password and revoke all other sessions."""
    current_session_id = getattr(request.state, "current_session_id", None)
    change_user_password(user.id, body.current_password, body.new_password, current_session_id)
    return {"ok": True}


@router.get("/sessions", response_model=list[SessionInfoResponse])
def list_user_sessions_endpoint(
    request: Request,
    user: User = Depends(get_current_user),
):
    """List all active sessions for the current user."""
    current_session_id = getattr(request.state, "current_session_id", None)
    records = list_sessions_for_user(user.id, current_session_id)
    return [SessionInfoResponse(**rec) for rec in records]


@router.delete("/sessions/{session_id}")
def revoke_session_endpoint(
    session_id: str,
    user: User = Depends(get_current_user),
):
    """Revoke a specific user session."""
    try:
        sess_uuid = to_uuid(session_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID.")
    revoked = revoke_single_session(user.id, sess_uuid)
    return {"ok": revoked}
