"""
Email Sequences API routes -- drip campaign / automation sequence management.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.database import get_service_client

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/email/sequences", tags=["Email Sequences"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SequenceCreate(BaseModel):
    name: str
    description: str = ""
    trigger_type: str = "manual"
    trigger_config: dict = {}
    list_id: Optional[str] = None
    from_name: str = ""
    from_email: str = ""


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    list_id: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[str] = None


class StepCreate(BaseModel):
    step_number: int
    step_type: str = "email"
    subject: str = ""
    html_content: str = ""
    text_content: str = ""
    delay_days: int = 0
    delay_hours: int = 0
    delay_minutes: int = 0
    condition_config: dict = {}
    action_type: Optional[str] = None
    action_config: dict = {}
    template_id: Optional[str] = None


class StepUpdate(BaseModel):
    step_number: Optional[int] = None
    step_type: Optional[str] = None
    subject: Optional[str] = None
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    delay_days: Optional[int] = None
    delay_hours: Optional[int] = None
    delay_minutes: Optional[int] = None
    condition_config: Optional[dict] = None
    action_type: Optional[str] = None
    action_config: Optional[dict] = None
    template_id: Optional[str] = None


class EnrollRequest(BaseModel):
    contact_ids: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_sequences(
    request: Request,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
):
    """List sequences with pagination."""
    try:
        db = get_service_client()
        offset = (page - 1) * per_page

        result = (
            db.table("email_sequences")
            .select("*", count="exact")
            .order("created_at", desc=True)
            .range(offset, offset + per_page - 1)
            .execute()
        )

        return {
            "data": result.data or [],
            "count": result.count or 0,
            "page": page,
            "per_page": per_page,
        }
    except Exception as e:
        logger.error("list_sequences_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list sequences")


@router.get("/{sequence_id}")
async def get_sequence(sequence_id: str):
    """Get a sequence with its steps."""
    try:
        db = get_service_client()
        result = db.table("email_sequences").select("*").eq("id", sequence_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Sequence not found")

        sequence = result.data[0]

        # Get steps
        steps = (
            db.table("email_sequence_steps")
            .select("*")
            .eq("sequence_id", sequence_id)
            .order("step_number")
            .execute()
        )

        sequence["steps"] = steps.data or []

        return sequence
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_sequence_error", sequence_id=sequence_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get sequence")


@router.post("", status_code=201)
async def create_sequence(body: SequenceCreate, request: Request):
    """Create a new email sequence."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "name": body.name,
            "description": body.description,
            "trigger_type": body.trigger_type,
            "trigger_config": body.trigger_config,
            "list_id": body.list_id,
            "from_name": body.from_name,
            "from_email": body.from_email,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }

        user_id = getattr(request.state, "user_id", None)
        if user_id:
            record["created_by"] = user_id

        result = db.table("email_sequences").insert(record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create sequence")

        logger.info("email_sequence_created", name=body.name)
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_sequence_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create sequence")


@router.put("/{sequence_id}")
async def update_sequence(sequence_id: str, body: SequenceUpdate):
    """Update a sequence."""
    try:
        db = get_service_client()
        data = body.model_dump(exclude_none=True)

        if not data:
            raise HTTPException(status_code=400, detail="No fields to update")

        data["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = (
            db.table("email_sequences")
            .update(data)
            .eq("id", sequence_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Sequence not found")

        logger.info("email_sequence_updated", sequence_id=sequence_id)
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_sequence_error", sequence_id=sequence_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update sequence")


@router.delete("/{sequence_id}")
async def delete_sequence(sequence_id: str):
    """Delete a sequence (only if draft or paused)."""
    try:
        db = get_service_client()

        existing = db.table("email_sequences").select("status").eq("id", sequence_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Sequence not found")

        if existing.data[0]["status"] not in ("draft", "paused"):
            raise HTTPException(
                status_code=400,
                detail="Only draft or paused sequences can be deleted",
            )

        db.table("email_sequences").delete().eq("id", sequence_id).execute()

        logger.info("email_sequence_deleted", sequence_id=sequence_id)
        return {"status": "deleted", "sequence_id": sequence_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_sequence_error", sequence_id=sequence_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete sequence")


@router.post("/{sequence_id}/activate")
async def activate_sequence(sequence_id: str):
    """Activate a sequence."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        existing = db.table("email_sequences").select("status").eq("id", sequence_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Sequence not found")

        if existing.data[0]["status"] not in ("draft", "paused"):
            raise HTTPException(
                status_code=400,
                detail="Only draft or paused sequences can be activated",
            )

        db.table("email_sequences").update({
            "status": "active",
            "updated_at": now,
        }).eq("id", sequence_id).execute()

        logger.info("email_sequence_activated", sequence_id=sequence_id)
        return {"status": "active", "sequence_id": sequence_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("activate_sequence_error", sequence_id=sequence_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to activate sequence")


@router.post("/{sequence_id}/pause")
async def pause_sequence(sequence_id: str):
    """Pause an active sequence."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        existing = db.table("email_sequences").select("status").eq("id", sequence_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Sequence not found")

        if existing.data[0]["status"] != "active":
            raise HTTPException(
                status_code=400,
                detail="Only active sequences can be paused",
            )

        db.table("email_sequences").update({
            "status": "paused",
            "updated_at": now,
        }).eq("id", sequence_id).execute()

        logger.info("email_sequence_paused", sequence_id=sequence_id)
        return {"status": "paused", "sequence_id": sequence_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("pause_sequence_error", sequence_id=sequence_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to pause sequence")


@router.get("/{sequence_id}/steps")
async def list_steps(sequence_id: str):
    """Get all steps for a sequence, ordered by step number."""
    try:
        db = get_service_client()

        # Verify sequence exists
        seq_check = db.table("email_sequences").select("id").eq("id", sequence_id).execute()
        if not seq_check.data:
            raise HTTPException(status_code=404, detail="Sequence not found")

        result = (
            db.table("email_sequence_steps")
            .select("*")
            .eq("sequence_id", sequence_id)
            .order("step_number")
            .execute()
        )

        return {"data": result.data or []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_steps_error", sequence_id=sequence_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list steps")


@router.post("/{sequence_id}/steps", status_code=201)
async def create_step(sequence_id: str, body: StepCreate):
    """Add a step to a sequence."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        # Verify sequence exists
        seq_check = db.table("email_sequences").select("id").eq("id", sequence_id).execute()
        if not seq_check.data:
            raise HTTPException(status_code=404, detail="Sequence not found")

        record = {
            "sequence_id": sequence_id,
            "step_number": body.step_number,
            "step_type": body.step_type,
            "subject": body.subject,
            "html_content": body.html_content,
            "text_content": body.text_content,
            "delay_days": body.delay_days,
            "delay_hours": body.delay_hours,
            "delay_minutes": body.delay_minutes,
            "condition_config": body.condition_config,
            "action_type": body.action_type,
            "action_config": body.action_config,
            "template_id": body.template_id,
            "created_at": now,
        }

        result = db.table("email_sequence_steps").insert(record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create step")

        logger.info("email_sequence_step_created", sequence_id=sequence_id, step_number=body.step_number)
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail="A step with this number already exists")
        logger.error("create_step_error", sequence_id=sequence_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create step")


@router.put("/{sequence_id}/steps/{step_id}")
async def update_step(sequence_id: str, step_id: str, body: StepUpdate):
    """Update a step in a sequence."""
    try:
        db = get_service_client()
        data = body.model_dump(exclude_none=True)

        if not data:
            raise HTTPException(status_code=400, detail="No fields to update")

        result = (
            db.table("email_sequence_steps")
            .update(data)
            .eq("id", step_id)
            .eq("sequence_id", sequence_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Step not found")

        logger.info("email_sequence_step_updated", sequence_id=sequence_id, step_id=step_id)
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_step_error", sequence_id=sequence_id, step_id=step_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update step")


@router.delete("/{sequence_id}/steps/{step_id}")
async def delete_step(sequence_id: str, step_id: str):
    """Delete a step and renumber remaining steps."""
    try:
        db = get_service_client()

        # Get the step to find its number
        step = (
            db.table("email_sequence_steps")
            .select("step_number")
            .eq("id", step_id)
            .eq("sequence_id", sequence_id)
            .execute()
        )

        if not step.data:
            raise HTTPException(status_code=404, detail="Step not found")

        deleted_step_number = step.data[0]["step_number"]

        # Delete the step
        db.table("email_sequence_steps").delete().eq("id", step_id).execute()

        # Renumber remaining steps that come after the deleted one
        remaining = (
            db.table("email_sequence_steps")
            .select("id, step_number")
            .eq("sequence_id", sequence_id)
            .gt("step_number", deleted_step_number)
            .order("step_number")
            .execute()
        )

        for s in (remaining.data or []):
            db.table("email_sequence_steps").update({
                "step_number": s["step_number"] - 1,
            }).eq("id", s["id"]).execute()

        logger.info("email_sequence_step_deleted", sequence_id=sequence_id, step_id=step_id)
        return {"status": "deleted", "step_id": step_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_step_error", sequence_id=sequence_id, step_id=step_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete step")


@router.post("/{sequence_id}/enroll")
async def enroll_contacts(sequence_id: str, body: EnrollRequest):
    """Enroll contacts in a sequence."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        # Verify sequence exists and is active
        seq = db.table("email_sequences").select("status").eq("id", sequence_id).execute()
        if not seq.data:
            raise HTTPException(status_code=404, detail="Sequence not found")

        if seq.data[0]["status"] != "active":
            raise HTTPException(status_code=400, detail="Sequence must be active to enroll contacts")

        enrolled = 0
        skipped = 0
        errors: list[dict] = []

        for contact_id in body.contact_ids:
            try:
                record = {
                    "sequence_id": sequence_id,
                    "contact_id": contact_id,
                    "current_step": 0,
                    "status": "active",
                    "enrolled_at": now,
                }

                db.table("email_sequence_enrollments").upsert(
                    record, on_conflict="sequence_id,contact_id"
                ).execute()
                enrolled += 1
            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    skipped += 1
                else:
                    errors.append({"contact_id": contact_id, "error": str(e)})

        # Update total_enrolled count
        enrollment_count = (
            db.table("email_sequence_enrollments")
            .select("id", count="exact")
            .eq("sequence_id", sequence_id)
            .execute()
        )
        db.table("email_sequences").update({
            "total_enrolled": enrollment_count.count or 0,
            "updated_at": now,
        }).eq("id", sequence_id).execute()

        logger.info("email_sequence_contacts_enrolled", sequence_id=sequence_id, enrolled=enrolled)
        return {"enrolled": enrolled, "skipped": skipped, "errors": errors}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("enroll_contacts_error", sequence_id=sequence_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to enroll contacts")


@router.post("/{sequence_id}/unenroll/{contact_id}")
async def unenroll_contact(sequence_id: str, contact_id: str):
    """Unenroll a contact from a sequence."""
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc).isoformat()

        result = (
            db.table("email_sequence_enrollments")
            .update({
                "status": "paused",
                "completed_at": now,
            })
            .eq("sequence_id", sequence_id)
            .eq("contact_id", contact_id)
            .eq("status", "active")
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Active enrollment not found")

        logger.info("email_sequence_contact_unenrolled", sequence_id=sequence_id, contact_id=contact_id)
        return {"status": "unenrolled", "sequence_id": sequence_id, "contact_id": contact_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("unenroll_contact_error", sequence_id=sequence_id, contact_id=contact_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to unenroll contact")


@router.get("/{sequence_id}/enrollments")
async def list_enrollments(
    sequence_id: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = None,
):
    """List enrollments for a sequence with status."""
    try:
        db = get_service_client()
        offset = (page - 1) * per_page

        # Verify sequence exists
        seq_check = db.table("email_sequences").select("id").eq("id", sequence_id).execute()
        if not seq_check.data:
            raise HTTPException(status_code=404, detail="Sequence not found")

        query = (
            db.table("email_sequence_enrollments")
            .select("*, email_contacts(email, first_name, last_name)", count="exact")
            .eq("sequence_id", sequence_id)
        )

        if status:
            query = query.eq("status", status)

        query = query.order("enrolled_at", desc=True)
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
        logger.error("list_enrollments_error", sequence_id=sequence_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list enrollments")


@router.get("/{sequence_id}/stats")
async def sequence_stats(sequence_id: str):
    """Get performance stats for a sequence."""
    try:
        db = get_service_client()

        # Get sequence
        seq = db.table("email_sequences").select("*").eq("id", sequence_id).execute()
        if not seq.data:
            raise HTTPException(status_code=404, detail="Sequence not found")

        sequence = seq.data[0]

        # Enrollment stats by status
        active = (
            db.table("email_sequence_enrollments")
            .select("id", count="exact")
            .eq("sequence_id", sequence_id)
            .eq("status", "active")
            .execute()
        )

        completed = (
            db.table("email_sequence_enrollments")
            .select("id", count="exact")
            .eq("sequence_id", sequence_id)
            .eq("status", "completed")
            .execute()
        )

        paused = (
            db.table("email_sequence_enrollments")
            .select("id", count="exact")
            .eq("sequence_id", sequence_id)
            .eq("status", "paused")
            .execute()
        )

        unsubscribed = (
            db.table("email_sequence_enrollments")
            .select("id", count="exact")
            .eq("sequence_id", sequence_id)
            .eq("status", "unsubscribed")
            .execute()
        )

        # Step-level stats
        steps = (
            db.table("email_sequence_steps")
            .select("id, step_number, step_type, subject, sent_count, open_count, click_count")
            .eq("sequence_id", sequence_id)
            .order("step_number")
            .execute()
        )

        # Total events for this sequence
        events = (
            db.table("email_events")
            .select("event_type")
            .eq("sequence_id", sequence_id)
            .execute()
        )

        event_counts: dict[str, int] = {}
        for event in (events.data or []):
            etype = event.get("event_type", "unknown")
            event_counts[etype] = event_counts.get(etype, 0) + 1

        return {
            "sequence_id": sequence_id,
            "name": sequence.get("name"),
            "status": sequence.get("status"),
            "total_enrolled": sequence.get("total_enrolled", 0),
            "total_completed": sequence.get("total_completed", 0),
            "enrollments": {
                "active": active.count or 0,
                "completed": completed.count or 0,
                "paused": paused.count or 0,
                "unsubscribed": unsubscribed.count or 0,
            },
            "events": event_counts,
            "steps": steps.data or [],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("sequence_stats_error", sequence_id=sequence_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get sequence stats")
