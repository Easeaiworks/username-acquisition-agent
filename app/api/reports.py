"""
Reporting API routes — daily reports, historical trends, and on-demand generation.
"""

from fastapi import APIRouter, Query, BackgroundTasks
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_service_client
from app.reporting.collector import collect_full_daily_report
from app.reporting.formatter import (
    format_text_summary,
    format_html_email,
    generate_and_persist_report,
)

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/generate")
async def generate_report(background_tasks: BackgroundTasks):
    """Generate today's daily report in the background."""
    background_tasks.add_task(generate_and_persist_report)
    return {"status": "generating", "message": "Daily report generation started"}


@router.get("/today")
async def get_today_report():
    """Get or generate today's report."""
    report = await collect_full_daily_report()
    text_summary = format_text_summary(report)
    return {
        "report": report,
        "text_summary": text_summary,
    }


@router.get("/latest")
async def get_latest_report():
    """Get the most recently persisted daily report."""
    db = get_service_client()
    result = (
        db.table("daily_reports")
        .select("*")
        .order("report_date", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return {"message": "No reports generated yet. Run POST /api/reports/generate first."}
    return result.data[0]


@router.get("/history")
async def get_report_history(
    days: int = Query(default=30, ge=1, le=365),
):
    """Get historical daily report summaries for trend analysis."""
    db = get_service_client()
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    result = (
        db.table("daily_reports")
        .select(
            "report_date, pipeline_total, new_companies, scored_today, "
            "emails_sent, replies_received, reply_rate, meetings_booked, "
            "attention_items, avg_score"
        )
        .gte("report_date", cutoff)
        .order("report_date", desc=False)
        .execute()
    )

    return {
        "period_days": days,
        "reports": result.data or [],
        "count": len(result.data or []),
    }


@router.get("/trends")
async def get_trends(
    days: int = Query(default=14, ge=7, le=90),
):
    """Calculate trend metrics over the specified period."""
    db = get_service_client()
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    midpoint = (datetime.utcnow() - timedelta(days=days // 2)).strftime("%Y-%m-%d")

    # Get all reports in range
    result = (
        db.table("daily_reports")
        .select(
            "report_date, pipeline_total, new_companies, emails_sent, "
            "replies_received, meetings_booked, avg_score"
        )
        .gte("report_date", cutoff)
        .order("report_date", desc=False)
        .execute()
    )

    reports = result.data or []
    if len(reports) < 2:
        return {"message": "Not enough data for trend analysis", "period_days": days}

    # Split into first half and second half
    first_half = [r for r in reports if r["report_date"] < midpoint]
    second_half = [r for r in reports if r["report_date"] >= midpoint]

    def avg(items, key):
        vals = [i.get(key, 0) or 0 for i in items]
        return round(sum(vals) / len(vals), 2) if vals else 0

    def trend(first, second):
        if first == 0:
            return 100.0 if second > 0 else 0.0
        return round((second - first) / first * 100, 1)

    first_avg_sent = avg(first_half, "emails_sent")
    second_avg_sent = avg(second_half, "emails_sent")
    first_avg_replies = avg(first_half, "replies_received")
    second_avg_replies = avg(second_half, "replies_received")
    first_avg_meetings = avg(first_half, "meetings_booked")
    second_avg_meetings = avg(second_half, "meetings_booked")
    first_avg_score = avg(first_half, "avg_score")
    second_avg_score = avg(second_half, "avg_score")

    return {
        "period_days": days,
        "data_points": len(reports),
        "trends": {
            "emails_sent": {
                "current_avg": second_avg_sent,
                "previous_avg": first_avg_sent,
                "change_pct": trend(first_avg_sent, second_avg_sent),
            },
            "replies": {
                "current_avg": second_avg_replies,
                "previous_avg": first_avg_replies,
                "change_pct": trend(first_avg_replies, second_avg_replies),
            },
            "meetings": {
                "current_avg": second_avg_meetings,
                "previous_avg": first_avg_meetings,
                "change_pct": trend(first_avg_meetings, second_avg_meetings),
            },
            "avg_score": {
                "current_avg": second_avg_score,
                "previous_avg": first_avg_score,
                "change_pct": trend(first_avg_score, second_avg_score),
            },
        },
        "totals": {
            "total_emails": sum((r.get("emails_sent", 0) or 0) for r in reports),
            "total_replies": sum((r.get("replies_received", 0) or 0) for r in reports),
            "total_meetings": sum((r.get("meetings_booked", 0) or 0) for r in reports),
            "total_new_companies": sum((r.get("new_companies", 0) or 0) for r in reports),
        },
    }


@router.get("/{report_date}")
async def get_report_by_date(report_date: str):
    """Get a specific daily report by date (YYYY-MM-DD)."""
    db = get_service_client()
    result = (
        db.table("daily_reports")
        .select("*")
        .eq("report_date", report_date)
        .execute()
    )
    if not result.data:
        return {"message": f"No report found for {report_date}"}
    return result.data[0]
