"""
Daily Scan Scheduler — orchestrates the autonomous daily pipeline.

Runs via APScheduler on Railway. The daily cycle:
1. Handle scanning for discovered companies (Tier 1)
2. Scoring scanned companies (Tier 2)
3. Auto-enrichment for top leads (Phase 4 — TODO)
4. Auto-outreach for Critical/Very High leads (Phase 5 — TODO)
5. Follow-up scheduling (Phase 5 — TODO)
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
        from app.engine_a.pipeline import run_daily_pipeline
        result = await run_daily_pipeline()

        # Phase 3: Enrich top leads
        logger.info("daily_phase_3_enrichment")
        # TODO: Implement in Phase 4
        # from app.engine_b.pipeline import run_enrichment
        # enrich_results = await run_enrichment()

        # Phase 4: Auto-outreach for high-scoring leads
        logger.info("daily_phase_4_outreach")
        # TODO: Implement in Phase 5
        # from app.engine_b.pipeline import run_auto_outreach
        # outreach_results = await run_auto_outreach(
        #     threshold=settings.auto_outreach_threshold
        # )

        # Phase 5: Process follow-ups
        logger.info("daily_phase_5_followups")
        # TODO: Implement in Phase 5

        # Phase 6: Generate daily report
        logger.info("daily_phase_6_report")
        # TODO: Implement in Phase 7

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            "daily_pipeline_completed",
            elapsed_seconds=round(elapsed, 1),
            scan_result=result.get("scan", {}),
            scoring_result=result.get("scoring", {}),
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
