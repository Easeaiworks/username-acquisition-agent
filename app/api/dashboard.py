"""
Dashboard API routes — aggregate data for the React dashboard.
"""

from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_service_client

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
async def dashboard_overview():
    """Get the main dashboard overview — all key metrics at a glance."""
    db = get_service_client()

    # Total companies
    total = db.table("companies").select("id", count="exact").execute()

    # By pipeline stage
    stages = {}
    for stage in ["discovered", "scanned", "scored", "enriching", "qualified", "outreach", "meeting", "closed"]:
        result = db.table("companies").select("id", count="exact").eq("pipeline_stage", stage).execute()
        stages[stage] = result.count or 0

    # Critical/Very High opportunities
    critical = (
        db.table("companies")
        .select("id", count="exact")
        .in_("priority_bucket", ["critical", "very_high"])
        .execute()
    )

    # Pending approval
    pending_approval = (
        db.table("companies")
        .select("id", count="exact")
        .eq("pipeline_stage", "scored")
        .gte("total_opportunity_score", 0.5)
        .eq("approved_for_outreach", False)
        .execute()
    )

    # Today's outreach
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_outreach = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .gte("sent_at", today_start.isoformat())
        .execute()
    )

    # Total meetings booked
    meetings = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("meeting_booked", True)
        .execute()
    )

    # Replies today
    today_replies = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("status", "replied")
        .gte("response_classified_at", today_start.isoformat())
        .execute()
    )

    return {
        "total_companies": total.count or 0,
        "pipeline_stages": stages,
        "high_value_opportunities": critical.count or 0,
        "pending_approval": pending_approval.count or 0,
        "outreach_sent_today": today_outreach.count or 0,
        "total_meetings_booked": meetings.count or 0,
        "replies_today": today_replies.count or 0,
    }


@router.get("/approval-queue")
async def approval_queue(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Get companies waiting for outreach approval."""
    db = get_service_client()
    offset = (page - 1) * page_size

    result = (
        db.table("companies")
        .select("*, platform_handles(*)", count="exact")
        .eq("pipeline_stage", "scored")
        .gte("total_opportunity_score", 0.5)
        .lt("total_opportunity_score", 0.65)
        .eq("approved_for_outreach", False)
        .order("total_opportunity_score", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )

    return {
        "data": result.data,
        "count": result.count or 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/top-opportunities")
async def top_opportunities(limit: int = Query(default=10, ge=1, le=50)):
    """Get the top-scoring opportunities across the pipeline."""
    db = get_service_client()

    result = (
        db.table("companies")
        .select("*, platform_handles(*)")
        .gte("total_opportunity_score", 0.5)
        .order("total_opportunity_score", desc=True)
        .limit(limit)
        .execute()
    )

    return result.data


@router.get("/recent-activity")
async def recent_activity(limit: int = Query(default=20, ge=1, le=100)):
    """Get recent audit log entries for the activity feed."""
    db = get_service_client()

    result = (
        db.table("audit_log")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return result.data


@router.get("/outreach-stats")
async def outreach_stats(days: int = Query(default=30, ge=1, le=90)):
    """Get outreach statistics for the specified period."""
    db = get_service_client()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # Total sent
    sent = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .gte("sent_at", cutoff)
        .in_("status", ["sent", "delivered", "opened", "clicked", "replied"])
        .execute()
    )

    # Replies
    replies = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("status", "replied")
        .gte("sent_at", cutoff)
        .execute()
    )

    # Positive replies
    positive = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("response_sentiment", "positive")
        .gte("sent_at", cutoff)
        .execute()
    )

    # Meetings
    meetings = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("meeting_booked", True)
        .gte("sent_at", cutoff)
        .execute()
    )

    total_sent = sent.count or 0
    total_replies = replies.count or 0

    return {
        "period_days": days,
        "total_sent": total_sent,
        "total_replies": total_replies,
        "positive_replies": positive.count or 0,
        "meetings_booked": meetings.count or 0,
        "reply_rate": round(total_replies / total_sent * 100, 1) if total_sent > 0 else 0,
    }
