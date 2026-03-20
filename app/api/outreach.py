"""
Outreach API routes — manage sequences, process replies, trigger auto-outreach.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from app.database import get_service_client
from app.engine_b.sequence_manager import (
    create_outreach_sequence,
    handle_reply,
    run_auto_outreach,
    process_followups,
)

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/outreach", tags=["outreach"])


class ReplyRequest(BaseModel):
    reply_text: str


class ManualOutreachRequest(BaseModel):
    company_id: str
    contact_id: str
    auto_send: bool = False


@router.post("/auto-run")
async def trigger_auto_outreach(
    background_tasks: BackgroundTasks,
    threshold: Optional[float] = Query(default=None),
):
    """
    Trigger auto-outreach for all qualified companies.

    Runs in the background. Creates and sends sequences for
    Critical/Very High companies that are approved.
    """
    background_tasks.add_task(_run_auto_outreach, threshold)

    return {
        "status": "started",
        "message": "Auto-outreach running in background",
    }


async def _run_auto_outreach(threshold: Optional[float]):
    try:
        result = await run_auto_outreach(threshold=threshold)
        logger.info("background_auto_outreach_complete", result=result)
    except Exception as e:
        logger.error("background_auto_outreach_error", error=str(e))


@router.post("/followups")
async def trigger_followups(background_tasks: BackgroundTasks):
    """Process all pending follow-ups for active sequences."""
    background_tasks.add_task(_run_followups)

    return {
        "status": "started",
        "message": "Processing follow-ups in background",
    }


async def _run_followups():
    try:
        result = await process_followups()
        logger.info("background_followups_complete", result=result)
    except Exception as e:
        logger.error("background_followups_error", error=str(e))


@router.post("/create")
async def create_manual_outreach(request: ManualOutreachRequest):
    """Manually create an outreach sequence for a specific company/contact."""
    db = get_service_client()

    # Fetch company
    company = db.table("companies").select("*").eq("id", request.company_id).execute()
    if not company.data:
        raise HTTPException(status_code=404, detail="Company not found")

    # Fetch contact
    contact = db.table("contacts").select("*").eq("id", request.contact_id).execute()
    if not contact.data:
        raise HTTPException(status_code=404, detail="Contact not found")

    result = await create_outreach_sequence(
        company=company.data[0],
        contact=contact.data[0],
        auto_send=request.auto_send,
    )

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Outreach blocked by compliance checks or missing email",
        )

    return result


@router.post("/{outreach_id}/reply")
async def process_reply(outreach_id: str, request: ReplyRequest):
    """Process an incoming reply to an outreach message."""
    result = await handle_reply(
        outreach_id=outreach_id,
        reply_text=request.reply_text,
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/{outreach_id}")
async def get_outreach_detail(outreach_id: str):
    """Get detailed info about a specific outreach sequence."""
    db = get_service_client()

    result = (
        db.table("outreach_sequences")
        .select("*, contacts(full_name, email, title), companies(brand_name)")
        .eq("id", outreach_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Outreach record not found")

    return result.data[0]


@router.get("/company/{company_id}")
async def get_company_outreach(company_id: str):
    """Get all outreach sequences for a company."""
    db = get_service_client()

    result = (
        db.table("outreach_sequences")
        .select("*, contacts(full_name, email, title)")
        .eq("company_id", company_id)
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "company_id": company_id,
        "sequences": result.data,
        "total": len(result.data),
    }


@router.get("/queue/pending")
async def get_pending_outreach(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Get outreach messages pending manual approval (draft status)."""
    db = get_service_client()
    offset = (page - 1) * page_size

    result = (
        db.table("outreach_sequences")
        .select("*, contacts(full_name, email, title), companies(brand_name, total_opportunity_score)", count="exact")
        .eq("status", "draft")
        .order("created_at", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )

    return {
        "data": result.data,
        "count": result.count or 0,
        "page": page,
        "page_size": page_size,
    }


@router.post("/{outreach_id}/approve")
async def approve_outreach(outreach_id: str):
    """Approve and send a draft outreach message."""
    db = get_service_client()

    outreach = db.table("outreach_sequences").select("*").eq("id", outreach_id).execute()
    if not outreach.data:
        raise HTTPException(status_code=404, detail="Outreach record not found")

    if outreach.data[0]["status"] != "draft":
        raise HTTPException(status_code=400, detail="Only draft messages can be approved")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    db.table("outreach_sequences").update({
        "status": "sent",
        "sent_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }).eq("id", outreach_id).execute()

    return {"status": "approved_and_sent", "outreach_id": outreach_id}


@router.post("/{outreach_id}/reject")
async def reject_outreach(outreach_id: str):
    """Reject a draft outreach message."""
    db = get_service_client()

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    db.table("outreach_sequences").update({
        "status": "failed",
        "updated_at": now.isoformat(),
    }).eq("id", outreach_id).execute()

    return {"status": "rejected", "outreach_id": outreach_id}
