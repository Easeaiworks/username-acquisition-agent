"""
Settings API routes — client-facing configuration for Instantly, sender info, etc.

Two-layer config system:
  1. Railway env vars (set by admin in Railway dashboard) — read-only from here
  2. client_settings Supabase table (set by client via Settings page) — read/write

The DB value takes priority when present; otherwise the env var value is shown.
This lets the pipeline work immediately from env vars while still giving
clients a self-service UI to override later.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.config import settings as app_settings
from app.database import get_service_client

import httpx
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


class InstantlySetup(BaseModel):
    api_key: str
    campaign_name: str = "S2Media - Username Acquisition Outreach"


# ---------------------------------------------------------------------------
# Mapping: setting_key → Railway env var attribute on app_settings
# ---------------------------------------------------------------------------
ENV_VAR_MAP = {
    "instantly_api_key": "instantly_api_key",
    "instantly_campaign_id": "instantly_campaign_id",
    "sender_email": "sender_email",
    "sender_name": "sender_name",
    "physical_address": "physical_address",
    "calendly_event_url": "calendly_event_url",
}


def _get_env_value(key: str) -> Optional[str]:
    """Look up the Railway env var value for a given setting key."""
    attr = ENV_VAR_MAP.get(key)
    if attr:
        val = getattr(app_settings, attr, None)
        return val if val else None
    return None


def _resolve_value(db_value: Optional[str], env_value: Optional[str]) -> tuple[str, str]:
    """
    Return (effective_value, source) where source is 'database', 'env', or 'none'.
    DB value takes priority when present.
    """
    if db_value:
        return db_value, "database"
    if env_value:
        return env_value, "env"
    return "", "none"


# ---------------------------------------------------------------------------
# Read settings
# ---------------------------------------------------------------------------

@router.get("/")
async def get_all_settings():
    """Get all client settings, merging DB values with env var fallbacks."""
    db = get_service_client()
    result = db.table("client_settings").select("*").order("setting_key").execute()

    settings_list = []
    for s in (result.data or []):
        db_val = s.get("setting_value") or ""
        env_val = _get_env_value(s["setting_key"])
        effective, source = _resolve_value(db_val, env_val)
        is_secret = s.get("is_secret", False)

        settings_list.append({
            "key": s["setting_key"],
            "value": _mask(effective) if is_secret and effective else effective,
            "has_value": bool(effective),
            "source": source,
            "description": s.get("description", ""),
            "is_secret": is_secret,
            "updated_at": s.get("updated_at"),
        })

    return {"settings": settings_list}


@router.get("/{key}")
async def get_setting(key: str):
    """Get a single setting by key, with env var fallback."""
    db = get_service_client()
    result = db.table("client_settings").select("*").eq("setting_key", key).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    s = result.data[0]
    db_val = s.get("setting_value") or ""
    env_val = _get_env_value(key)
    effective, source = _resolve_value(db_val, env_val)
    is_secret = s.get("is_secret", False)

    return {
        "key": s["setting_key"],
        "value": _mask(effective) if is_secret and effective else effective,
        "has_value": bool(effective),
        "source": source,
        "description": s.get("description", ""),
        "is_secret": is_secret,
        "updated_at": s.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# Update settings
# ---------------------------------------------------------------------------

@router.put("/{key}")
async def update_setting(key: str, body: SettingUpdate):
    """Update a single setting value in the DB (overrides env var)."""
    db = get_service_client()
    now = datetime.now(timezone.utc).isoformat()

    result = db.table("client_settings").select("id").eq("setting_key", key).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    db.table("client_settings").update({
        "setting_value": body.value,
        "updated_at": now,
    }).eq("setting_key", key).execute()

    logger.info("setting_updated", key=key)
    return {"status": "updated", "key": key}


# ---------------------------------------------------------------------------
# Instantly integration helpers
# ---------------------------------------------------------------------------

def _get_instantly_key() -> Optional[str]:
    """Get the Instantly API key from DB first, then env var fallback."""
    try:
        db = get_service_client()
        key_row = (
            db.table("client_settings")
            .select("setting_value")
            .eq("setting_key", "instantly_api_key")
            .execute()
        )
        db_key = key_row.data[0]["setting_value"] if key_row.data else None
        if db_key:
            return db_key
    except Exception:
        pass
    # Fallback to Railway env var
    return app_settings.instantly_api_key


@router.post("/instantly/test")
async def test_instantly_connection():
    """Test the Instantly API connection using stored key OR env var fallback."""
    api_key = _get_instantly_key()

    if not api_key:
        return {"ok": False, "error": "No API key configured. Set INSTANTLY_API_KEY in Railway or enter it on the Settings page."}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.instantly.ai/api/v2/accounts",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                params={"limit": 10},
            )

        if resp.status_code == 401:
            return {"ok": False, "error": "Invalid API key. Check your Instantly API key."}

        if resp.status_code >= 400:
            return {"ok": False, "error": f"Instantly API error: {resp.status_code}"}

        data = resp.json()
        accounts = data.get("items") or data.get("data") or data.get("accounts") or []

        return {
            "ok": True,
            "sending_accounts": len(accounts),
            "accounts": [
                {"email": a.get("email", ""), "status": a.get("status", "")}
                for a in accounts[:10]
            ],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/instantly/auto-setup")
async def auto_setup_instantly(body: InstantlySetup):
    """
    Full Instantly setup: save the API key, auto-create a campaign with
    {{subject}} and {{body}} variables, and store the campaign ID.
    """
    db = get_service_client()
    now = datetime.now(timezone.utc).isoformat()

    # 1. Save the API key to DB
    db.table("client_settings").update({
        "setting_value": body.api_key,
        "updated_at": now,
    }).eq("setting_key", "instantly_api_key").execute()

    # 2. Test the key
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.instantly.ai/api/v2/accounts",
                headers={
                    "Authorization": f"Bearer {body.api_key}",
                    "Content-Type": "application/json",
                },
                params={"limit": 5},
            )
        if resp.status_code == 401:
            return {"ok": False, "step": "auth", "error": "Invalid API key"}
    except Exception as e:
        return {"ok": False, "step": "auth", "error": str(e)}

    # 3. Create campaign with variable templates
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            camp_resp = await client.post(
                "https://api.instantly.ai/api/v2/campaigns",
                headers={
                    "Authorization": f"Bearer {body.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "name": body.campaign_name,
                    "campaign_schedule": {
                        "schedules": [{
                            "name": "Business Hours ET",
                            "timing": {"from": "09:00", "to": "17:00"},
                            "days": {"0": False, "1": True, "2": True, "3": True, "4": True, "5": True, "6": False},
                            "timezone": "Etc/GMT+5",
                        }]
                    },
                    "sequences": [{
                        "steps": [{
                            "type": "email",
                            "delay": 0,
                            "variants": [{
                                "subject": "{{subject}}",
                                "body": "{{body}}",
                            }],
                        }]
                    }],
                },
            )

        if camp_resp.status_code >= 400:
            # Timezone format fallback
            async with httpx.AsyncClient(timeout=20.0) as client:
                camp_resp = await client.post(
                    "https://api.instantly.ai/api/v2/campaigns",
                    headers={
                        "Authorization": f"Bearer {body.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "name": body.campaign_name,
                        "campaign_schedule": {
                            "schedules": [{
                                "name": "Business Hours",
                                "timing": {"from": "09:00", "to": "17:00"},
                                "days": {"0": False, "1": True, "2": True, "3": True, "4": True, "5": True, "6": False},
                                "timezone": "Etc/GMT+12",
                            }]
                        },
                        "sequences": [{
                            "steps": [{
                                "type": "email",
                                "delay": 0,
                                "variants": [{
                                    "subject": "{{subject}}",
                                    "body": "{{body}}",
                                }],
                            }]
                        }],
                    },
                )

        camp_data = camp_resp.json()
        campaign_id = camp_data.get("id")

        if not campaign_id:
            return {"ok": False, "step": "campaign", "error": f"Failed to create campaign: {camp_data}"}

    except Exception as e:
        return {"ok": False, "step": "campaign", "error": str(e)}

    # 4. Save campaign ID
    db.table("client_settings").update({
        "setting_value": campaign_id,
        "updated_at": now,
    }).eq("setting_key", "instantly_campaign_id").execute()

    logger.info("instantly_auto_setup_complete", campaign_id=campaign_id)

    return {
        "ok": True,
        "campaign_id": campaign_id,
        "campaign_name": body.campaign_name,
        "message": "Instantly connected and campaign created successfully.",
    }


# ---------------------------------------------------------------------------
# System status — shows what's configured across both env vars and DB
# ---------------------------------------------------------------------------

@router.get("/system/status")
async def get_system_status():
    """
    Comprehensive config status: which integrations have keys set
    (from either env vars or DB), and which are missing.
    """
    checks = {
        "supabase": bool(app_settings.supabase_url and app_settings.supabase_service_role_key),
        "anthropic": bool(app_settings.anthropic_api_key),
        "instantly_api_key": bool(_get_instantly_key()),
        "instantly_campaign_id": bool(app_settings.instantly_campaign_id or _get_db_value("instantly_campaign_id")),
        "youtube": bool(app_settings.youtube_api_key),
        "twitch": bool(app_settings.twitch_client_id and app_settings.twitch_client_secret),
        "apify": bool(app_settings.apify_api_token),
        "rocketreach": bool(app_settings.rocketreach_api_key),
        "hunter": bool(app_settings.hunter_api_key),
        "sender_email": bool(app_settings.sender_email or _get_db_value("sender_email")),
        "physical_address": bool(app_settings.physical_address or _get_db_value("physical_address")),
    }

    configured = sum(1 for v in checks.values() if v)
    total = len(checks)

    return {
        "configured": configured,
        "total": total,
        "ready": configured == total,
        "integrations": checks,
    }


def _get_db_value(key: str) -> Optional[str]:
    """Quick lookup of a value from client_settings DB."""
    try:
        db = get_service_client()
        result = db.table("client_settings").select("setting_value").eq("setting_key", key).execute()
        val = result.data[0]["setting_value"] if result.data else None
        return val if val else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mask(value: str) -> str:
    """Mask a secret value, showing only the last 4 chars."""
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]
