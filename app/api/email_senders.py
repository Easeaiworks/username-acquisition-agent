"""
Email Senders API routes -- manage SMTP / SendGrid / SES sender configurations.

IMPORTANT: Sensitive fields in the config JSON (passwords, API keys, secrets)
are masked when returned via the API.
"""

import copy
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.database import get_service_client

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/email/senders", tags=["Email Senders"])


# ---------------------------------------------------------------------------
# Sensitive field masking
# ---------------------------------------------------------------------------

SENSITIVE_KEYS = frozenset({
    "password", "api_key", "secret_access_key", "secret", "token",
})


def _mask_config(config: dict) -> dict:
    """Replace sensitive values with masked versions showing only last 4 chars."""
    masked = copy.deepcopy(config)
    for key, value in masked.items():
        if key.lower() in SENSITIVE_KEYS and isinstance(value, str) and len(value) > 4:
            masked[key] = "••••••" + value[-4:]
        elif key.lower() in SENSITIVE_KEYS and isinstance(value, str):
            masked[key] = "••••••"
    return masked


def _mask_sender_row(row: dict) -> dict:
    """Mask sensitive fields in a sender config row."""
    result = dict(row)
    if "config" in result and isinstance(result["config"], dict):
        result["config"] = _mask_config(result["config"])
    return result


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SenderConfigCreate(BaseModel):
    name: str
    sender_type: str  # 'smtp', 'sendgrid', 'ses'
    config: dict  # Provider-specific config
    from_email: str
    from_name: str = ""
    daily_limit: int = 500


class SenderConfigUpdate(BaseModel):
    name: Optional[str] = None
    sender_type: Optional[str] = None
    config: Optional[dict] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    daily_limit: Optional[int] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_senders():
    """List all sender configurations (sensitive fields masked)."""
    try:
        db = get_service_client()
        result = db.table("email_sender_config").select("*").order("created_at", desc=True).execute()

        return {"data": [_mask_sender_row(row) for row in (result.data or [])]}
    except Exception as e:
        logger.error("list_senders_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list sender configs")


@router.get("/{config_id}")
async def get_sender(config_id: str):
    """Get a sender config (sensitive fields masked)."""
    try:
        db = get_service_client()
        result = db.table("email_sender_config").select("*").eq("id", config_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Sender config not found")

        return _mask_sender_row(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_sender_error", config_id=config_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get sender config")


@router.post("", status_code=201)
async def create_sender(body: SenderConfigCreate):
    """Create a new sender configuration."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        if body.sender_type not in ("smtp", "sendgrid", "ses"):
            raise HTTPException(
                status_code=400,
                detail="sender_type must be 'smtp', 'sendgrid', or 'ses'",
            )

        record = {
            "name": body.name,
            "sender_type": body.sender_type,
            "config": body.config,
            "from_email": body.from_email,
            "from_name": body.from_name,
            "daily_limit": body.daily_limit,
            "is_default": False,
            "is_verified": False,
            "sent_today": 0,
            "last_reset_at": now,
            "created_at": now,
            "updated_at": now,
        }

        result = db.table("email_sender_config").insert(record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create sender config")

        logger.info("email_sender_config_created", name=body.name, sender_type=body.sender_type)
        return _mask_sender_row(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_sender_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create sender config")


@router.put("/{config_id}")
async def update_sender(config_id: str, body: SenderConfigUpdate):
    """Update a sender configuration."""
    try:
        db = get_service_client()
        data = body.model_dump(exclude_none=True)

        if not data:
            raise HTTPException(status_code=400, detail="No fields to update")

        if "sender_type" in data and data["sender_type"] not in ("smtp", "sendgrid", "ses"):
            raise HTTPException(
                status_code=400,
                detail="sender_type must be 'smtp', 'sendgrid', or 'ses'",
            )

        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = (
            db.table("email_sender_config")
            .update(data)
            .eq("id", config_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Sender config not found")

        logger.info("email_sender_config_updated", config_id=config_id)
        return _mask_sender_row(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_sender_error", config_id=config_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update sender config")


@router.delete("/{config_id}")
async def delete_sender(config_id: str):
    """Delete a sender configuration."""
    try:
        db = get_service_client()

        result = db.table("email_sender_config").delete().eq("id", config_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Sender config not found")

        logger.info("email_sender_config_deleted", config_id=config_id)
        return {"status": "deleted", "config_id": config_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_sender_error", config_id=config_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete sender config")


@router.post("/{config_id}/verify")
async def verify_sender(config_id: str, request: Request):
    """Test a sender config by verifying the connection/credentials."""
    try:
        db = get_service_client()

        # Get the config
        result = db.table("email_sender_config").select("*").eq("id", config_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Sender config not found")

        row = result.data[0]

        # Build a sender instance and verify
        from app.email.sender import _build_sender_from_row

        sender = _build_sender_from_row(row)
        if not sender:
            raise HTTPException(status_code=400, detail="Failed to build sender from config")

        verified = await sender.verify_config()

        # Update is_verified flag
        db.table("email_sender_config").update({
            "is_verified": verified,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", config_id).execute()

        if verified:
            logger.info("email_sender_verified", config_id=config_id)
            return {"status": "verified", "config_id": config_id}
        else:
            return {"status": "failed", "config_id": config_id, "message": "Verification failed -- check credentials"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("verify_sender_error", config_id=config_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to verify sender config")


@router.post("/{config_id}/set-default")
async def set_default_sender(config_id: str):
    """Set a sender config as the default (unsets all others)."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        # Verify config exists
        config_check = db.table("email_sender_config").select("id").eq("id", config_id).execute()
        if not config_check.data:
            raise HTTPException(status_code=404, detail="Sender config not found")

        # Unset all other defaults
        db.table("email_sender_config").update({
            "is_default": False,
            "updated_at": now,
        }).eq("is_default", True).execute()

        # Set this one as default
        db.table("email_sender_config").update({
            "is_default": True,
            "updated_at": now,
        }).eq("id", config_id).execute()

        logger.info("email_sender_set_default", config_id=config_id)
        return {"status": "default_set", "config_id": config_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("set_default_sender_error", config_id=config_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to set default sender")
