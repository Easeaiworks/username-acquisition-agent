"""
Email Lists API routes -- audience/mailing list management with membership.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.database import get_service_client

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/email/lists", tags=["Email Lists"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ListCreate(BaseModel):
    name: str
    description: str = ""
    default_from_name: str = ""
    default_from_email: str = ""
    default_reply_to: str = ""


class ListUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    default_from_name: Optional[str] = None
    default_from_email: Optional[str] = None
    default_reply_to: Optional[str] = None
    is_active: Optional[bool] = None


class AddMembersRequest(BaseModel):
    contact_ids: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
async def list_lists(request: Request):
    """List all email lists with contact counts."""
    try:
        db = get_service_client()
        result = db.table("email_lists").select("*").order("created_at", desc=True).execute()

        return {"data": result.data or []}
    except Exception as e:
        logger.error("list_lists_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list email lists")


@router.get("/{list_id}")
async def get_list(list_id: str):
    """Get email list details."""
    try:
        db = get_service_client()
        result = db.table("email_lists").select("*").eq("id", list_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="List not found")

        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_list_error", list_id=list_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get list")


@router.post("/", status_code=201)
async def create_list(body: ListCreate, request: Request):
    """Create a new email list."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "name": body.name,
            "description": body.description,
            "default_from_name": body.default_from_name,
            "default_from_email": body.default_from_email,
            "default_reply_to": body.default_reply_to,
            "contact_count": 0,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        # Set created_by if user is authenticated
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            record["created_by"] = user_id

        result = db.table("email_lists").insert(record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create list")

        logger.info("email_list_created", name=body.name)
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_list_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create list")


@router.put("/{list_id}")
async def update_list(list_id: str, body: ListUpdate):
    """Update an email list."""
    try:
        db = get_service_client()
        data = body.model_dump(exclude_none=True)

        if not data:
            raise HTTPException(status_code=400, detail="No fields to update")

        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = (
            db.table("email_lists")
            .update(data)
            .eq("id", list_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="List not found")

        logger.info("email_list_updated", list_id=list_id)
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_list_error", list_id=list_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update list")


@router.delete("/{list_id}")
async def delete_list(list_id: str):
    """Delete an email list (cascades to memberships)."""
    try:
        db = get_service_client()

        result = db.table("email_lists").delete().eq("id", list_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="List not found")

        logger.info("email_list_deleted", list_id=list_id)
        return {"status": "deleted", "list_id": list_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_list_error", list_id=list_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete list")


@router.get("/{list_id}/members")
async def list_members(
    list_id: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
):
    """Get members of an email list with pagination."""
    try:
        db = get_service_client()
        offset = (page - 1) * per_page

        # Verify list exists
        list_check = db.table("email_lists").select("id").eq("id", list_id).execute()
        if not list_check.data:
            raise HTTPException(status_code=404, detail="List not found")

        result = (
            db.table("email_list_members")
            .select("*, email_contacts(*)", count="exact")
            .eq("list_id", list_id)
            .order("added_at", desc=True)
            .range(offset, offset + per_page - 1)
            .execute()
        )

        return {
            "data": result.data or [],
            "count": result.count or 0,
            "page": page,
            "per_page": per_page,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_members_error", list_id=list_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list members")


@router.post("/{list_id}/members")
async def add_members(list_id: str, body: AddMembersRequest):
    """Add contacts to an email list."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        # Verify list exists
        list_check = db.table("email_lists").select("id").eq("id", list_id).execute()
        if not list_check.data:
            raise HTTPException(status_code=404, detail="List not found")

        added = 0
        skipped = 0
        errors: list[dict] = []

        for contact_id in body.contact_ids:
            try:
                record = {
                    "list_id": list_id,
                    "contact_id": contact_id,
                    "status": "active",
                    "added_at": now,
                }
                db.table("email_list_members").upsert(
                    record, on_conflict="list_id,contact_id"
                ).execute()
                added += 1
            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    skipped += 1
                else:
                    errors.append({"contact_id": contact_id, "error": str(e)})

        # Update contact count on the list
        count_result = (
            db.table("email_list_members")
            .select("id", count="exact")
            .eq("list_id", list_id)
            .eq("status", "active")
            .execute()
        )
        db.table("email_lists").update({
            "contact_count": count_result.count or 0,
            "updated_at": now,
        }).eq("id", list_id).execute()

        logger.info("email_list_members_added", list_id=list_id, added=added, skipped=skipped)
        return {"added": added, "skipped": skipped, "errors": errors}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("add_members_error", list_id=list_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to add members")


@router.delete("/{list_id}/members/{contact_id}")
async def remove_member(list_id: str, contact_id: str):
    """Remove a contact from an email list."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        result = (
            db.table("email_list_members")
            .delete()
            .eq("list_id", list_id)
            .eq("contact_id", contact_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Membership not found")

        # Update contact count
        count_result = (
            db.table("email_list_members")
            .select("id", count="exact")
            .eq("list_id", list_id)
            .eq("status", "active")
            .execute()
        )
        db.table("email_lists").update({
            "contact_count": count_result.count or 0,
            "updated_at": now,
        }).eq("id", list_id).execute()

        logger.info("email_list_member_removed", list_id=list_id, contact_id=contact_id)
        return {"status": "removed", "list_id": list_id, "contact_id": contact_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("remove_member_error", list_id=list_id, contact_id=contact_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to remove member")


@router.get("/{list_id}/stats")
async def list_stats(list_id: str):
    """Get engagement stats for an email list."""
    try:
        db = get_service_client()

        # Verify list exists
        list_check = db.table("email_lists").select("*").eq("id", list_id).execute()
        if not list_check.data:
            raise HTTPException(status_code=404, detail="List not found")

        list_data = list_check.data[0]

        # Total members
        total_result = (
            db.table("email_list_members")
            .select("id", count="exact")
            .eq("list_id", list_id)
            .execute()
        )
        total = total_result.count or 0

        # Subscribed (active) members
        subscribed_result = (
            db.table("email_list_members")
            .select("id", count="exact")
            .eq("list_id", list_id)
            .eq("status", "active")
            .execute()
        )
        subscribed = subscribed_result.count or 0

        # Get campaigns sent to this list for open/click rates
        campaigns = (
            db.table("email_campaigns")
            .select("sent_count, open_count, click_count")
            .eq("list_id", list_id)
            .eq("status", "sent")
            .execute()
        )

        total_sent = 0
        total_opens = 0
        total_clicks = 0
        for c in (campaigns.data or []):
            total_sent += c.get("sent_count", 0)
            total_opens += c.get("open_count", 0)
            total_clicks += c.get("click_count", 0)

        open_rate = (total_opens / total_sent * 100) if total_sent > 0 else 0.0
        click_rate = (total_clicks / total_sent * 100) if total_sent > 0 else 0.0

        return {
            "list_id": list_id,
            "name": list_data.get("name"),
            "total": total,
            "subscribed": subscribed,
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2),
            "campaigns_sent": len(campaigns.data or []),
            "total_emails_sent": total_sent,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_stats_error", list_id=list_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get list stats")
