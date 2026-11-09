"""CSRF protection middleware for cookie-authenticated state-changing requests."""

from __future__ import annotations

import logging
from urllib.parse import urlparse
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from config import settings

logger = logging.getLogger("nexus.csrf")
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class CSRFMiddleware(BaseHTTPMiddleware):
    """Enforce custom header and origin validation on state-changing requests."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Exempt safe read methods
        if request.method in SAFE_METHODS:
            return await call_next(request)

        # Exempt health check endpoints if any
        if request.url.path in ("/health", "/api/health"):
            return await call_next(request)

        # 1. Validate Origin header if present against allowed CORS origins
        origin = request.headers.get("origin")
        if origin:
            parsed_origin = origin.rstrip("/")
            allowed = {o.rstrip("/") for o in settings.CORS_ORIGINS}
            # Allow origin if matched in configured CORS origins
            if parsed_origin not in allowed:
                logger.warning(f"CSRF rejected: forbidden origin '{origin}' from IP {request.client.host if request.client else 'unknown'}")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Cross-origin request rejected."},
                )

        # 2. Require custom header (e.g. X-Requested-With) on state-changing requests
        requested_with = request.headers.get("x-requested-with")
        if not requested_with:
            logger.warning(f"CSRF rejected: missing X-Requested-With header on {request.method} {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Missing required state-changing request header."},
            )

        return await call_next(request)
