"""Bcrypt password hashing, verification, dummy timing defenses, and rehash checks."""

from __future__ import annotations

import bcrypt
from config import settings

# A static valid bcrypt hash (cost 12) used for constant-time comparison when a user does not exist
_DUMMY_BCRYPT_HASH = b"$2b$12$e8u3V9o91l66aYd9t2R3epPqm99b3cQzP9w.E1Z0dM3bHwKkOqU6"
MAX_PASSWORD_BYTES = 72


def hash_password(password: str, rounds: int | None = None) -> str:
    """Hash a plaintext password using bcrypt with explicit 72-byte validation."""
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > MAX_PASSWORD_BYTES:
        raise ValueError("Password exceeds maximum length of 72 bytes.")
    cost = rounds if rounds is not None else settings.BCRYPT_ROUNDS
    salt = bcrypt.gensalt(rounds=cost)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time verification of a plaintext password against a bcrypt hash."""
    pwd_bytes = plain_password.encode("utf-8")
    if len(pwd_bytes) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False


def verify_dummy_password(plain_password: str) -> bool:
    """Perform dummy hash check to prevent timing analysis on non-existent emails."""
    pwd_bytes = plain_password.encode("utf-8")
    if len(pwd_bytes) > MAX_PASSWORD_BYTES:
        pwd_bytes = pwd_bytes[:MAX_PASSWORD_BYTES]
    try:
        bcrypt.checkpw(pwd_bytes, _DUMMY_BCRYPT_HASH)
    except Exception:
        pass
    return False


def needs_rehash(hashed_password: str, target_rounds: int | None = None) -> bool:
    """Determine whether the hash was computed with fewer rounds than the target cost."""
    target = target_rounds if target_rounds is not None else settings.BCRYPT_ROUNDS
    parts = hashed_password.split("$")
    # Expected format: ['', '2b', '12', '...']
    if len(parts) >= 3:
        try:
            current_rounds = int(parts[2])
            return current_rounds < target
        except ValueError:
            return True
    return True
