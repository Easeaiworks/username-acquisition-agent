"""
Daily Report Data Collector — gathers metrics from all pipeline stages.

Collects:
- Pipeline throughput: companies scanned, scored, enriched, contacted today
- Scoring distribution: bucket counts and movements since last report
- Outreach performance: emails sent, replies, positive replies, meetings
- Top new opportunities discovered today
- Stale/blocked items needing attention
- API usage and rate limit status
"""

from datetime import datetime, timedelta
from typing import Any

from app.database import get_service_client

import structlog

logger = structlog.get_logger()


async def collect_pipeline_metrics(
    report_date: datetime | None = None,
) -> dict[str, Any]:
    """Collect pipeline throughput metrics for a single day."""
    db = get_service_client()
    date = report_date or datetime.utcnow()
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    start_iso = day_start.isoformat()
    end_iso = day_end.isoformat()

    # Total companies by stage
    stages = {}
    for stage in [
        "new", "scanned", "scored", "enriched", "qualified",
        "approval_queue", "outreach_active", "meeting_booked",
        "rejected", "parked",
    ]:
        result = (
            db.table("companies")
            .select("id", count="exact")
            .eq("pipeline_stage", stage)
            .execute()
        )
        stages[stage] = result.count or 0

    total = sum(stages.values())

    # Companies that moved stages today (updated_at within the day)
    moved_today = (
        db.table("companies")
        .select("id", count="exact")
        .gte("updated_at", start_iso)
        .lt("updated_at", end_iso)
        .execute()
    )

    # New companies discovered today
    new_today = (
        db.table("companies")
        .select("id", count="exact")
        .gte("created_at", start_iso)
        .lt("created_at", end_iso)
        .execute()
    )

    return {
        "date": day_start.strftime("%Y-%m-%d"),
        "total_companies": total,
        "stage_breakdown": stages,
        "new_companies_today": new_today.count or 0,
        "stage_movements_today": moved_today.count or 0,
    }


async def collect_scoring_metrics(
    report_date: datetime | None = None,
) -> dict[str, Any]:
    """Collect scoring distribution and quality metrics."""
    db = get_service_client()
    date = report_date or datetime.utcnow()
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    start_iso = day_start.isoformat()
    end_iso = day_end.isoformat()

    # Priority bucket distribution
    buckets = {}
    for bucket in ["critical", "very_high", "high", "medium", "low"]:
        result = (
            db.table("companies")
            .select("id", count="exact")
            .eq("priority_bucket", bucket)
            .execute()
        )
        buckets[bucket] = result.count or 0

    # Scored today
    scored_today = (
        db.table("companies")
        .select("id", count="exact")
        .gte("scored_at", start_iso)
        .lt("scored_at", end_iso)
        .execute()
    )

    # Average score of companies scored today
    scored_results = (
        db.table("companies")
        .select("composite_score")
        .gte("scored_at", start_iso)
        .lt("scored_at", end_iso)
        .execute()
    )
    scores = [r["composite_score"] for r in (scored_results.data or []) if r.get("composite_score")]
    avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    return {
        "priority_distribution": buckets,
        "scored_today": scored_today.count or 0,
        "avg_score_today": avg_score,
        "high_value_today": sum(1 for s in scores if s >= 0.65),
    }


