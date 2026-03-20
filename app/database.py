"""
Supabase database connection and client management.
Uses the service_role key for backend operations (bypasses RLS).
"""

from supabase import create_client, Client
from app.config import settings
import structlog

logger = structlog.get_logger()

# Service role client — full access, used by backend pipelines
_service_client: Client | None = None

# Anon client — respects RLS, used by dashboard API endpoints
_anon_client: Client | None = None


def get_service_client() -> Client:
    """Get the Supabase client with service_role privileges.
    Use this for all backend pipeline operations (scanning, scoring, enrichment).
    """
    global _service_client
    if _service_client is None:
        _service_client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        logger.info("supabase_service_client_initialized")
    return _service_client


def get_anon_client() -> Client:
    """Get the Supabase client with anon privileges.
    Use this for dashboard-facing API endpoints that should respect RLS.
    """
    global _anon_client
    if _anon_client is None:
        _anon_client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key,
        )
        logger.info("supabase_anon_client_initialized")
    return _anon_client


def get_db() -> Client:
    """Default database client for dependency injection in FastAPI routes.
    Uses service_role for backend operations.
    """
    return get_service_client()
