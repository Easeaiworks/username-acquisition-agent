"""
API Key Authentication Middleware — protects all /api/* endpoints.

Supports two auth methods:
1. X-API-Key header (preferred for server-to-server)
2. Authorization: Bearer <key> header (standard for clients)

Authentication is checked in two stages:
1. Constant-time comparison against the legacy DASHBOARD_API_KEY env var
   (treated as super_admin with user_id=None for backward compatibility).
2. Database lookup in admin_users table for per-user API keys with RBAC.

The authenticated user's role and identity are set on request.state:
  - request.state.user_id    (str | None)
  - request.state.user_role  ("super_admin" | "admin" | "viewer")
  - request.state.user_email (str | None)
  - request.state.user_name  (str | None)
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
from datetime import datetime, timezone

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
    "/api/auth/login",
})

# Paths that start with these prefixes are public
PUBLIC_PREFIXES = (
    "/assets/",
    "/favicon",
)


def _constant_time_compare(a: str, b: str) -> bool:
    """Timing-safe string comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _set_request_state(request: Request, user_id, role, email=None, name=None):
    """Populate request.state with authenticated user info."""
    request.state.user_id = user_id
    request.state.user_role = role
    request.state.user_email = email
    request.state.user_name = name


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
            # In dev mode, default to super_admin so admin endpoints work
            _set_request_state(request, user_id=None, role="super_admin")
            return await call_next(request)

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

        # --- Stage 1: Check against legacy DASHBOARD_API_KEY (constant-time) ---
        if settings.dashboard_api_key and _constant_time_compare(api_key, settings.dashboard_api_key):
            _set_request_state(
                request,
                user_id=None,
                role="super_admin",
                email=None,
                name="Legacy Admin",
            )
            return await call_next(request)

        # --- Stage 2: Look up per-user API key in admin_users table ---
        try:
            from app.database import get_service_client
            db = get_service_client()

            result = (
                db.table("admin_users")
                .select("id, role, is_active, email, name")
                .eq("api_key", api_key)
                .execute()
            )

            if result.data:
                user = result.data[0]

                if not user.get("is_active", False):
                    logger.warning(
                        "auth_inactive_user",
                        user_id=user["id"],
                        path=path,
                    )
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Account is deactivated"},
                    )

                _set_request_state(
                    request,
                    user_id=user["id"],
                    role=user["role"],
                    email=user.get("email"),
                    name=user.get("name"),
                )

                # Update last_login_at (inline, non-critical)
                try:
                    db.table("admin_users").update({
                        "last_login_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", user["id"]).execute()
                except Exception:
                    pass  # Non-critical — don't fail the request

                return await call_next(request)

        except Exception as e:
            logger.error("auth_db_lookup_error", error=str(e), path=path)
            # Fall through to rejection below

        # --- Neither matched — reject ---
        logger.warning(
            "auth_failed",
            path=path,
            ip=request.client.host if request.client else "unknown",
        )
        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid API key"},
        )
