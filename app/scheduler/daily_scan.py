"""
Daily Scan Scheduler — orchestrates the autonomous daily pipeline.

Runs via APScheduler on Railway. The daily cycle:
1. Company discovery (if automated sources configured)
2. Handle scanning for discovered companies
3. Scoring
4. Auto-enrichment for Tier 2 leads
5. Auto-outreach for Critical/Very High leads
6. Follow-up scheduling
7. Daily report generation
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from app.config import settings

import structlog

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()


async def run_daily_pipeline():
    """Execute the full daily autonomous pipeline."""
    start_time = datetime.utcnow()
    logger.info("daily_pipeline_started", time=start_time.isoformat())

    try:
        # Phase 1: Scan discovered companies
        logger.info("daily_phase_1_scanning")
        # TODO: Implement in Phase 2
        # from app.engine_a.pipeline import run_tier1_scan
        # scan_results = await run_tier1_scan()

        # Phase 2: Score scanned companies
        logger.info("daily_phase_2_scoring")
        # TODO: Implement in Phase 3
        # from app.engine_a.pipeline import run_scoring
        # score_results = await run_scoring()

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
        # from app.engine_b.sequence_manager import process_followups
        # await process_followups()

        # Phase 6: Generate daily report
        logger.info("daily_phase_6_report")
        # TODO: Implement in Phase 7
        # from app.scheduler.report_generator import generate_daily_report
        # await generate_daily_report()

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info("daily_pipeline_completed", elapsed_seconds=round(elapsed, 1))

    except Exception as e:
        logger.error("daily_pipeline_failed", error=str(e))
        raise


def start_scheduler():
    """Start the APScheduler with the daily scan job."""
    scheduler.add_job(
        run_daily_pipeline,
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
