"""
API Key Authentication Middleware — protects all /api/* endpoints.

Supports two auth methods:
1. X-API-Key header (preferred for server-to-server)
2. Authorization: Bearer <key> header (standard for clients)

The API key is set via the DASHBOARD_API_KEY environment variable.
In development, auth can be disabled by setting REQUIRE_AUTH=false.
"""

from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

import structlog
import hashlib
import hmac
import time

logger = structlog.get_logger()

# Security scheme definitions for OpenAPI docs
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

# Paths that never require auth
PUBLIC_PATHS = frozenset({
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
})

# Paths that start with these prefixes are public
PUBLIC_PREFIXES = (
    "/assets/",
    "/favicon",
)


def _constant_time_compare(a: str, b: str) -> bool:
    """Timing-safe string comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces API key authentication on /api/* routes."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        # Skip auth for non-API paths (dashboard SPA)
        if not path.startswith("/api/"):
            return await call_next(request)

        # Skip auth in development if REQUIRE_AUTH is false
        if not settings.require_auth:
            return await call_next(request)

        # Check if API key is configured
        if not settings.dashboard_api_key:
            logger.warning("auth_no_api_key_configured", path=path)
            return JSONResponse(
                status_code=500,
                content={"detail": "Server authentication not configured"},
            )

        # Try X-API-Key header first
        api_key = request.headers.get("X-API-Key")

        # Fall back to Authorization: Bearer <key>
        if not api_key:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:]

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing API key. Provide X-API-Key header or Authorization: Bearer <key>"},
            )

        if not _constant_time_compare(api_key, settings.dashboard_api_key):
            logger.warning(
                "auth_failed",
                path=path,
                ip=request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid API key"},
            )

        return await call_next(request)
