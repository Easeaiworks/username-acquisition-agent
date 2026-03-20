"""
Handle Scanner — orchestrates handle lookups across all four platforms.

For each company, the scanner:
1. Generates the ideal handle slug from the brand name
2. Generates candidate handles (exact match + common modifiers)
3. Checks each platform for the exact brand handle
4. If the brand already has a presence, checks their current handle
5. Runs mismatch detection and dormancy analysis
6. Stores results in the platform_handles table

This is the core Tier 1 scanning engine. It's designed to be called per-company
and is orchestrated by the pipeline module for batch processing.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import structlog

from app.config import settings
from app.database import get_service_client
from app.engine_a.brand_normalizer import generate_handle_slug
from app.engine_a.handle_candidates import generate_candidates
from app.engine_a.mismatch_detector import detect_mismatch, calculate_cross_platform_severity
from app.integrations.youtube import lookup_channel_by_handle, check_handle_availability as yt_check
from app.integrations.twitch import lookup_user_by_login, check_handle_availability as tw_check
from app.integrations.apify import (
    check_instagram_handle,
    check_tiktok_handle,
)
from app.models.platform_handle import Platform, MismatchType

logger = structlog.get_logger()

# Platform checker registry — maps platform enum to check function
PLATFORM_CHECKERS = {
    Platform.YOUTUBE: yt_check,
    Platform.TWITCH: tw_check,
    Platform.INSTAGRAM: check_instagram_handle,
    Platform.TIKTOK: check_tiktok_handle,
}


async def scan_company_handles(
    company_id: str,
    brand_name: str,
    domain: Optional[str] = None,
    platforms: Optional[list[Platform]] = None,
    save_results: bool = True,
) -> dict:
    """
    Scan all platforms for a company's handle status.

    This is the main entry point for Tier 1 scanning.

    Args:
        company_id: Supabase company ID
        brand_name: The company's brand name
        domain: Company domain (for extra context)
        platforms: Which platforms to scan (default: all four)
        save_results: Whether to persist results to DB

    Returns:
        {
            "company_id": str,
            "brand_slug": str,
            "platforms": {platform: handle_result, ...},
            "cross_platform_severity": float,
            "scan_duration_secs": float,
        }
    """
    start_time = datetime.now(timezone.utc)
    platforms = platforms or list(Platform)
    brand_slug = generate_handle_slug(brand_name)

    logger.info(
        "scan_started",
        company_id=company_id,
        brand_name=brand_name,
        brand_slug=brand_slug,
        platforms=[p.value for p in platforms],
    )

    # Scan each platform concurrently
    platform_tasks = {
        platform: _scan_single_platform(brand_slug, platform)
        for platform in platforms
    }

    # Gather results (with exception handling per platform)
    platform_results = {}
    results = await asyncio.gather(
        *platform_tasks.values(),
        return_exceptions=True,
    )

    for platform, result in zip(platform_tasks.keys(), results):
        if isinstance(result, Exception):
            logger.error(
                "platform_scan_error",
                platform=platform.value,
                brand_slug=brand_slug,
                error=str(result),
            )
            platform_results[platform.value] = {
                "error": str(result),
                "mismatch_type": MismatchType.NONE,
                "mismatch_severity": 0.0,
            }
        else:
            platform_results[platform.value] = result

    # Calculate cross-platform severity
    mismatch_records = [
        r for r in platform_results.values()
        if "error" not in r
    ]
    cross_severity = calculate_cross_platform_severity(mismatch_records)

    # Persist results
    if save_results:
        await _save_scan_results(company_id, brand_slug, platform_results)
        await _update_company_stage(company_id)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    logger.info(
        "scan_completed",
        company_id=company_id,
        brand_slug=brand_slug,
        cross_severity=round(cross_severity, 3),
        duration_secs=round(elapsed, 2),
    )

    return {
        "company_id": company_id,
        "brand_slug": brand_slug,
        "platforms": platform_results,
        "cross_platform_severity": cross_severity,
        "scan_duration_secs": round(elapsed, 2),
    }


async def _scan_single_platform(brand_slug: str, platform: Platform) -> dict:
    """
    Scan a single platform for the ideal handle.

    Steps:
    1. Check if the exact brand handle exists on the platform
    2. Analyze the result (available, taken, dormant holder, etc.)
    3. Run mismatch detection

    Returns a mismatch analysis dict.
    """
    checker = PLATFORM_CHECKERS.get(platform)
    if not checker:
        logger.warning("no_checker_for_platform", platform=platform.value)
        return {"mismatch_type": MismatchType.NONE, "mismatch_severity": 0.0}

    logger.debug("platform_scan_start", platform=platform.value, handle=brand_slug)

    # Check the exact brand handle
    check_result = await checker(brand_slug)

    available = check_result.get("available", None)
    holder_data = (
        check_result.get("user_data")
        or check_result.get("channel_data")
        or check_result.get("profile_data")
    )

    # Build holder info for mismatch detection
    holder_info = None
    if holder_data:
        holder_info = {
            "last_post_date": holder_data.get("last_post_date"),
            "follower_count": holder_data.get("follower_count") or holder_data.get("subscriber_count"),
            "post_count": holder_data.get("post_count") or holder_data.get("video_count"),
            "display_name": holder_data.get("display_name", ""),
            "description": holder_data.get("description", ""),
            "account_dormant": holder_data.get("account_dormant", False),
        }

    # Run mismatch detection
    # For now, observed_handle is None (we don't yet know what handle the brand
    # actually uses on this platform — that would require finding the brand's
    # actual account, which is a separate step). The key insight here is:
    # we're checking if the IDEAL handle is available.
    mismatch = detect_mismatch(
        brand_slug=brand_slug,
        observed_handle=None,  # TODO: Phase 3+ will find actual brand accounts
        platform=platform.value,
        account_exists=not available if available is not None else None,
        ideal_handle_available=available,
        ideal_handle_holder_info=holder_info if not available else None,
    )

    # Enrich with raw platform data
    mismatch["platform"] = platform.value
    mismatch["ideal_handle"] = brand_slug
    mismatch["handle_available"] = available
    mismatch["holder_summary"] = _summarize_holder(holder_data) if holder_data else None

    logger.debug(
        "platform_scan_done",
        platform=platform.value,
        handle=brand_slug,
        available=available,
        mismatch_type=mismatch["mismatch_type"],
        severity=mismatch["mismatch_severity"],
    )

    return mismatch


def _summarize_holder(holder_data: dict) -> dict:
    """Create a concise summary of who currently holds a handle."""
    return {
        "display_name": holder_data.get("display_name", ""),
        "description": (holder_data.get("description") or "")[:200],
        "follower_count": holder_data.get("follower_count") or holder_data.get("subscriber_count"),
        "post_count": holder_data.get("post_count") or holder_data.get("video_count"),
        "last_post_date": holder_data.get("last_post_date"),
        "account_dormant": holder_data.get("account_dormant", False),
        "is_verified": holder_data.get("is_verified", False),
    }


async def _save_scan_results(
    company_id: str,
    brand_slug: str,
    platform_results: dict,
) -> None:
    """Persist scan results to the platform_handles table."""
    try:
        supabase = get_service_client()

        for platform_name, result in platform_results.items():
            if "error" in result:
                continue

            record = {
                "company_id": company_id,
                "platform": platform_name,
                "observed_handle": None,  # Will be populated when we find brand's actual account
                "exact_match": result.get("mismatch_type") == MismatchType.NONE,
                "mismatch_type": (
                    result["mismatch_type"].value
                    if hasattr(result["mismatch_type"], "value")
                    else result["mismatch_type"]
                ),
                "mismatch_severity": result.get("mismatch_severity", 0.0),
                "handle_available": result.get("handle_available"),
                "account_dormant": result.get("account_dormant", False),
                "dormancy_months": result.get("dormancy_months"),
                "confidence": 0.8,  # Base confidence for API-sourced data
                "data_source": f"api_{platform_name}",
                "current_holder_info": result.get("holder_summary"),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

            # Upsert: update if platform+company combo already exists
            supabase.table("platform_handles").upsert(
                record,
                on_conflict="company_id,platform",
            ).execute()

        logger.info("scan_results_saved", company_id=company_id, platforms=list(platform_results.keys()))

    except Exception as e:
        logger.error("save_scan_results_error", company_id=company_id, error=str(e))


async def _update_company_stage(company_id: str) -> None:
    """Move company to 'scanned' pipeline stage after scanning completes."""
    try:
        supabase = get_service_client()
        supabase.table("companies").update({
            "pipeline_stage": "scanned",
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", company_id).execute()

    except Exception as e:
        logger.error("update_company_stage_error", company_id=company_id, error=str(e))


async def scan_batch(
    companies: list[dict],
    platforms: Optional[list[Platform]] = None,
    concurrency: int = 5,
) -> list[dict]:
    """
    Scan a batch of companies with controlled concurrency.

    Args:
        companies: List of company dicts with 'id' and 'brand_name'
        platforms: Which platforms to scan
        concurrency: Max concurrent company scans

    Returns:
        List of scan result dicts
    """
    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def _scan_with_limit(company: dict):
        async with semaphore:
            return await scan_company_handles(
                company_id=company["id"],
                brand_name=company["brand_name"],
                domain=company.get("domain"),
                platforms=platforms,
            )

    tasks = [_scan_with_limit(c) for c in companies]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Separate successes from errors
    scan_results = []
    for company, result in zip(companies, results):
        if isinstance(result, Exception):
            logger.error(
                "batch_scan_error",
                company_id=company["id"],
                error=str(result),
            )
            scan_results.append({
                "company_id": company["id"],
                "error": str(result),
            })
        else:
            scan_results.append(result)

    return scan_results
