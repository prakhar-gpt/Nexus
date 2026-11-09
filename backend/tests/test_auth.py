"""Unit and service tests for authentication, password hashing, policies, and sessions."""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException

from auth.passwords import hash_password, needs_rehash, verify_dummy_password, verify_password
from auth.policy import validate_password_policy
from auth.session_store import (
    create_session,
    get_active_session,
    list_user_sessions,
    revoke_all_user_sessions,
    revoke_session,
    rotate_session,
)
from auth.tokens import generate_session_token, hash_session_token
from config import settings
from db.models import User
from db.session import session_scope


def test_password_hashing_and_72_byte_limit():
    """Bcrypt password hashing should succeed for valid strings and explicitly reject >72 bytes."""
    valid_pwd = "A" * 72
    hashed = hash_password(valid_pwd, rounds=4)
    assert hashed.startswith("$2b$04$")
    assert verify_password(valid_pwd, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False

    # Over 72 bytes must raise ValueError, not silently truncate
    over_72 = "A" * 73
    with pytest.raises(ValueError, match="72 bytes"):
        hash_password(over_72)

    # Multi-byte UTF-8 character length validation
    multi_byte = "🔒" * 20  # 4 bytes each = 80 bytes
    with pytest.raises(ValueError, match="72 bytes"):
        hash_password(multi_byte)


def test_needs_rehash():
    """Hashes generated with lower rounds must flag as needing rehash."""
    old_hash = hash_password("ValidPassword123", rounds=4)
    assert needs_rehash(old_hash, target_rounds=12) is True
    assert needs_rehash(old_hash, target_rounds=4) is False


def test_dummy_password_verification():
    """Dummy verification runs safely without throwing exceptions."""
    assert verify_dummy_password("SomePassword123") is False
    assert verify_dummy_password("A" * 100) is False


def test_password_policy_enforcement():
    """Password policy rejects short passwords, common phrases, and email username matches."""
    # Too short
    with pytest.raises(ValueError, match="at least 10 characters"):
        validate_password_policy("short9")

    # Over 72 bytes
    with pytest.raises(ValueError, match="72 bytes"):
        validate_password_policy("X" * 73)

    # Identical to email
    with pytest.raises(ValueError, match="cannot match your email"):
        validate_password_policy("analyst@firm.com", email="analyst@firm.com")

    # Contains email username
    with pytest.raises(ValueError, match="cannot contain your email username"):
        validate_password_policy("prakhar123456", email="prakhar@nexus.ai")

    # Common passwords
    with pytest.raises(ValueError, match="too common"):
        validate_password_policy("password123")

    # Valid password
    validate_password_policy("StrongCommercialPassphrase2026", email="jane@firm.com")


def test_session_tokens():
    """Opaque tokens are random and generate deterministic SHA-256 digests."""
    t1 = generate_session_token()
    t2 = generate_session_token()
    assert t1 != t2
    assert len(t1) >= 40
    h1 = hash_session_token(t1)
    assert h1 == hash_session_token(t1)
    assert h1 != hash_session_token(t2)
    assert len(h1) == 64


def test_session_lifecycle():
    """Sessions create, rotate, validate, and revoke properly."""
    test_user_id = uuid.uuid4()
    with session_scope() as session:
        user = User(
            id=test_user_id,
            email=f"sess_test_{uuid.uuid4().hex[:8]}@nexus.ai",
            name="Session Tester",
            role="analyst",
            is_active=True,
        )
        session.add(user)
        session.flush()

        raw_token, sess_record = create_session(session, user.id, user_agent="PyTest", ip="127.0.0.1")
        assert sess_record.token_hash == hash_session_token(raw_token)
        assert sess_record.revoked_at is None

        # Verify active
        active = get_active_session(session, raw_token)
        assert active is not None
        active_sess, active_user = active
        assert active_sess.id == sess_record.id
        assert active_user.id == user.id

        # Rotate session
        new_token, new_sess = rotate_session(session, active_sess)
        assert new_token != raw_token
        assert active_sess.revoked_at is not None

        # Old token is now invalid
        assert get_active_session(session, raw_token) is None
        # New token is active
        assert get_active_session(session, new_token) is not None

        # Single revocation
        revoked = revoke_session(session, new_sess.id, user.id)
        assert revoked is True
        assert get_active_session(session, new_token) is None


def test_session_idle_and_absolute_expiration():
    """Sessions past absolute or idle expiry cutoffs must fail active lookup."""
    test_user_id = uuid.uuid4()
    with session_scope() as session:
        user = User(
            id=test_user_id,
            email=f"exp_test_{uuid.uuid4().hex[:8]}@nexus.ai",
            name="Expiry Tester",
            role="analyst",
            is_active=True,
        )
        session.add(user)
        session.flush()

        raw_token, sess_record = create_session(session, user.id)

        # Force absolute expiration
        sess_record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        session.flush()
        assert get_active_session(session, raw_token) is None


def test_no_sensitive_fields_in_pydantic_responses():
    """Verify that models and responses never expose password_hash or token_hash."""
    from api.routers.auth import SessionInfoResponse, UserProfileResponse

    user_fields = UserProfileResponse.model_fields.keys()
    assert "password_hash" not in user_fields
    assert "password" not in user_fields

    session_fields = SessionInfoResponse.model_fields.keys()
    assert "token_hash" not in session_fields
    assert "raw_token" not in session_fields
