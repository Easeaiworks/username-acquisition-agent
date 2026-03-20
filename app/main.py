"""
Sean Lead Agent — FastAPI Application Entry Point

Username Acquisition & Corporate Outreach System
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.utils.logging import setup_logging
from app.api.companies import router as companies_router
from app.api.dashboard import router as dashboard_router
from app.api.scoring import router as scoring_router
from app.api.enrichment import router as enrichment_router
from app.api.outreach import router as outreach_router

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
    )

    # Initialize scheduler if in production
    if settings.is_production:
        from app.scheduler.daily_scan import start_scheduler
        start_scheduler()
        logger.info("scheduler_started")

    yield

    # Shutdown
    logger.info("application_shutting_down")


app = FastAPI(
    title="Sean Lead Agent",
    description="Username Acquisition & Corporate Outreach System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow dashboard frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",       # Local dashboard dev
        "http://localhost:5173",       # Vite dev server
        "https://*.railway.app",       # Railway deployed dashboard
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(companies_router)
app.include_router(dashboard_router)
app.include_router(scoring_router)
app.include_router(enrichment_router)
app.include_router(outreach_router)


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
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
    # Serve static assets (JS, CSS, images) from /assets
    app.mount("/assets", StaticFiles(directory=DASHBOARD_DIR / "assets"), name="dashboard-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Catch-all: serve the React SPA for any non-API route."""
        # If a static file exists in dist, serve it directly
        file_path = DASHBOARD_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise, serve index.html for client-side routing
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
