"""Authentication domain service: signup, login, lockout defenses, password change, and sessions."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select

from auth.passwords import hash_password, needs_rehash, verify_dummy_password, verify_password
from auth.policy import validate_password_policy
from auth.session_store import (
    create_session,
    list_user_sessions,
    revoke_all_user_sessions,
    revoke_session,
)
from auth.tokens import hash_session_token
from config import settings
from db.models import Session as DbSession, User
from db.session import session_scope

logger = logging.getLogger("nexus.auth")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    """Normalize and validate email address."""
    clean = email.strip().lower()
    if not EMAIL_REGEX.match(clean) or len(clean) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email address format.",
        )
    return clean


def signup_user(
    email: str,
    password: str,
    name: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, User]:
    """Register a new user account and issue an initial session."""
    if not settings.ALLOW_SIGNUP:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account registration is currently closed.",
        )

    clean_email = normalize_email(email)
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Display name is required.",
        )

    try:
        validate_password_policy(password, email=clean_email)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    pwd_hash = hash_password(password)

    with session_scope() as session:
        existing = session.execute(
            select(User).where(User.email.ilike(clean_email))
        ).scalar_one_or_none()
        if existing:
            # Usability disclosure limited strictly to account conflict resolution
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Sign in instead.",
            )

        user = User(
            email=clean_email,
            name=clean_name,
            password_hash=pwd_hash,
            role="analyst",
            is_active=True,
            failed_login_count=0,
            locked_until=None,
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user)
        session.flush()

        raw_token, sess = create_session(session, user.id, user_agent=user_agent, ip=ip)
        logger.info(f"User signed up successfully: user_id={user.id}, ip={ip}")

        user_copy = User(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        return raw_token, user_copy


def login_user(
    email: str,
    password: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, User]:
    """Authenticate credentials with constant-time verification and lockout defense."""
    clean_email = normalize_email(email)
    now = datetime.now(timezone.utc)

    with session_scope() as session:
        user = session.execute(
            select(User).where(User.email.ilike(clean_email))
        ).scalar_one_or_none()

        # Non-existent user: run dummy hash to protect against timing attacks
        if not user:
            verify_dummy_password(password)
            logger.warning(f"Login failed (email not found): email={clean_email}, ip={ip}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email or password is incorrect.",
            )

        # Check account lockout
        if user.locked_until and user.locked_until > now:
            retry_after = int((user.locked_until - now).total_seconds())
            logger.warning(f"Login rejected (locked account): user_id={user.id}, ip={ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account temporarily locked due to failed attempts. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(max(1, retry_after))},
            )

        # Deactivated user
        if not user.is_active:
            verify_dummy_password(password)
            logger.warning(f"Login failed (inactive account): user_id={user.id}, ip={ip}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email or password is incorrect.",
            )

        # Verify password
        is_valid = verify_password(password, user.password_hash or "")
        if not is_valid:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
                retry_secs = settings.LOCKOUT_MINUTES * 60
                logger.warning(f"User account locked out: user_id={user.id}, ip={ip}")
                session.flush()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many failed attempts. Account locked for {settings.LOCKOUT_MINUTES} minutes.",
                    headers={"Retry-After": str(retry_secs)},
                )
            session.flush()
            logger.warning(f"Login failed (wrong password): user_id={user.id}, ip={ip}, failed_count={user.failed_login_count}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email or password is incorrect.",
            )

        # Reset failed login count on success
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now

        # Transparent cost upgrade if needed
        if user.password_hash and needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        raw_token, sess = create_session(session, user.id, user_agent=user_agent, ip=ip)
        logger.info(f"User logged in successfully: user_id={user.id}, ip={ip}")

        user_copy = User(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        return raw_token, user_copy


def logout_user(raw_token: str | None) -> None:
    """Revoke current session by token."""
    if not raw_token:
        return
    token_hash = hash_session_token(raw_token)
    with session_scope() as session:
        sess = session.execute(
            select(DbSession).where(
                DbSession.token_hash == token_hash,
                DbSession.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if sess:
            sess.revoked_at = datetime.now(timezone.utc)
            session.flush()
            logger.info(f"Session revoked on logout: session_id={sess.id}, user_id={sess.user_id}")


def change_user_password(
    user_id: uuid.UUID,
    current_password: str,
    new_password: str,
    current_session_id: uuid.UUID | None = None,
) -> None:
    """Validate current password, verify new password against policy, and update hash while revoking other sessions."""
    with session_scope() as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        if not verify_password(current_password, user.password_hash or ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )

        try:
            validate_password_policy(new_password, email=user.email)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

        user.password_hash = hash_password(new_password)
        # Revoke all other sessions
        revoked_count = revoke_all_user_sessions(session, user.id, except_session_id=current_session_id)
        logger.info(f"Password changed for user_id={user.id}. Revoked {revoked_count} other sessions.")


def list_sessions_for_user(
    user_id: uuid.UUID,
    current_session_id: uuid.UUID | None = None,
) -> list[dict]:
    """List active sessions for a user, marking the current session."""
    with session_scope() as session:
        records = list_user_sessions(session, user_id)
        return [
            {
                "id": str(s.id),
                "created_at": s.created_at.isoformat(),
                "last_seen_at": s.last_seen_at.isoformat(),
                "expires_at": s.expires_at.isoformat(),
                "user_agent": s.user_agent or "Unknown client",
                "ip": s.ip or "Unknown IP",
                "is_current": s.id == current_session_id,
            }
            for s in records
        ]


def revoke_single_session(user_id: uuid.UUID, session_id: uuid.UUID) -> bool:
    """Revoke a specific session owned by the user."""
    with session_scope() as session:
        return revoke_session(session, session_id, user_id)
