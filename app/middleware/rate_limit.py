"""
HTTP Rate Limiting Middleware — prevents abuse of API endpoints.

Uses a simple in-memory sliding window counter per IP.
For production scale, swap to Redis-backed limiter.

Default limits:
- General API: 60 requests/minute
- Mutation endpoints (POST/PUT/DELETE): 20 requests/minute
- Background jobs (auto-run, generate): 5 requests/minute
"""

import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

import structlog

logger = structlog.get_logger()

# Endpoints with tighter limits (expensive operations)
STRICT_PATHS = frozenset({
    "/api/outreach/auto-run",
    "/api/outreach/followups",
    "/api/enrichment/run",
    "/api/scoring/run",
    "/api/reports/generate",
})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window rate limiter per client IP."""

    def __init__(self, app, general_limit: int = 60, mutation_limit: int = 20, strict_limit: int = 5, window: int = 60):
        super().__init__(app)
        self.general_limit = general_limit
        self.mutation_limit = mutation_limit
        self.strict_limit = strict_limit
        self.window = window
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_key(self, request) -> str:
        """Extract client identifier from request."""
        # Use X-Forwarded-For if behind a proxy (Railway)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _clean_window(self, key: str, now: float):
        """Remove timestamps outside the current window."""
        cutoff = now - self.window
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def _get_limit(self, request) -> int:
        """Determine rate limit for the request."""
        path = request.url.path
        if path in STRICT_PATHS:
            return self.strict_limit
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            return self.mutation_limit
        return self.general_limit

    async def dispatch(self, request, call_next):
        path = request.url.path

        # Only rate-limit API paths
        if not path.startswith("/api/"):
            return await call_next(request)

        client_key = self._get_client_key(request)
        # Include path category in key for strict endpoints
        if path in STRICT_PATHS:
            rate_key = f"{client_key}:strict:{path}"
        elif request.method in ("POST", "PUT", "DELETE", "PATCH"):
            rate_key = f"{client_key}:mutation"
        else:
            rate_key = f"{client_key}:general"

        now = time.time()
        self._clean_window(rate_key, now)

        limit = self._get_limit(request)

        if len(self._requests[rate_key]) >= limit:
            retry_after = int(self.window - (now - self._requests[rate_key][0]))
            logger.warning(
                "rate_limit_exceeded",
                client=client_key,
                path=path,
                limit=limit,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. Max {limit} requests per {self.window}s. Retry after {retry_after}s."},
                headers={"Retry-After": str(retry_after)},
            )

        self._requests[rate_key].append(now)

        response = await call_next(request)

        # Add rate limit headers
        remaining = limit - len(self._requests[rate_key])
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(int(now + self.window))

        return response
