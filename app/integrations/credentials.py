"""
Credential Resolver — reads API keys from the admin-managed
api_integrations table first, falls back to Railway environment
variables when no DB value is set.

This is what makes the admin panel's "Integrations" page actually
take effect: when a non-developer admin enters their Hunter.io API
key through the UI, it gets stored in api_integrations and this
module ensures the backend reads it from there instead of relying
solely on the env var.

Usage:
    from app.integrations.credentials import get_credential

    api_key = await get_credential("hunter", "api_key")
    client_id = await get_credential("twitch", "client_id")
"""

from __future__ import annotations

import time
from typing import Optional

import structlog

from app.config import settings

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# In-memory TTL cache — avoids a DB round-trip on every API call.
# Entries expire after CACHE_TTL_SECONDS so admin changes propagate quickly.
# ---------------------------------------------------------------------------

CACHE_TTL_SECONDS = 120  # 2 minutes

_cache: dict[str, tuple[float, dict]] = {}  # service_name -> (expires_at, row_data)


def _cache_get(service_name: str) -> Optional[dict]:
    """Return cached row data if still fresh, else None."""
    entry = _cache.get(service_name)
    if entry is None:
        return None
    expires_at, data = entry
    if time.monotonic() > expires_at:
        del _cache[service_name]
        return None
    return data


def _cache_set(service_name: str, data: dict) -> None:
    _cache[service_name] = (time.monotonic() + CACHE_TTL_SECONDS, data)


def invalidate_cache(service_name: Optional[str] = None) -> None:
    """
    Clear the credential cache.
    Call this after an admin updates an integration via the API.
    Pass a service_name to clear just that service, or None to flush all.
    """
    if service_name:
        _cache.pop(service_name, None)
    else:
        _cache.clear()


# ---------------------------------------------------------------------------
# Mapping: DB service_name + field -> settings attribute (env var fallback)
# ---------------------------------------------------------------------------

_ENV_FALLBACK: dict[tuple[str, str], str] = {
    # Data Enrichment
    ("hunter", "api_key"): "hunter_api_key",
    ("rocketreach", "api_key"): "rocketreach_api_key",
    ("apify", "api_key"): "apify_api_token",
    ("youtube", "api_key"): "youtube_api_key",
    ("twitch", "client_id"): "twitch_client_id",
    ("twitch", "client_secret"): "twitch_client_secret",

    # Email Providers
    ("instantly", "api_key"): "instantly_api_key",
    ("instantly", "campaign_id"): "instantly_campaign_id",
    ("sendgrid", "api_key"): None,  # no env var currently
    ("mailgun", "api_key"): None,
    ("mailgun", "domain"): None,

    # Scheduling
    ("calendly", "api_key"): "calendly_api_key",
    ("calendly", "event_url"): "calendly_event_url",

    # AI
    ("anthropic", "api_key"): "anthropic_api_key",
}


def _env_fallback(service_name: str, field: str) -> Optional[str]:
    """
    Look up the settings attribute for a given service+field combo.
    Returns the value from the Railway env var, or None.
    """
    attr_name = _ENV_FALLBACK.get((service_name, field))
    if attr_name is None:
        return None
    return getattr(settings, attr_name, None)


# ---------------------------------------------------------------------------
# Core resolver
# ---------------------------------------------------------------------------

async def _fetch_integration_row(service_name: str) -> Optional[dict]:
    """Query the api_integrations table for a service. Returns the row as dict."""
    try:
        from app.database import get_service_client
        db = get_service_client()
        result = (
            db.table("api_integrations")
            .select("api_key_encrypted, extra_config, is_connected")
            .eq("service_name", service_name)
            .maybe_single()
            .execute()
        )
        return result.data if result.data else None
    except Exception as e:
        logger.warning(
            "credential_db_lookup_failed",
            service=service_name,
            error=str(e),
        )
        return None


async def get_credential(service_name: str, field: str = "api_key") -> Optional[str]:
    """
    Resolve a credential value for a given service and field.

    Priority:
        1. api_integrations table (admin-managed via the dashboard)
        2. Railway environment variable (set by developer in Railway)

    Args:
        service_name: e.g. "hunter", "instantly", "twitch"
        field: e.g. "api_key", "client_id", "campaign_id", "client_secret"

    Returns:
        The credential string, or None if not configured anywhere.

    Examples:
        api_key = await get_credential("hunter", "api_key")
        client_id = await get_credential("twitch", "client_id")
        campaign_id = await get_credential("instantly", "campaign_id")
    """
    # 1. Check cache
    row = _cache_get(service_name)

    # 2. Cache miss — fetch from DB
    if row is None:
        row = await _fetch_integration_row(service_name)
        if row is not None:
            _cache_set(service_name, row)
        else:
            # Cache a "not found" marker so we don't re-query on every call
            _cache_set(service_name, {"_empty": True})
            row = {"_empty": True}

    # 3. Extract the value from the DB row
    db_value = None

    if not row.get("_empty"):
        if field == "api_key":
            # Primary API key stored in the dedicated column
            db_value = row.get("api_key_encrypted")
        else:
            # Additional fields stored in extra_config JSON
            extra = row.get("extra_config") or {}
            db_value = extra.get(field)

    # 4. Return DB value if present, otherwise env var fallback
    if db_value:
        return db_value

    return _env_fallback(service_name, field)


async def is_connected(service_name: str) -> bool:
    """Check if a service has valid credentials (either DB or env var)."""
    key = await get_credential(service_name, "api_key")
    return key is not None and len(key) > 0


async def get_all_credentials(service_name: str) -> dict[str, Optional[str]]:
    """
    Get all credential fields for a service as a dict.
    Useful for services that need multiple fields (e.g., Twitch needs
    client_id + client_secret).

    Returns:
        Dict of field_name -> value, with DB taking priority over env vars.
    """
    # Gather all known fields for this service from the fallback map
    fields = set()
    for (svc, fld) in _ENV_FALLBACK:
        if svc == service_name:
            fields.add(fld)

    # Always include "api_key" as a base field
    fields.add("api_key")

    result = {}
    for field in fields:
        result[field] = await get_credential(service_name, field)

    return result
