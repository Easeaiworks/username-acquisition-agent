"""
Settings API routes — client-facing configuration for Instantly, sender info, etc.

Clients use these endpoints (via the dashboard Settings page) to enter their
own Instantly API key and campaign ID, so they don't need Railway access.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.database import get_service_client
from app.integrations import instantly

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    value: str


class InstantlySetup(BaseModel):
    api_key: str
    campaign_name: str = "S2Media - Username Acquisition Outreach"


# ---------------------------------------------------------------------------
# Read settings
# ---------------------------------------------------------------------------

@router.get("/")
async def get_all_settings():
    """Get all client settings (secrets are masked)."""
    db = get_service_client()
    result = db.table("client_settings").select("*").order("setting_key").execute()

    settings_list = []
    for s in (result.data or []):
        val = s.get("setting_value") or ""
        settings_list.append({
            "key": s["setting_key"],
            "value": _mask(val) if s.get("is_secret") and val else val,
            "has_value": bool(val),
            "description": s.get("description", ""),
            "is_secret": s.get("is_secret", False),
            "updated_at": s.get("updated_at"),
        })

    return {"settings": settings_list}


@router.get("/{key}")
async def get_setting(key: str):
    """Get a single setting by key (secrets are masked)."""
    db = get_service_client()
    result = db.table("client_settings").select("*").eq("setting_key", key).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    s = result.data[0]
    val = s.get("setting_value") or ""
    return {
        "key": s["setting_key"],
        "value": _mask(val) if s.get("is_secret") and val else val,
        "has_value": bool(val),
        "description": s.get("description", ""),
        "is_secret": s.get("is_secret", False),
        "updated_at": s.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# Update settings
# ---------------------------------------------------------------------------

@router.put("/{key}")
async def update_setting(key: str, body: SettingUpdate):
    """Update a single setting value."""
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

@router.post("/instantly/test")
async def test_instantly_connection():
    """Test the Instantly API connection using the stored API key."""
    db = get_service_client()
    key_row = (
        db.table("client_settings")
        .select("setting_value")
        .eq("setting_key", "instantly_api_key")
        .execute()
    )
    api_key = (key_row.data[0]["setting_value"] if key_row.data else None)

    if not api_key:
        return {"ok": False, "error": "No API key configured. Enter your Instantly API key first."}

    try:
        # Use the stored key to test the connection
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.instantly.ai/api/v2/accounts",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                params={"limit": 5},
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
                for a in accounts[:5]
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

    # 1. Save the API key
    db.table("client_settings").update({
        "setting_value": body.api_key,
        "updated_at": now,
    }).eq("setting_key", "instantly_api_key").execute()

    # 2. Test the key
    import httpx
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
            # If timezone format fails, try without timezone
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
# Helpers
# ---------------------------------------------------------------------------

def _mask(value: str) -> str:
    """Mask a secret value, showing only the last 4 chars."""
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]
