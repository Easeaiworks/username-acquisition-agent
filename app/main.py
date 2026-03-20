"""
Sean Lead Agent — FastAPI Application Entry Point

Username Acquisition & Corporate Outreach System
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.utils.logging import setup_logging
from app.middleware.auth import AuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.api.companies import router as companies_router
from app.api.dashboard import router as dashboard_router
from app.api.scoring import router as scoring_router
from app.api.enrichment import router as enrichment_router
from app.api.outreach import router as outreach_router
from app.api.reports import router as reports_router

import structlog


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    setup_logging()
    logger = structlog.get_logger()
    logger.info(
        "application_starting",
        env=settings.app_env,
        port=settings.app_port,
        auth_enabled=settings.require_auth,
    )

    # Validate critical config in production
    if settings.is_production:
        _validate_production_config(logger)
        from app.scheduler.daily_scan import start_scheduler
        start_scheduler()
        logger.info("scheduler_started")

    yield

    # Shutdown
    logger.info("application_shutting_down")


def _validate_production_config(logger):
    """Verify all required settings are present before production startup."""
    warnings = []
    if not settings.dashboard_api_key:
        warnings.append("DASHBOARD_API_KEY not set — API endpoints are unprotected")
    if not settings.require_auth:
        warnings.append("REQUIRE_AUTH is false — authentication is disabled")
    if not settings.sender_email:
        warnings.append("SENDER_EMAIL not set — outreach will not send")
    if not settings.physical_address:
        warnings.append("PHYSICAL_ADDRESS not set — CAN-SPAM non-compliant")

    for w in warnings:
        logger.warning("production_config_warning", message=w)


app = FastAPI(
    title="Sean Lead Agent",
    description="Username Acquisition & Corporate Outreach System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# ---------------------------------------------------------------------------
# Middleware stack (order matters — last added = first executed)
# ---------------------------------------------------------------------------

# 1. CORS — configure allowed origins
_origins = ["http://localhost:3000", "http://localhost:5173"]
if settings.allowed_origins:
    _origins.extend(o.strip() for o in settings.allowed_origins.split(",") if o.strip())
elif settings.is_production:
    # In production without explicit origins, restrict to same-origin only
    _origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# 2. Security headers on every response
app.add_middleware(SecurityHeadersMiddleware)

# 3. Rate limiting
app.add_middleware(
    RateLimitMiddleware,
    general_limit=settings.api_rate_limit,
    mutation_limit=max(settings.api_rate_limit // 3, 10),
    strict_limit=5,
)

# 4. API key authentication
app.add_middleware(AuthMiddleware)

# ---------------------------------------------------------------------------
# Register API routes
# ---------------------------------------------------------------------------
app.include_router(companies_router)
app.include_router(dashboard_router)
app.include_router(scoring_router)
app.include_router(enrichment_router)
app.include_router(outreach_router)
app.include_router(reports_router)


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway (unauthenticated)."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "env": settings.app_env,
    }


# ---------------------------------------------------------------------------
# Serve React dashboard static files in production
# ---------------------------------------------------------------------------
DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "dist"

if DASHBOARD_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DASHBOARD_DIR / "assets"), name="dashboard-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Catch-all: serve the React SPA for any non-API route."""
        # Prevent path traversal
        safe_path = Path(full_path).name if full_path else ""
        file_path = DASHBOARD_DIR / safe_path
        if safe_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(DASHBOARD_DIR / "index.html")
else:
    @app.get("/")
    async def root():
        """Root endpoint — basic system info (dashboard not built)."""
        return {
            "name": "Sean Lead Agent",
            "description": "Username Acquisition & Corporate Outreach System",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }
