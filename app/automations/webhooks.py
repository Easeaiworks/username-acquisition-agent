"""
Webhook dispatch system — delivers event payloads to subscribed HTTP endpoints.

When an event occurs in the pipeline, registered webhook endpoints that subscribe
to that event type receive an HTTP POST with the event payload. Deliveries are
logged in the webhook_deliveries table for debugging and retry tracking.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import httpx
import structlog

from app.database import get_service_client

logger = structlog.get_logger()

DELIVERY_TIMEOUT = 10.0  # seconds


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Single webhook delivery
# ---------------------------------------------------------------------------

async def deliver_webhook(endpoint: dict, event_type: str, payload: dict) -> bool:
    """
    POST a webhook payload to a single endpoint.

    Includes standard webhook headers:
        X-Webhook-Event: the event type
        X-Webhook-Timestamp: Unix timestamp of delivery
        X-Webhook-Signature: HMAC-SHA256 hex digest (if endpoint has a secret)

    Args:
        endpoint: Row from webhook_endpoints table
        event_type: Event type string (e.g. 'lead_scored')
        payload: Event payload dict

    Returns:
        True if delivery was successful (2xx response), False otherwise
    """
    url = endpoint["url"]
    webhook_id = endpoint["id"]
    secret = endpoint.get("secret")

    timestamp = str(int(time.time()))
    payload_bytes = json.dumps(payload, default=str).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event_type,
        "X-Webhook-Timestamp": timestamp,
        "User-Agent": "UsernameAcquisition-Webhook/1.0",
    }

    if secret:
        # Sign: timestamp + "." + payload
        sign_data = f"{timestamp}.".encode("utf-8") + payload_bytes
        signature = _sign_payload(sign_data, secret)
        headers["X-Webhook-Signature"] = f"sha256={signature}"

    response_status = None
    response_body = None
    success = False

    try:
        async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT) as client:
            resp = await client.post(url, content=payload_bytes, headers=headers)

        response_status = resp.status_code
        response_body = resp.text[:2000]  # cap stored response size
        success = 200 <= resp.status_code < 300

        logger.info(
            "webhook_delivered",
            webhook_id=webhook_id,
            url=url,
            event_type=event_type,
            status=resp.status_code,
            success=success,
        )

    except httpx.TimeoutException:
        response_body = "Timeout after 10s"
        logger.warning("webhook_timeout", webhook_id=webhook_id, url=url)

    except httpx.ConnectError as e:
        response_body = f"Connection error: {str(e)[:500]}"
        logger.warning("webhook_connect_error", webhook_id=webhook_id, url=url, error=str(e))

    except Exception as e:
        response_body = f"Error: {str(e)[:500]}"
        logger.error("webhook_delivery_error", webhook_id=webhook_id, url=url, error=str(e))

    # Log delivery in webhook_deliveries table
    try:
        db = get_service_client()
        db.table("webhook_deliveries").insert({
            "webhook_id": webhook_id,
            "event_type": event_type,
            "payload": payload,
            "response_status": response_status,
            "response_body": response_body,
            "success": success,
            "attempt": 1,
            "delivered_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.error("webhook_delivery_log_failed", webhook_id=webhook_id, error=str(e))

    # Update endpoint stats
    try:
        db = get_service_client()
        update_data: dict = {
            "last_triggered_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if not success:
            update_data["failure_count"] = (endpoint.get("failure_count") or 0) + 1
        else:
            # Reset failure count on success
            update_data["failure_count"] = 0

        db.table("webhook_endpoints").update(update_data).eq("id", webhook_id).execute()
    except Exception as e:
        logger.error("webhook_endpoint_update_failed", webhook_id=webhook_id, error=str(e))

    return success


# ---------------------------------------------------------------------------
# Batch dispatch
# ---------------------------------------------------------------------------

async def dispatch_webhooks(event_type: str, payload: dict) -> int:
    """
    Find all active webhook endpoints subscribed to the given event type
    and deliver the payload to each.

    Uses Postgres array containment to check if the event_type is in the
    endpoint's events array.

    Args:
        event_type: The event type (e.g. 'lead_scored', 'company_approved')
        payload: The event payload dict

    Returns:
        Number of webhooks dispatched (attempted)
    """
    db = get_service_client()

    try:
        result = (
            db.table("webhook_endpoints")
            .select("*")
            .eq("is_active", True)
            .contains("events", [event_type])
            .execute()
        )
        endpoints = result.data or []
    except Exception as e:
        logger.error("webhook_query_failed", event_type=event_type, error=str(e))
        return 0

    if not endpoints:
        logger.debug("no_webhook_endpoints", event_type=event_type)
        return 0

    logger.info(
        "dispatching_webhooks",
        event_type=event_type,
        endpoint_count=len(endpoints),
    )

    dispatched = 0

    for endpoint in endpoints:
        try:
            await deliver_webhook(endpoint, event_type, payload)
            dispatched += 1
        except Exception as e:
            logger.error(
                "webhook_dispatch_error",
                webhook_id=endpoint["id"],
                url=endpoint["url"],
                error=str(e),
            )

    logger.info(
        "webhooks_dispatched",
        event_type=event_type,
        total=len(endpoints),
        dispatched=dispatched,
    )

    return dispatched
