"""Application and authentication settings loaded from environment with safe defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int(key: str, default: int) -> int:
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # Security & Hashing
    BCRYPT_ROUNDS: int = field(default_factory=lambda: _get_int("BCRYPT_ROUNDS", 12))

    # Sessions & Cookies
    SESSION_COOKIE_NAME: str = field(default_factory=lambda: os.environ.get("SESSION_COOKIE_NAME", "nexus_session"))
    SESSION_EXPIRY_DAYS: int = field(default_factory=lambda: _get_int("SESSION_EXPIRY_DAYS", 14))
    SESSION_IDLE_EXPIRY_DAYS: int = field(default_factory=lambda: _get_int("SESSION_IDLE_EXPIRY_DAYS", 7))
    SESSION_TOUCH_INTERVAL_SECONDS: int = field(default_factory=lambda: _get_int("SESSION_TOUCH_INTERVAL_SECONDS", 300))
    COOKIE_SECURE: bool = field(default_factory=lambda: _get_bool("COOKIE_SECURE", False))
    COOKIE_SAMESITE: str = field(default_factory=lambda: os.environ.get("COOKIE_SAMESITE", "lax").lower())

    # Registration & Lockout
    ALLOW_SIGNUP: bool = field(default_factory=lambda: _get_bool("ALLOW_SIGNUP", True))
    MAX_FAILED_LOGIN_ATTEMPTS: int = field(default_factory=lambda: _get_int("MAX_FAILED_LOGIN_ATTEMPTS", 5))
    LOCKOUT_MINUTES: int = field(default_factory=lambda: _get_int("LOCKOUT_MINUTES", 15))

    # Rate Limiting
    TRUSTED_PROXY_HEADERS: bool = field(default_factory=lambda: _get_bool("TRUSTED_PROXY_HEADERS", False))
    RATE_LIMIT_LOGIN_PER_MIN_IP: int = field(default_factory=lambda: _get_int("RATE_LIMIT_LOGIN_PER_MIN_IP", 5))
    RATE_LIMIT_LOGIN_PER_HOUR_IP: int = field(default_factory=lambda: _get_int("RATE_LIMIT_LOGIN_PER_HOUR_IP", 20))
    RATE_LIMIT_SIGNUP_PER_HOUR_IP: int = field(default_factory=lambda: _get_int("RATE_LIMIT_SIGNUP_PER_HOUR_IP", 5))
    RATE_LIMIT_CHANGE_PASSWORD_PER_HOUR_USER: int = field(default_factory=lambda: _get_int("RATE_LIMIT_CHANGE_PASSWORD_PER_HOUR_USER", 5))
    RATE_LIMIT_CHAT_PER_MIN_USER: int = field(default_factory=lambda: _get_int("RATE_LIMIT_CHAT_PER_MIN_USER", 30))
    RATE_LIMIT_UPLOAD_PER_HOUR_USER: int = field(default_factory=lambda: _get_int("RATE_LIMIT_UPLOAD_PER_HOUR_USER", 10))
    RATE_LIMIT_API_PER_MIN_USER: int = field(default_factory=lambda: _get_int("RATE_LIMIT_API_PER_MIN_USER", 120))
    MAX_CONCURRENT_SSE_PER_USER: int = field(default_factory=lambda: _get_int("MAX_CONCURRENT_SSE_PER_USER", 5))

    # CORS
    CORS_ORIGINS: list[str] = field(default_factory=lambda: [
        origin.strip() for origin in os.environ.get(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",") if origin.strip()
    ])

    # Ingestion & Upload Constraints
    UPLOAD_MAX_BYTES: int = field(default_factory=lambda: _get_int("UPLOAD_MAX_BYTES", 50 * 1024 * 1024))
    UPLOAD_MAX_ROWS: int = field(default_factory=lambda: _get_int("UPLOAD_MAX_ROWS", 600_000))
    UPLOAD_MAX_COLUMNS: int = field(default_factory=lambda: _get_int("UPLOAD_MAX_COLUMNS", 64))
    UPLOAD_HEADER_SCAN_ROWS: int = field(default_factory=lambda: _get_int("UPLOAD_HEADER_SCAN_ROWS", 20))
    UPLOAD_MAX_REGENERATE_RUNS: int = field(default_factory=lambda: _get_int("UPLOAD_MAX_REGENERATE_RUNS", 3))
    UPLOAD_DIR: str = field(default_factory=lambda: os.environ.get("UPLOAD_DIR", "datasets/uploads"))
    UPLOAD_ALLOWED_EXTENSIONS: set[str] = field(default_factory=lambda: {
        ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
        for ext in os.environ.get("UPLOAD_ALLOWED_EXTENSIONS", ".csv,.xlsx").split(",")
        if ext.strip()
    })


settings = Settings()
