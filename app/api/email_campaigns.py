"""
Email Campaigns API routes -- create, send, schedule, and track email campaigns.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.database import get_service_client

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/email/campaigns", tags=["Email Campaigns"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CampaignCreate(BaseModel):
    name: str
    subject: str = ""
    preview_text: str = ""
    from_name: str = ""
    from_email: str = ""
    reply_to: str = ""
    html_content: str = ""
    text_content: str = ""
    list_id: Optional[str] = None
    campaign_type: str = "regular"


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    preview_text: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    list_id: Optional[str] = None


class ScheduleRequest(BaseModel):
    scheduled_at: str  # ISO datetime string


class PreviewRequest(BaseModel):
    html_content: str
    subject: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
async def list_campaigns(
    request: Request,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = None,
):
    """List campaigns with pagination and optional status filter."""
    try:
        db = get_service_client()
        offset = (page - 1) * per_page

        query = db.table("email_campaigns").select("*", count="exact")

        if status:
            query = query.eq("status", status)

        query = query.order("created_at", desc=True)
        query = query.range(offset, offset + per_page - 1)
        result = query.execute()

        return {
            "data": result.data or [],
            "count": result.count or 0,
            "page": page,
            "per_page": per_page,
        }
    except Exception as e:
        logger.error("list_campaigns_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list campaigns")


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get a single campaign with stats."""
    try:
        db = get_service_client()
        result = db.table("email_campaigns").select("*").eq("id", campaign_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_campaign_error", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get campaign")