async def collect_outreach_metrics(
    report_date: datetime | None = None,
) -> dict[str, Any]:
    """Collect outreach performance metrics."""
    db = get_service_client()
    date = report_date or datetime.utcnow()
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    start_iso = day_start.isoformat()
    end_iso = day_end.isoformat()

    # Emails sent today
    sent_today = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .gte("sent_at", start_iso)
        .lt("sent_at", end_iso)
        .execute()
    )

    # Replies received today
    replies_today = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("status", "replied")
        .gte("response_classified_at", start_iso)
        .lt("response_classified_at", end_iso)
        .execute()
    )

    # Reply classification breakdown for today
    classifications = {}
    for category in ["positive", "neutral", "negative", "objection", "ooo", "unsubscribe"]:
        result = (
            db.table("outreach_sequences")
            .select("id", count="exact")
            .eq("response_sentiment", category)
            .gte("response_classified_at", start_iso)
            .lt("response_classified_at", end_iso)
            .execute()
        )
        classifications[category] = result.count or 0

    # Meetings booked today
    meetings_today = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("meeting_booked", True)
        .gte("updated_at", start_iso)
        .lt("updated_at", end_iso)
        .execute()
    )

    # Bounces today
    bounces_today = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("status", "bounced")
        .gte("updated_at", start_iso)
        .lt("updated_at", end_iso)
        .execute()
    )

    # Active sequences total
    active_total = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .in_("status", ["sent", "delivered", "opened"])
        .execute()
    )

    total_sent = sent_today.count or 0
    total_replies = replies_today.count or 0

    return {
        "sent_today": total_sent,
        "replies_today": total_replies,
        "reply_rate_today": round(total_replies / total_sent * 100, 1) if total_sent > 0 else 0.0,
        "reply_classifications": classifications,
        "meetings_booked_today": meetings_today.count or 0,
        "bounces_today": bounces_today.count or 0,
        "active_sequences_total": active_total.count or 0,
    }


async def collect_top_opportunities(
    report_date: datetime | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Get today's top newly scored opportunities."""
    db = get_service_client()
    date = report_date or datetime.utcnow()
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    result = (
        db.table("companies")
        .select("id, brand_name, domain, industry, composite_score, priority_bucket, pipeline_stage")
        .gte("scored_at", day_start.isoformat())
        .lt("scored_at", day_end.isoformat())
        .order("composite_score", desc=True)
        .limit(limit)
        .execute()
    )

    return result.data or []


async def collect_attention_items() -> dict[str, Any]:
    """Identify items that need human attention."""
    db = get_service_client()

    # Pending approvals
    pending = (
        db.table("companies")
        .select("id", count="exact")
        .eq("pipeline_stage", "approval_queue")
        .execute()
    )

    # Stale sequences (sent > 7 days, no reply)
    stale_cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    stale = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("status", "sent")
        .lt("sent_at", stale_cutoff)
        .execute()
    )

    # Objections needing review
    objections = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("response_sentiment", "objection")
        .eq("reviewed", False)
        .execute()
    )

    # Positive replies not yet followed up
    hot_leads = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("response_sentiment", "positive")
        .eq("meeting_booked", False)
        .execute()
    )

    return {
        "pending_approvals": pending.count or 0,
        "stale_sequences": stale.count or 0,
        "unreviewed_objections": objections.count or 0,
        "hot_leads_no_meeting": hot_leads.count or 0,
    }


async def collect_full_daily_report(
    report_date: datetime | None = None,
) -> dict[str, Any]:
    """Collect all metrics into a single daily report payload."""
    date = report_date or datetime.utcnow()

    pipeline = await collect_pipeline_metrics(date)
    scoring = await collect_scoring_metrics(date)
    outreach = await collect_outreach_metrics(date)
    top_opps = await collect_top_opportunities(date)
    attention = await collect_attention_items()

    report = {
        "report_date": pipeline["date"],
        "generated_at": datetime.utcnow().isoformat(),
        "pipeline": pipeline,
        "scoring": scoring,
        "outreach": outreach,
        "top_opportunities": top_opps,
        "attention_required": attention,
        "health": {
            "total_attention_items": sum(attention.values()),
            "pipeline_active": pipeline["total_companies"] > 0,
            "outreach_active": outreach["active_sequences_total"] > 0,
        },
    }

    logger.info(
        "daily_report_collected",
        date=pipeline["date"],
        total_companies=pipeline["total_companies"],
        sent_today=outreach["sent_today"],
        meetings_today=outreach["meetings_booked_today"],
    )

    return report
