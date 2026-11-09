"""Opaque token generation and SHA-256 token hashing."""

from __future__ import annotations

import hashlib
import secrets


def generate_session_token() -> str:
    """Generate an opaque random URL-safe token with 256 bits of entropy."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Compute the SHA-256 hex digest of a raw session token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
