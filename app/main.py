"""
Sean Lead Agent — FastAPI Application Entry Point

Username Acquisition & Corporate Outreach System
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.logging import setup_logging
from app.api.companies import router as companies_router
from app.api.dashboard import router as dashboard_router

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


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "env": settings.app_env,
    }


@app.get("/")
async def root():
    """Root endpoint — basic system info."""
    return {
        "name": "Sean Lead Agent",
        "description": "Username Acquisition & Corporate Outreach System",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
