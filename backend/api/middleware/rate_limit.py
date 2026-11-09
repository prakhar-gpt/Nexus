"""Testable in-process sliding-window rate limiter with bounded memory and pluggable backend."""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from auth.tokens import hash_session_token
from config import settings

logger = logging.getLogger("nexus.ratelimit")


@dataclass(frozen=True)
class RateLimitRule:
    max_requests: int
    window_seconds: int


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after_seconds: int = 0
    remaining: int = 0


class RateLimiterBackend(Protocol):
    def check(self, key: str, rule: RateLimitRule) -> Decision:
        ...


class InMemorySlidingWindowLimiter:
    """Thread-safe sliding-window rate limiter with bounded memory and idle key eviction."""

    def __init__(self, max_keys: int = 10_000) -> None:
        self._max_keys = max_keys
        self._store: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_eviction = time.monotonic()

    def check(self, key: str, rule: RateLimitRule) -> Decision:
        now = time.monotonic()
        cutoff = now - rule.window_seconds

        with self._lock:
            # Bounded memory: periodic sweep every 60 seconds or when key threshold reached
            if len(self._store) >= self._max_keys or (now - self._last_eviction) > 60:
                self._evict_idle_keys(cutoff)

            timestamps = self._store.get(key)
            if timestamps is None:
                timestamps = deque()
                self._store[key] = timestamps

            # Evict timestamps outside current window
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= rule.max_requests:
                oldest = timestamps[0]
                retry_after = max(1, int(rule.window_seconds - (now - oldest)))
                return Decision(allowed=False, retry_after_seconds=retry_after, remaining=0)

            timestamps.append(now)
            remaining = rule.max_requests - len(timestamps)
            return Decision(allowed=True, retry_after_seconds=0, remaining=remaining)

    def _evict_idle_keys(self, global_cutoff: float) -> None:
        self._last_eviction = time.monotonic()
        to_delete = [
            k for k, dq in self._store.items()
            if not dq or dq[-1] <= global_cutoff
        ]
        for k in to_delete:
            del self._store[k]
        # Hard cap: if still too large, drop oldest entries
        if len(self._store) > self._max_keys:
            sorted_keys = sorted(self._store.keys(), key=lambda k: self._store[k][-1] if self._store[k] else 0)
            excess = len(self._store) - self._max_keys
            for k in sorted_keys[:excess]:
                del self._store[k]


# Singleton default limiter instance
global_rate_limiter = InMemorySlidingWindowLimiter()

# Config rules
LOGIN_MIN_RULE = RateLimitRule(max_requests=settings.RATE_LIMIT_LOGIN_PER_MIN_IP, window_seconds=60)
LOGIN_HOUR_RULE = RateLimitRule(max_requests=settings.RATE_LIMIT_LOGIN_PER_HOUR_IP, window_seconds=3600)
SIGNUP_RULE = RateLimitRule(max_requests=settings.RATE_LIMIT_SIGNUP_PER_HOUR_IP, window_seconds=3600)
CHANGE_PASSWORD_RULE = RateLimitRule(max_requests=settings.RATE_LIMIT_CHANGE_PASSWORD_PER_HOUR_USER, window_seconds=3600)
CHAT_RULE = RateLimitRule(max_requests=settings.RATE_LIMIT_CHAT_PER_MIN_USER, window_seconds=60)
UPLOAD_RULE = RateLimitRule(max_requests=settings.RATE_LIMIT_UPLOAD_PER_HOUR_USER, window_seconds=3600)
GENERAL_API_RULE = RateLimitRule(max_requests=settings.RATE_LIMIT_API_PER_MIN_USER, window_seconds=60)


def extract_client_ip(request: Request) -> str:
    if settings.TRUSTED_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def extract_client_key(request: Request) -> str:
    """Return user-scoped key if session exists, else IP key."""
    cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if cookie:
        return f"usr:{hash_session_token(cookie)}"
    return f"ip:{extract_client_ip(request)}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce rate limits per endpoint category and protect auth payload size."""

    def __init__(self, app, limiter: RateLimiterBackend | None = None) -> None:
        super().__init__(app)
        self.limiter = limiter or global_rate_limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # 1. Exempt health checks
        if path in ("/health", "/api/health", "/docs", "/openapi.json"):
            return await call_next(request)

        # 2. Limit request body size for auth routes (max 16KB)
        if path.startswith("/auth/"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > 16384:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": "Request payload exceeds allowed limit of 16KB."},
                )

        ip = extract_client_ip(request)
        key = extract_client_key(request)

        # 3. Apply route-specific rate limits
        decisions: list[Decision] = []

        if path == "/auth/login" and request.method == "POST":
            decisions.append(self.limiter.check(f"login:min:{ip}", LOGIN_MIN_RULE))
            decisions.append(self.limiter.check(f"login:hour:{ip}", LOGIN_HOUR_RULE))
        elif path == "/auth/signup" and request.method == "POST":
            decisions.append(self.limiter.check(f"signup:{ip}", SIGNUP_RULE))
        elif path == "/auth/change-password" and request.method == "POST":
            decisions.append(self.limiter.check(f"chpwd:{key}", CHANGE_PASSWORD_RULE))
        elif "/chat" in path and request.method == "POST":
            decisions.append(self.limiter.check(f"chat:{key}", CHAT_RULE))
        elif "/uploads" in path and request.method == "POST":
            decisions.append(self.limiter.check(f"upload:{key}", UPLOAD_RULE))
        else:
            decisions.append(self.limiter.check(f"gen:{key}", GENERAL_API_RULE))

        # Check for rejection
        for decision in decisions:
            if not decision.allowed:
                retry_after = decision.retry_after_seconds
                logger.warning(
                    f"Rate limit hit: key={key}, path={path}, method={request.method}, retry_after={retry_after}"
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={"Retry-After": str(retry_after)},
                    content={"detail": f"Too many attempts. Try again in {retry_after} seconds."},
                )

        return await call_next(request)