@router.post("/", status_code=201)
async def create_campaign(body: CampaignCreate, request: Request):
    """Create a new email campaign."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "name": body.name,
            "subject": body.subject,
            "preview_text": body.preview_text,
            "from_name": body.from_name,
            "from_email": body.from_email,
            "reply_to": body.reply_to,
            "html_content": body.html_content,
            "text_content": body.text_content,
            "list_id": body.list_id,
            "campaign_type": body.campaign_type,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }

        user_id = getattr(request.state, "user_id", None)
        if user_id:
            record["created_by"] = user_id

        result = db.table("email_campaigns").insert(record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create campaign")

        logger.info("email_campaign_created", name=body.name)
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_campaign_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create campaign")


@router.put("/{campaign_id}")
async def update_campaign(campaign_id: str, body: CampaignUpdate):
    """Update a campaign (only if draft or scheduled)."""
    try:
        db = get_service_client()

        # Check current status
        existing = db.table("email_campaigns").select("status").eq("id", campaign_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if existing.data[0]["status"] not in ("draft", "scheduled"):
            raise HTTPException(
                status_code=400,
                detail="Only draft or scheduled campaigns can be edited",
            )

        data = body.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(status_code=400, detail="No fields to update")

        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = (
            db.table("email_campaigns")
            .update(data)
            .eq("id", campaign_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        logger.info("email_campaign_updated", campaign_id=campaign_id)
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_campaign_error", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update campaign")


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: str):
    """Delete a campaign (only if draft)."""
    try:
        db = get_service_client()

        # Check current status
        existing = db.table("email_campaigns").select("status").eq("id", campaign_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if existing.data[0]["status"] != "draft":
            raise HTTPException(
                status_code=400,
                detail="Only draft campaigns can be deleted",
            )

        db.table("email_campaigns").delete().eq("id", campaign_id).execute()

        logger.info("email_campaign_deleted", campaign_id=campaign_id)
        return {"status": "deleted", "campaign_id": campaign_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_campaign_error", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete campaign")


@router.post("/{campaign_id}/schedule")
async def schedule_campaign(campaign_id: str, body: ScheduleRequest):
    """Schedule a campaign for future sending."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        # Validate campaign exists and is draft
        existing = db.table("email_campaigns").select("status").eq("id", campaign_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if existing.data[0]["status"] not in ("draft", "scheduled"):
            raise HTTPException(
                status_code=400,
                detail="Only draft or scheduled campaigns can be scheduled",
            )

        result = (
            db.table("email_campaigns")
            .update({
                "status": "scheduled",
                "scheduled_at": body.scheduled_at,
                "updated_at": now,
            })
            .eq("id", campaign_id)
            .execute()
        )

        logger.info("email_campaign_scheduled", campaign_id=campaign_id, scheduled_at=body.scheduled_at)
        return {"status": "scheduled", "campaign_id": campaign_id, "scheduled_at": body.scheduled_at}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("schedule_campaign_error", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to schedule campaign")


@router.post("/{campaign_id}/send")
async def send_campaign(campaign_id: str):
    """
    Send a campaign immediately.

    Fetches all subscribed contacts from the campaign's list, renders templates
    with tracking, and sends in batches of 50.
    """
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        # 1. Get campaign
        campaign_result = db.table("email_campaigns").select("*").eq("id", campaign_id).execute()
        if not campaign_result.data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        campaign = campaign_result.data[0]

        if campaign["status"] not in ("draft", "scheduled"):
            raise HTTPException(
                status_code=400,
                detail=f"Campaign cannot be sent (current status: {campaign['status']})",
            )

        if not campaign.get("list_id"):
            raise HTTPException(status_code=400, detail="Campaign has no list assigned")

        # 2. Set status to sending
        db.table("email_campaigns").update({
            "status": "sending",
            "started_sending_at": now,
            "updated_at": now,
        }).eq("id", campaign_id).execute()

        # 3. Get subscribed contacts from the list
        members = (
            db.table("email_list_members")
            .select("contact_id, email_contacts(*)")
            .eq("list_id", campaign["list_id"])
            .eq("status", "active")
            .execute()
        )

        contacts = []
        for member in (members.data or []):
            contact = member.get("email_contacts")
            if contact and contact.get("status") == "subscribed":
                contacts.append(contact)

        if not contacts:
            db.table("email_campaigns").update({
                "status": "sent",
                "finished_sending_at": now,
                "recipients_count": 0,
                "updated_at": now,
            }).eq("id", campaign_id).execute()
            return {"sent": 0, "failed": 0, "message": "No subscribed contacts in list"}

        # Update recipients count
        db.table("email_campaigns").update({
            "recipients_count": len(contacts),
        }).eq("id", campaign_id).execute()

        # 4. Get sender
        from app.email.sender import get_default_sender, EmailMessage

        sender = await get_default_sender()
        if not sender:
            db.table("email_campaigns").update({
                "status": "draft",
                "started_sending_at": None,
                "updated_at": now,
            }).eq("id", campaign_id).execute()
            raise HTTPException(status_code=500, detail="No default email sender configured")

        # 5. Send in batches of 50
        from app.email.template_engine import render_template, get_default_variables
        from app.email.tracking import inject_tracking

        sent_count = 0
        failed_count = 0
        batch_size = 50

        for i in range(0, len(contacts), batch_size):
            batch = contacts[i:i + batch_size]
            messages = []

            for contact in batch:
                # Render template
                variables = get_default_variables(contact=contact, campaign=campaign)
                html = render_template(campaign["html_content"], variables)

                # Inject tracking (open pixel, click wrapping, unsubscribe)
                html = inject_tracking(
                    html=html,
                    campaign_id=campaign_id,
                    contact_id=contact["id"],
                )

                # Render text content if present
                text_content = ""
                if campaign.get("text_content"):
                    text_content = render_template(campaign["text_content"], variables)

                # Render subject
                subject = render_template(campaign["subject"], variables)

                messages.append(EmailMessage(
                    to_email=contact["email"],
                    to_name=f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                    from_email=campaign.get("from_email", ""),
                    from_name=campaign.get("from_name", ""),
                    reply_to=campaign.get("reply_to", ""),
                    subject=subject,
                    html_content=html,
                    text_content=text_content,
                    campaign_id=campaign_id,
                    contact_id=contact["id"],
                ))

            # Send the batch
            results = await sender.send_batch(messages)

            # Record events
            send_time = datetime.now(timezone.utc).isoformat()
            for msg, result in zip(messages, results):
                if result.success:
                    sent_count += 1
                    # Record sent event
                    try:
                        db.table("email_events").insert({
                            "campaign_id": campaign_id,
                            "contact_id": msg.contact_id,
                            "event_type": "sent",
                            "metadata": {"message_id": result.message_id or ""},
                            "created_at": send_time,
                        }).execute()

                        # Update contact's last_emailed_at and email_count
                        db.table("email_contacts").update({
                            "last_emailed_at": send_time,
                            "email_count": contact.get("email_count", 0) + 1,
                        }).eq("id", msg.contact_id).execute()
                    except Exception as e:
                        logger.error("record_sent_event_error", error=str(e))
                else:
                    failed_count += 1

            # Small delay between batches
            if i + batch_size < len(contacts):
                await asyncio.sleep(1)

        # 8. Update campaign stats and status
        finish_time = datetime.now(timezone.utc).isoformat()
        db.table("email_campaigns").update({
            "status": "sent",
            "sent_count": sent_count,
            "finished_sending_at": finish_time,
            "updated_at": finish_time,
        }).eq("id", campaign_id).execute()

        logger.info(
            "email_campaign_sent",
            campaign_id=campaign_id,
            sent=sent_count,
            failed=failed_count,
        )
        return {"sent": sent_count, "failed": failed_count}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("send_campaign_error", campaign_id=campaign_id, error=str(e))
        # Revert status on unexpected error
        try:
            db = get_service_client()
            db.table("email_campaigns").update({
                "status": "draft",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", campaign_id).execute()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to send campaign")


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: str):
    """Pause a sending campaign."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        existing = db.table("email_campaigns").select("status").eq("id", campaign_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if existing.data[0]["status"] != "sending":
            raise HTTPException(
                status_code=400,
                detail="Only actively sending campaigns can be paused",
            )

        db.table("email_campaigns").update({
            "status": "paused",
            "updated_at": now,
        }).eq("id", campaign_id).execute()

        logger.info("email_campaign_paused", campaign_id=campaign_id)
        return {"status": "paused", "campaign_id": campaign_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("pause_campaign_error", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to pause campaign")


@router.post("/{campaign_id}/duplicate")
async def duplicate_campaign(campaign_id: str, request: Request):
    """Duplicate a campaign as a new draft."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        # Get original campaign
        original = db.table("email_campaigns").select("*").eq("id", campaign_id).execute()
        if not original.data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        campaign = original.data[0]

        # Create copy as draft
        new_record = {
            "name": f"{campaign['name']} (Copy)",
            "subject": campaign.get("subject", ""),
            "preview_text": campaign.get("preview_text", ""),
            "from_name": campaign.get("from_name", ""),
            "from_email": campaign.get("from_email", ""),
            "reply_to": campaign.get("reply_to", ""),
            "html_content": campaign.get("html_content", ""),
            "text_content": campaign.get("text_content", ""),
            "template_id": campaign.get("template_id"),
            "list_id": campaign.get("list_id"),
            "segment_conditions": campaign.get("segment_conditions", {}),
            "campaign_type": campaign.get("campaign_type", "regular"),
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }

        user_id = getattr(request.state, "user_id", None)
        if user_id:
            new_record["created_by"] = user_id

        result = db.table("email_campaigns").insert(new_record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to duplicate campaign")

        logger.info("email_campaign_duplicated", original_id=campaign_id, new_id=result.data[0]["id"])
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("duplicate_campaign_error", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to duplicate campaign")


@router.get("/{campaign_id}/stats")
async def campaign_stats(campaign_id: str):
    """Get detailed campaign stats."""
    try:
        db = get_service_client()

        # Get campaign
        campaign = db.table("email_campaigns").select("*").eq("id", campaign_id).execute()
        if not campaign.data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        c = campaign.data[0]

        # Get event counts by type
        events = (
            db.table("email_events")
            .select("event_type")
            .eq("campaign_id", campaign_id)
            .execute()
        )

        event_counts: dict[str, int] = {}
        for event in (events.data or []):
            etype = event.get("event_type", "unknown")
            event_counts[etype] = event_counts.get(etype, 0) + 1

        sent = c.get("sent_count", 0) or event_counts.get("sent", 0)
        delivered = c.get("delivered_count", 0) or event_counts.get("delivered", 0)
        opened = c.get("open_count", 0) or event_counts.get("opened", 0)
        clicked = c.get("click_count", 0) or event_counts.get("clicked", 0)
        bounced = c.get("bounce_count", 0) or event_counts.get("bounced", 0)
        unsubscribed = c.get("unsubscribe_count", 0) or event_counts.get("unsubscribed", 0)

        open_rate = (opened / sent * 100) if sent > 0 else 0.0
        click_rate = (clicked / sent * 100) if sent > 0 else 0.0
        bounce_rate = (bounced / sent * 100) if sent > 0 else 0.0
        unsubscribe_rate = (unsubscribed / sent * 100) if sent > 0 else 0.0

        return {
            "campaign_id": campaign_id,
            "name": c.get("name"),
            "status": c.get("status"),
            "recipients_count": c.get("recipients_count", 0),
            "sent": sent,
            "delivered": delivered,
            "opened": opened,
            "unique_opens": c.get("unique_open_count", 0),
            "clicked": clicked,
            "unique_clicks": c.get("unique_click_count", 0),
            "bounced": bounced,
            "unsubscribed": unsubscribed,
            "complained": c.get("complaint_count", 0),
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2),
            "bounce_rate": round(bounce_rate, 2),
            "unsubscribe_rate": round(unsubscribe_rate, 2),
            "started_sending_at": c.get("started_sending_at"),
            "finished_sending_at": c.get("finished_sending_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("campaign_stats_error", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get campaign stats")


@router.post("/preview")
async def preview_campaign(body: PreviewRequest):
    """Render a preview of campaign content with sample data."""
    try:
        from app.email.template_engine import render_template

        sample_contact = {
            "email": "jane@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "company": "Acme Corp",
        }

        sample_campaign = {
            "name": "Preview Campaign",
        }

        from app.email.template_engine import get_default_variables
        variables = get_default_variables(contact=sample_contact, campaign=sample_campaign)

        rendered_html = render_template(body.html_content, variables)
        rendered_subject = render_template(body.subject, variables) if body.subject else ""

        return {
            "html": rendered_html,
            "subject": rendered_subject,
        }
    except Exception as e:
        logger.error("preview_campaign_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to render preview")
