"""
Engine A Pipeline — orchestrates the full Tier 1→2→3 scanning flow.

Tier 1: Cheap, broad scan (thousands of companies/day)
    - CSV import → brand normalization → handle scanning across all platforms
    - Cost: ~$0.01 per company (mostly free API calls)

Tier 2: Selective enrichment (top 10-20% by score)
    - Score each company → enrich contacts for high-scorers
    - Cost: ~$0.10-0.50 per company (RocketReach/Hunter credits)

Tier 3: Human-reviewed outbound (top opportunities)
    - Generate outreach → approval queue → send sequences
    - Cost: ~$0.50-2.00 per company (Claude copy generation + email sending)

This module runs the Tier 1 scanning pipeline and prepares companies
for Tier 2 scoring (Phase 3).
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import structlog

from app.config import settings
from app.database import get_service_client
from app.engine_a.company_discovery import get_companies_for_scanning
from app.engine_a.handle_scanner import scan_batch
from app.engine_a.scoring import score_batch, get_scoring_summary
from app.models.platform_handle import Platform

logger = structlog.get_logger()

# Batch sizes
SCAN_BATCH_SIZE = 50       # Companies per batch
SCAN_CONCURRENCY = 5       # Concurrent company scans per batch
MAX_DAILY_SCANS = 2000     # Safety limit


async def run_tier1_scan(
    limit: Optional[int] = None,
    platforms: Optional[list[Platform]] = None,
) -> dict:
    """
    Run the full Tier 1 scanning pipeline.

    1. Fetch companies in 'discovered' stage
    2. Scan each company across all platforms
    3. Store results and advance pipeline stage

    Args:
        limit: Max companies to scan (default: MAX_DAILY_SCANS)
        platforms: Which platforms to scan (default: all)

    Returns:
        Pipeline run summary dict
    """
    start_time = datetime.now(timezone.utc)
    limit = limit or MAX_DAILY_SCANS

    logger.info("tier1_scan_starting", limit=limit)

    # Fetch companies that need scanning
    companies = await get_companies_for_scanning(limit=limit, stage="discovered")

    if not companies:
        logger.info("tier1_no_companies_to_scan")
        return {
            "status": "completed",
            "companies_scanned": 0,
            "companies_available": 0,
            "duration_secs": 0,
        }

    logger.info("tier1_companies_loaded", count=len(companies))

    # Process in batches
    all_results = []
    total_scanned = 0
    total_errors = 0

    for batch_start in range(0, len(companies), SCAN_BATCH_SIZE):
        batch = companies[batch_start:batch_start + SCAN_BATCH_SIZE]
        batch_num = (batch_start // SCAN_BATCH_SIZE) + 1

        logger.info(
            "tier1_batch_start",
            batch_num=batch_num,
            batch_size=len(batch),
        )

        batch_results = await scan_batch(
            companies=batch,
            platforms=platforms,
            concurrency=SCAN_CONCURRENCY,
        )

        for result in batch_results:
            if "error" in result:
                total_errors += 1
            else:
                total_scanned += 1

        all_results.extend(batch_results)

        # Brief pause between batches to be nice to APIs
        if batch_start + SCAN_BATCH_SIZE < len(companies):
            await asyncio.sleep(2)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    # Calculate summary stats
    severity_scores = [
        r.get("cross_platform_severity", 0)
        for r in all_results
        if "error" not in r
    ]
    high_value_count = sum(1 for s in severity_scores if s >= 0.5)

    summary = {
        "status": "completed",
        "companies_available": len(companies),
        "companies_scanned": total_scanned,
        "companies_errored": total_errors,
        "high_value_opportunities": high_value_count,
        "avg_severity": round(sum(severity_scores) / len(severity_scores), 3) if severity_scores else 0,
        "max_severity": round(max(severity_scores), 3) if severity_scores else 0,
        "duration_secs": round(elapsed, 2),
    }

    logger.info("tier1_scan_complete", **summary)

    # Store pipeline run metadata
    await _record_pipeline_run("tier1_scan", summary)

    return summary


async def run_tier2_scoring(limit: int = 500) -> dict:
    """
    Run Tier 2 scoring on all scanned companies.

    Fetches companies in the 'scanned' stage and runs the weighted
    scoring model on each. Results are persisted and companies advance
    to the 'scored' stage.

    Args:
        limit: Max companies to score

    Returns:
        Scoring run summary dict
    """
    start_time = datetime.now(timezone.utc)

    logger.info("tier2_scoring_starting", limit=limit)

    try:
        db = get_service_client()
        result = (
            db.table("companies")
            .select("*")
            .eq("pipeline_stage", "scanned")
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        companies = result.data
    except Exception as e:
        logger.error("tier2_fetch_error", error=str(e))
        return {"status": "error", "error": str(e)}

    if not companies:
        logger.info("tier2_no_companies_to_score")
        return {"status": "completed", "companies_scored": 0}

    scored_results = await score_batch(companies, concurrency=10)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    # Classify results by bucket
    bucket_counts = {}
    for r in scored_results:
        bucket = r.get("priority_bucket", "unknown")
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    summary = {
        "status": "completed",
        "companies_available": len(companies),
        "companies_scored": len(scored_results),
        "bucket_distribution": bucket_counts,
        "duration_secs": round(elapsed, 2),
    }

    logger.info("tier2_scoring_complete", **summary)
    await _record_pipeline_run("tier2_scoring", summary)

    return summary


async def run_daily_pipeline() -> dict:
    """
    Run the full daily pipeline: Tier 1 scan → Tier 2 scoring.

    This is the main entry point called by the APScheduler cron job.
    Future phases will add enrichment and outreach steps.

    Returns:
        Combined pipeline run summary
    """
    logger.info("daily_pipeline_starting")
    start_time = datetime.now(timezone.utc)

    # Step 1: Scan new companies
    scan_result = await run_tier1_scan()

    # Step 2: Score all scanned companies
    score_result = await run_tier2_scoring()

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    summary = {
        "status": "completed",
        "scan": scan_result,
        "scoring": score_result,
        "total_duration_secs": round(elapsed, 2),
    }

    logger.info("daily_pipeline_complete", duration_secs=round(elapsed, 2))
    await _record_pipeline_run("daily_pipeline", summary)

    return summary


async def run_rescan_stale(
    days_stale: int = 30,
    limit: int = 200,
) -> dict:
    """
    Re-scan companies whose handle data is stale.

    Useful for catching dormant accounts that have become newly inactive,
    or handles that have been released.

    Args:
        days_stale: Consider data older than this many days as stale
        limit: Max companies to rescan

    Returns:
        Pipeline run summary dict
    """
    try:
        db = get_service_client()

        # Find companies that were scanned but not recently
        cutoff = datetime.now(timezone.utc).isoformat()

        result = (
            db.table("companies")
            .select("*")
            .eq("pipeline_stage", "scanned")
            .lt("scanned_at", cutoff)
            .order("scanned_at", desc=False)
            .limit(limit)
            .execute()
        )

        companies = result.data

        if not companies:
            return {"status": "completed", "companies_rescanned": 0}

        logger.info("rescan_stale_starting", count=len(companies))

        # Reset their stage so the scanner picks them up
        for company in companies:
            db.table("companies").update({
                "pipeline_stage": "discovered",
            }).eq("id", company["id"]).execute()

        # Now run the regular scan
        return await run_tier1_scan(limit=len(companies))

    except Exception as e:
        logger.error("rescan_stale_error", error=str(e))
        return {"status": "error", "error": str(e)}


async def get_pipeline_stats() -> dict:
    """
    Get current pipeline statistics across all stages.

    Returns:
        Dict with counts per stage and overall metrics
    """
    try:
        db = get_service_client()

        # Count by pipeline stage
        stages = ["discovered", "scanned", "scored", "enriching", "qualified", "outreach", "meeting", "closed"]
        counts = {}

        for stage in stages:
            result = (
                db.table("companies")
                .select("id", count="exact")
                .eq("pipeline_stage", stage)
                .execute()
            )
            counts[stage] = result.count or 0

        # High-value opportunities (scored >= 0.5)
        high_value = (
            db.table("companies")
            .select("id", count="exact")
            .gte("total_opportunity_score", 0.5)
            .execute()
        )

        # Approval queue
        approval_queue = (
            db.table("companies")
            .select("id", count="exact")
            .eq("pipeline_stage", "qualified")
            .eq("approved_for_outreach", False)
            .execute()
        )

        return {
            "stage_counts": counts,
            "total_companies": sum(counts.values()),
            "high_value_opportunities": high_value.count or 0,
            "approval_queue_size": approval_queue.count or 0,
        }

    except Exception as e:
        logger.error("pipeline_stats_error", error=str(e))
        return {"error": str(e)}


async def _record_pipeline_run(run_type: str, summary: dict) -> None:
    """Record a pipeline run in the audit log for tracking."""
    try:
        db = get_service_client()
        db.table("audit_log").insert({
            "action": run_type,
            "details": summary,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.error("record_pipeline_run_error", error=str(e))
