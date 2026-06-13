"""
Email Contacts API routes -- CRUD, tagging, import, and unsubscribe management.
"""

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field

from app.database import get_service_client

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/email/contacts", tags=["Email Contacts"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ContactCreate(BaseModel):
    email: EmailStr
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    phone: str = ""
    tags: list[str] = Field(default_factory=list)
    custom_fields: dict = Field(default_factory=dict)
    source: str = "manual"


class ContactUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    tags: Optional[list[str]] = None
    custom_fields: Optional[dict] = None
    status: Optional[str] = None


class ContactImportItem(BaseModel):
    email: EmailStr
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    tags: list[str] = Field(default_factory=list)


class ContactImportRequest(BaseModel):
    contacts: list[ContactImportItem]


class TagsRequest(BaseModel):
    tags: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
async def list_contacts(
    request: Request,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    search: Optional[str] = None,
    status: Optional[str] = None,
    list_id: Optional[str] = None,
    tags: Optional[str] = Query(default=None, description="Comma-separated tags to filter by"),
):
    """List contacts with pagination, search, and filters."""
    try:
        db = get_service_client()
        offset = (page - 1) * per_page

        if list_id:
            # Get contacts through list membership join
            query = (
                db.table("email_list_members")
                .select(
                    "contact_id, email_contacts(*)",
                    count="exact",
                )
                .eq("list_id", list_id)
                .eq("status", "active")
            )
            query = query.range(offset, offset + per_page - 1)
            result = query.execute()

            contacts = [row["email_contacts"] for row in (result.data or []) if row.get("email_contacts")]

            # Apply search/status filters in-memory for list-filtered queries
            if search:
                s = search.lower()
                contacts = [
                    c for c in contacts
                    if s in (c.get("email") or "").lower()
                    or s in (c.get("first_name") or "").lower()
                    or s in (c.get("last_name") or "").lower()
                ]
            if status:
                contacts = [c for c in contacts if c.get("status") == status]

            return {
                "data": contacts,
                "count": result.count or 0,
                "page": page,
                "per_page": per_page,
            }

        # Standard query without list filter
        query = db.table("email_contacts").select("*", count="exact")

        if status:
            query = query.eq("status", status)

        if search:
            sanitized = re.sub(r"[^\w\s\-\.@]", "", search).strip()[:100]
            if sanitized:
                query = query.or_(
                    f"email.ilike.%{sanitized}%,"
                    f"first_name.ilike.%{sanitized}%,"
                    f"last_name.ilike.%{sanitized}%"
                )

        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            for tag in tag_list:
                query = query.contains("tags", [tag])

        query = query.order("created_at", desc=True)
        query = query.range(offset, offset + per_page - 1)
        result = query.execute()

        return {
            "data": result.data or [],
            "count": result.count or 0,
            "page": page,
            "per_page": per_page,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_contacts_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list contacts")


@router.get("/{contact_id}")
async def get_contact(contact_id: str):
    """Get a single contact with engagement stats."""
    try:
        db = get_service_client()
        result = db.table("email_contacts").select("*").eq("id", contact_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Contact not found")

        contact = result.data[0]

        # Get engagement stats from email_events
        events = (
            db.table("email_events")
            .select("event_type", count="exact")
            .eq("contact_id", contact_id)
            .execute()
        )

        event_counts: dict[str, int] = {}
        for event in (events.data or []):
            etype = event.get("event_type", "unknown")
            event_counts[etype] = event_counts.get(etype, 0) + 1

        # Get list memberships
        memberships = (
            db.table("email_list_members")
            .select("list_id, status, added_at, email_lists(name)")
            .eq("contact_id", contact_id)
            .execute()
        )

        contact["engagement_stats"] = event_counts
        contact["lists"] = memberships.data or []

        return contact
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_contact_error", contact_id=contact_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get contact")


@router.post("/", status_code=201)
async def create_contact(body: ContactCreate):
    """Create a new email contact."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "email": body.email,
            "first_name": body.first_name,
            "last_name": body.last_name,
            "company": body.company,
            "phone": body.phone,
            "tags": body.tags,
            "custom_fields": body.custom_fields,
            "source": body.source,
            "status": "subscribed",
            "subscribed_at": now,
            "created_at": now,
            "updated_at": now,
        }

        result = db.table("email_contacts").insert(record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create contact")

        logger.info("email_contact_created", email=body.email)
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="A contact with this email already exists")
        logger.error("create_contact_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create contact")


@router.put("/{contact_id}")
async def update_contact(contact_id: str, body: ContactUpdate):
    """Update contact fields."""
    try:
        db = get_service_client()
        data = body.model_dump(exclude_none=True)

        if not data:
            raise HTTPException(status_code=400, detail="No fields to update")

        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = (
            db.table("email_contacts")
            .update(data)
            .eq("id", contact_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Contact not found")

        logger.info("email_contact_updated", contact_id=contact_id)
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_contact_error", contact_id=contact_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update contact")


@router.delete("/{contact_id}")
async def delete_contact(contact_id: str):
    """Soft-delete a contact by setting status to 'cleaned'."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        result = (
            db.table("email_contacts")
            .update({"status": "cleaned", "updated_at": now})
            .eq("id", contact_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Contact not found")

        logger.info("email_contact_soft_deleted", contact_id=contact_id)
        return {"status": "deleted", "contact_id": contact_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_contact_error", contact_id=contact_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete contact")


@router.post("/import")
async def import_contacts(body: ContactImportRequest):
    """Bulk import contacts from a JSON array. Upserts by email."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        imported = 0
        skipped = 0
        errors: list[dict] = []

        for item in body.contacts:
            try:
                record = {
                    "email": item.email,
                    "first_name": item.first_name,
                    "last_name": item.last_name,
                    "company": item.company,
                    "tags": item.tags,
                    "source": "import",
                    "status": "subscribed",
                    "subscribed_at": now,
                    "created_at": now,
                    "updated_at": now,
                }

                result = (
                    db.table("email_contacts")
                    .upsert(record, on_conflict="email")
                    .execute()
                )

                if result.data:
                    imported += 1
                else:
                    skipped += 1
            except Exception as e:
                errors.append({"email": item.email, "error": str(e)})

        logger.info(
            "email_contacts_imported",
            imported=imported,
            skipped=skipped,
            errors=len(errors),
        )
        return {"imported": imported, "skipped": skipped, "errors": errors}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("import_contacts_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to import contacts")


@router.post("/{contact_id}/tags")
async def add_tags(contact_id: str, body: TagsRequest):
    """Add tags to a contact (merge with existing)."""
    try:
        db = get_service_client()

        # Get current tags
        result = db.table("email_contacts").select("tags").eq("id", contact_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Contact not found")

        existing_tags = result.data[0].get("tags") or []
        merged = list(set(existing_tags + body.tags))

        update_result = (
            db.table("email_contacts")
            .update({"tags": merged, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", contact_id)
            .execute()
        )

        logger.info("email_contact_tags_added", contact_id=contact_id, tags=body.tags)
        return {"contact_id": contact_id, "tags": merged}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("add_tags_error", contact_id=contact_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to add tags")


@router.delete("/{contact_id}/tags")
async def remove_tags(contact_id: str, body: TagsRequest):
    """Remove specific tags from a contact."""
    try:
        db = get_service_client()

        # Get current tags
        result = db.table("email_contacts").select("tags").eq("id", contact_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Contact not found")

        existing_tags = result.data[0].get("tags") or []
        updated = [t for t in existing_tags if t not in body.tags]

        update_result = (
            db.table("email_contacts")
            .update({"tags": updated, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", contact_id)
            .execute()
        )

        logger.info("email_contact_tags_removed", contact_id=contact_id, tags=body.tags)
        return {"contact_id": contact_id, "tags": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("remove_tags_error", contact_id=contact_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to remove tags")


@router.post("/{contact_id}/unsubscribe")
async def unsubscribe_contact(contact_id: str):
    """Unsubscribe a contact -- set status to 'unsubscribed' and record timestamp."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        result = (
            db.table("email_contacts")
            .update({
                "status": "unsubscribed",
                "unsubscribed_at": now,
                "updated_at": now,
            })
            .eq("id", contact_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Contact not found")

        logger.info("email_contact_unsubscribed", contact_id=contact_id)
        return {"status": "unsubscribed", "contact_id": contact_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("unsubscribe_contact_error", contact_id=contact_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to unsubscribe contact")
