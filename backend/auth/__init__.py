"""Authentication, password management, and session lifecycle package."""

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

__all__ = [
    "hash_password",
    "verify_password",
    "verify_dummy_password",
    "needs_rehash",
    "validate_password_policy",
    "generate_session_token",
    "hash_session_token",
    "create_session",
    "get_active_session",
    "rotate_session",
    "revoke_session",
    "revoke_all_user_sessions",
    "list_user_sessions",
]
