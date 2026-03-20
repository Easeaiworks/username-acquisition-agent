"""
Daily Scan Scheduler — orchestrates the autonomous daily pipeline.

Runs via APScheduler on Railway. The daily cycle:
1. Handle scanning for discovered companies (Tier 1)
2. Scoring scanned companies (Tier 2)
3. Auto-enrichment for top leads (Tier 3)
4. Auto-outreach for Critical/Very High leads
5. Follow-up processing for active sequences
6. Daily report generation (Phase 7 — TODO)
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from app.config import settings

import structlog

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()


async def run_daily_pipeline_job():
    """Execute the full daily autonomous pipeline via scheduler."""
    start_time = datetime.utcnow()
    logger.info("daily_pipeline_started", time=start_time.isoformat())

    try:
        # Steps 1-3: Scan → Score → Enrich
        from app.engine_a.pipeline import run_daily_pipeline
        pipeline_result = await run_daily_pipeline()

        # Step 4: Auto-outreach for qualified companies
        logger.info("daily_phase_4_outreach")
        from app.engine_b.sequence_manager import run_auto_outreach
        outreach_result = await run_auto_outreach(
            threshold=settings.auto_outreach_threshold,
        )

        # Step 5: Process follow-ups for active sequences
        logger.info("daily_phase_5_followups")
        from app.engine_b.sequence_manager import process_followups
        followup_result = await process_followups()

        # Step 6: Generate daily report
        logger.info("daily_phase_6_report")
        # TODO: Implement in Phase 7

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            "daily_pipeline_completed",
            elapsed_seconds=round(elapsed, 1),
            scan_result=pipeline_result.get("scan", {}),
            scoring_result=pipeline_result.get("scoring", {}),
            enrichment_result=pipeline_result.get("enrichment", {}),
            outreach_result=outreach_result,
            followup_result=followup_result,
        )

    except Exception as e:
        logger.error("daily_pipeline_failed", error=str(e))
        raise


def start_scheduler():
    """Start the APScheduler with the daily scan job."""
    scheduler.add_job(
        run_daily_pipeline_job,
        trigger=CronTrigger(
            hour=settings.daily_scan_hour,
            minute=settings.daily_scan_minute,
        ),
        id="daily_pipeline",
        name="Daily Opportunity Scanner Pipeline",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "scheduler_started",
        scan_time=f"{settings.daily_scan_hour:02d}:{settings.daily_scan_minute:02d}",
    )


def stop_scheduler():
    """Gracefully stop the scheduler."""
    scheduler.shutdown()
    logger.info("scheduler_stopped")
