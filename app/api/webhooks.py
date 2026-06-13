"""
Webhook endpoint API routes — CRUD, test delivery, delivery history.
"""

import json
import time
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_service_client
from app.automations.webhooks import deliver_webhook
from app.automations.triggers import ALL_EVENTS

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class WebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1)
    secret: Optional[str] = None
    events: list[str] = Field(default_factory=list)


class WebhookUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    url: Optional[str] = None
    secret: Optional[str] = None
    events: Optional[list[str]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mask_secret(secret: str | None) -> str | None:
    """Mask webhook secret, showing only the last 4 characters."""
    if not secret:
        return None
    if len(secret) <= 4:
        return "*" * len(secret)
    return "*" * (len(secret) - 4) + secret[-4:]


def _sanitize_webhook(webhook: dict) -> dict:
    """Sanitize a webhook record for API response (mask secret)."""
    webhook = dict(webhook)
    webhook["secret"] = _mask_secret(webhook.get("secret"))
    return webhook


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("/")
async def list_webhooks():
    """List all webhook endpoints."""
    db = get_service_client()

    try:
        result = (
            db.table("webhook_endpoints")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as e:
        logger.error("list_webhooks_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch webhooks")

    webhooks = [_sanitize_webhook(w) for w in (result.data or [])]
    return {"data": webhooks}


@router.get("/events")
async def list_event_types():
    """List available event types you can subscribe a webhook to."""
    event_descriptions = {
        "lead_scored": "Fires when a company receives a new score",
        "company_approved": "Fires when a company is approved in the pipeline",
        "outreach_sent": "Fires when outreach email is sent",
        "stage_changed": "Fires when a company moves pipeline stages",
        "score_threshold": "Fires when a company score crosses a threshold",
        "company_added": "Fires when a new company enters the pipeline",
        "contact_enriched": "Fires when contact info is found for a company",
    }

    events = []
    for event in ALL_EVENTS:
        events.append({
            "type": event,
            "label": event.replace("_", " ").title(),
            "description": event_descriptions.get(event, ""),
        })

    return {"data": events}


@router.get("/{webhook_id}")
async def get_webhook(webhook_id: str):
    """Get webhook details with recent deliveries."""
    db = get_service_client()

    try:
        result = (
            db.table("webhook_endpoints")
            .select("*")
            .eq("id", webhook_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        logger.error("get_webhook_failed", webhook_id=webhook_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch webhook")

    if not result.data:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    webhook = _sanitize_webhook(result.data)

    # Attach recent deliveries
    try:
        deliveries_result = (
            db.table("webhook_deliveries")
            .select("*")
            .eq("webhook_id", webhook_id)
            .order("delivered_at", desc=True)
            .limit(10)
            .execute()
        )
        webhook["recent_deliveries"] = deliveries_result.data or []
    except Exception:
        webhook["recent_deliveries"] = []

    return webhook


@router.post("/")
async def create_webhook(body: WebhookCreate):
    """Create a new webhook endpoint."""
    db = get_service_client()

    # Generate a secret if not provided
    secret = body.secret or secrets.token_hex(32)

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "name": body.name,
        "url": body.url,
        "secret": secret,
        "events": body.events,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "failure_count": 0,
    }

    try:
        result = db.table("webhook_endpoints").insert(record).execute()
    except Exception as e:
        logger.error("create_webhook_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create webhook")

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create webhook")

    logger.info("webhook_created", webhook_id=result.data[0]["id"], name=body.name)
    return _sanitize_webhook(result.data[0])


@router.put("/{webhook_id}")
async def update_webhook(webhook_id: str, body: WebhookUpdate):
    """Update an existing webhook endpoint."""
    db = get_service_client()

    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        result = (
            db.table("webhook_endpoints")
            .update(data)
            .eq("id", webhook_id)
            .execute()
        )
    except Exception as e:
        logger.error("update_webhook_failed", webhook_id=webhook_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update webhook")

    if not result.data:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    logger.info("webhook_updated", webhook_id=webhook_id)
    return _sanitize_webhook(result.data[0])


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """Delete a webhook endpoint and its delivery history (cascade)."""
    db = get_service_client()

    try:
        result = (
            db.table("webhook_endpoints")
            .delete()
            .eq("id", webhook_id)
            .execute()
        )
    except Exception as e:
        logger.error("delete_webhook_failed", webhook_id=webhook_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete webhook")

    if not result.data:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    logger.info("webhook_deleted", webhook_id=webhook_id)
    return {"status": "deleted", "webhook_id": webhook_id}


@router.post("/{webhook_id}/toggle")
async def toggle_webhook(webhook_id: str):
    """Enable or disable a webhook endpoint."""
    db = get_service_client()

    # Fetch current state
    try:
        current = (
            db.table("webhook_endpoints")
            .select("id, is_active")
            .eq("id", webhook_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        logger.error("toggle_webhook_query_failed", webhook_id=webhook_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch webhook")

    if not current.data:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    new_state = not current.data["is_active"]

    try:
        result = (
            db.table("webhook_endpoints")
            .update({
                "is_active": new_state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", webhook_id)
            .execute()
        )
    except Exception as e:
        logger.error("toggle_webhook_update_failed", webhook_id=webhook_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to toggle webhook")

    logger.info("webhook_toggled", webhook_id=webhook_id, is_active=new_state)
    return {"webhook_id": webhook_id, "is_active": new_state}


# ---------------------------------------------------------------------------
# Test delivery
# ---------------------------------------------------------------------------

@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: str):
    """Send a test payload to the webhook URL."""
    db = get_service_client()

    try:
        result = (
            db.table("webhook_endpoints")
            .select("*")
            .eq("id", webhook_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        logger.error("test_webhook_query_failed", webhook_id=webhook_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch webhook")

    if not result.data:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    endpoint = result.data

    test_payload = {
        "event": "test",
        "message": "This is a test delivery from the Username Acquisition Agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "webhook_id": webhook_id,
        "webhook_name": endpoint["name"],
    }

    logger.info("webhook_test_initiated", webhook_id=webhook_id, url=endpoint["url"])

    success = await deliver_webhook(endpoint, "test", test_payload)

    return {
        "webhook_id": webhook_id,
        "success": success,
        "message": "Test delivery successful" if success else "Test delivery failed",
    }


# ---------------------------------------------------------------------------
# Delivery history
# ---------------------------------------------------------------------------

@router.get("/{webhook_id}/deliveries")
async def list_deliveries(
    webhook_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    """List delivery history for a webhook endpoint with pagination."""
    db = get_service_client()
    offset = (page - 1) * page_size

    # Verify webhook exists
    try:
        wh = (
            db.table("webhook_endpoints")
            .select("id")
            .eq("id", webhook_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        logger.error("list_deliveries_wh_check_failed", webhook_id=webhook_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to verify webhook")

    if not wh.data:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    try:
        result = (
            db.table("webhook_deliveries")
            .select("*", count="exact")
            .eq("webhook_id", webhook_id)
            .order("delivered_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
    except Exception as e:
        logger.error("list_deliveries_failed", webhook_id=webhook_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch deliveries")

    return {
        "data": result.data or [],
        "count": result.count or 0,
        "page": page,
        "page_size": page_size,
    }
