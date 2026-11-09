"""Database operations for server-side session lifecycle: creation, validation, rotation, and revocation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.orm import Session as OrmSession

from auth.tokens import generate_session_token, hash_session_token
from config import settings
from db.models import Session, User


def create_session(
    db_session: OrmSession,
    user_id: uuid.UUID,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, Session]:
    """Create a new server-side session, returning (raw_token, session_record)."""
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.SESSION_EXPIRY_DAYS)

    record = Session(
        user_id=user_id,
        token_hash=token_hash,
        created_at=now,
        last_seen_at=now,
        expires_at=expires_at,
        revoked_at=None,
        user_agent=user_agent[:500] if user_agent else None,
        ip=ip[:100] if ip else None,
    )
    db_session.add(record)
    db_session.flush()
    return raw_token, record


def get_active_session(
    db_session: OrmSession,
    raw_token: str,
) -> tuple[Session, User] | None:
    """Validate raw token against stored hashed sessions and verify active bounds.
    
    Checks absolute expiry, idle expiry, revocation, and user status.
    Throttles last_seen_at updates.
    """
    token_hash = hash_session_token(raw_token)
    stmt = (
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(
            Session.token_hash == token_hash,
            Session.revoked_at.is_(None),
        )
    )
    result = db_session.execute(stmt).first()
    if not result:
        return None

    sess, user = result
    now = datetime.now(timezone.utc)

    # 1. Absolute expiration check
    if sess.expires_at <= now:
        sess.revoked_at = now
        db_session.flush()
        return None

    # 2. Idle expiration check
    idle_cutoff = now - timedelta(days=settings.SESSION_IDLE_EXPIRY_DAYS)
    if sess.last_seen_at <= idle_cutoff:
        sess.revoked_at = now
        db_session.flush()
        return None

    # 3. User active check
    if not user.is_active:
        sess.revoked_at = now
        db_session.flush()
        return None

    # 4. Throttled touch of last_seen_at
    touch_delta = timedelta(seconds=settings.SESSION_TOUCH_INTERVAL_SECONDS)
    if (now - sess.last_seen_at) >= touch_delta:
        sess.last_seen_at = now
        db_session.flush()

    return sess, user


def rotate_session(
    db_session: OrmSession,
    old_session: Session,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, Session]:
    """Revoke existing session and issue a newly generated session."""
    now = datetime.now(timezone.utc)
    old_session.revoked_at = now
    db_session.flush()
    return create_session(
        db_session,
        user_id=old_session.user_id,
        user_agent=user_agent or old_session.user_agent,
        ip=ip or old_session.ip,
    )


def revoke_session(
    db_session: OrmSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """Revoke a specific session belonging to the user."""
    stmt = select(Session).where(
        Session.id == session_id,
        Session.user_id == user_id,
        Session.revoked_at.is_(None),
    )
    record = db_session.execute(stmt).scalar_one_or_none()
    if record:
        record.revoked_at = datetime.now(timezone.utc)
        db_session.flush()
        return True
    return False


def revoke_all_user_sessions(
    db_session: OrmSession,
    user_id: uuid.UUID,
    except_session_id: uuid.UUID | None = None,
) -> int:
    """Revoke all sessions for a user, optionally exempting the current active session."""
    now = datetime.now(timezone.utc)
    query = (
        update(Session)
        .where(
            Session.user_id == user_id,
            Session.revoked_at.is_(None),
        )
    )
    if except_session_id is not None:
        query = query.where(Session.id != except_session_id)
    query = query.values(revoked_at=now)
    result = db_session.execute(query)
    db_session.flush()
    return result.rowcount


def list_user_sessions(
    db_session: OrmSession,
    user_id: uuid.UUID,
) -> list[Session]:
    """List all non-revoked, unexpired sessions for a user."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(Session)
        .where(
            Session.user_id == user_id,
            Session.revoked_at.is_(None),
            Session.expires_at > now,
        )
        .order_by(Session.last_seen_at.desc())
    )
    return list(db_session.execute(stmt).scalars().all())
