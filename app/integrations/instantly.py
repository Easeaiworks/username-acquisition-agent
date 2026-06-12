"""
Instantly.ai V2 API client.

Instantly handles deliverability (warmup, rotation, throttling), reply
detection, bounce handling, and scheduling. Our app generates the
personalized message body; Instantly delivers it.

Integration pattern:
    1. User creates a campaign in Instantly with sequence steps that
       reference custom variables (e.g. {{subject}}, {{body}}).
    2. We add a "lead" to that campaign with the generated subject/body
       passed as custom variables.
    3. Instantly sends the message per the campaign's schedule using
       the connected sending inbox (e.g. sean@s2media.live).
    4. Instantly tracks delivery/opens/replies and fires webhooks that
       our /api/webhooks/instantly endpoint ingests.

Docs: https://developer.instantly.ai (V2 API).
Auth: Bearer token via INSTANTLY_API_KEY.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx
import structlog

from app.config import settings
from app.integrations.credentials import get_credential

logger = structlog.get_logger()

BASE_URL = "https://api.instantly.ai/api/v2"
DEFAULT_TIMEOUT = 20.0


class InstantlyError(Exception):
    """Raised when the Instantly API returns a non-success response."""


async def _resolve_api_key() -> str:
    """Resolve the Instantly API key from DB or env var."""
    key = await get_credential("instantly")
    if not key:
        raise InstantlyError("INSTANTLY_API_KEY is not configured")
    return key


def _headers_with_key(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _request(
    method: str,
    path: str,
    *,
    json: Optional[dict] = None,
    params: Optional[dict] = None,
) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    api_key = await _resolve_api_key()
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.request(method, url, headers=_headers_with_key(api_key), json=json, params=params)

    if resp.status_code >= 400:
        body = resp.text[:500]
        logger.error(
            "instantly_api_error",
            method=method,
            path=path,
            status=resp.status_code,
            body=body,
        )
        raise InstantlyError(f"{method} {path} → {resp.status_code}: {body}")

    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

async def list_campaigns(limit: int = 50) -> list[dict]:
    """List all campaigns in the Instantly workspace."""
    data = await _request("GET", "/campaigns", params={"limit": limit})
    return data.get("items") or data.get("data") or data.get("campaigns") or []


async def get_campaign(campaign_id: str) -> dict:
    """Fetch details for a single campaign."""
    return await _request("GET", f"/campaigns/{campaign_id}")


# ---------------------------------------------------------------------------
# Leads / sending
# ---------------------------------------------------------------------------

async def add_lead_to_campaign(
    *,
    campaign_id: str,
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    company_name: Optional[str] = None,
    personalization: Optional[str] = None,
    custom_variables: Optional[dict[str, str]] = None,
    skip_if_in_workspace: bool = True,
) -> dict:
    """
    Add a lead to an Instantly campaign so it gets sent at the next scheduled slot.

    The `custom_variables` dict is merged into Instantly's lead-level custom
    variable bag; campaigns can reference these as {{variable_name}} inside
    their sequence templates.
    """
    payload: dict[str, Any] = {
        "campaign": campaign_id,
        "email": email,
        "skip_if_in_workspace": skip_if_in_workspace,
    }
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if company_name:
        payload["company_name"] = company_name
    if personalization:
        payload["personalization"] = personalization

    # Instantly stores arbitrary custom variables in the lead's custom_variables field
    custom = dict(custom_variables or {})
    if custom:
        payload["custom_variables"] = custom

    data = await _request("POST", "/leads", json=payload)
    logger.info(
        "instantly_lead_added",
        campaign_id=campaign_id,
        email=email,
        lead_id=data.get("id"),
    )
    return data


async def update_lead(lead_id: str, **fields: Any) -> dict:
    """Update fields on an existing lead."""
    return await _request("PATCH", f"/leads/{lead_id}", json=fields)


async def get_lead_by_email(email: str) -> Optional[dict]:
    """Look up a lead in the workspace by email address."""
    data = await _request(
        "POST",
        "/leads/list",
        json={"search": email, "limit": 1},
    )
    items = data.get("items") or data.get("data") or []
    return items[0] if items else None


# ---------------------------------------------------------------------------
# Health / accounts
# ---------------------------------------------------------------------------

async def list_sending_accounts() -> list[dict]:
    """List the email accounts connected to Instantly for sending."""
    data = await _request("GET", "/accounts", params={"limit": 100})
    return data.get("items") or data.get("data") or data.get("accounts") or []


async def healthcheck() -> dict:
    """Lightweight check that the API key is valid and accounts exist."""
    try:
        accounts = await list_sending_accounts()
        return {
            "ok": True,
            "sending_accounts": len(accounts),
            "warmed_up": sum(1 for a in accounts if a.get("warmup_status") == "active"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# High-level convenience
# ---------------------------------------------------------------------------

async def send_outreach(
    *,
    to_email: str,
    subject: str,
    body: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    company_name: Optional[str] = None,
    campaign_id: Optional[str] = None,
) -> dict:
    """
    Send a single outreach email by adding the recipient to an Instantly campaign.

    Returns the provider response (which includes the lead id). Raises
    InstantlyError on configuration / API failure.
    """
    campaign_id = campaign_id or await get_credential("instantly", "campaign_id")
    if not campaign_id:
        raise InstantlyError(
            "INSTANTLY_CAMPAIGN_ID is not configured. Create a campaign in "
            "Instantly with sequence steps using {{subject}} and {{body}} "
            "variables, then set the campaign id in Railway."
        )

    return await add_lead_to_campaign(
        campaign_id=campaign_id,
        email=to_email,
        first_name=first_name,
        last_name=last_name,
        company_name=company_name,
        personalization=body,  # Instantly's first-class personalization slot
        custom_variables={
            "subject": subject,
            "body": body,
        },
    )
