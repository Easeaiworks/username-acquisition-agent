"""
Scoring API routes — trigger scoring runs and view results.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional

from app.database import get_service_client
from app.engine_a.scoring import (
    score_company,
    score_and_persist,
    score_batch,
    get_scoring_summary,
)

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.post("/run")
async def trigger_scoring_run(
    background_tasks: BackgroundTasks,
    limit: int = Query(default=500, ge=1, le=5000),
    min_stage: str = Query(default="scanned"),
):
    """
    Trigger a scoring run for all scanned companies.

    Runs in the background so the API returns immediately.
    Check /api/scoring/summary for results.
    """
    db = get_service_client()

    result = (
        db.table("companies")
        .select("*")
        .eq("pipeline_stage", min_stage)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )

    companies = result.data
    if not companies:
        return {"status": "no_companies", "message": f"No companies in '{min_stage}' stage"}

    # Run scoring in background
    background_tasks.add_task(_run_scoring_batch, companies)

    return {
        "status": "started",
        "companies_queued": len(companies),
        "message": f"Scoring {len(companies)} companies in the background",
    }


async def _run_scoring_batch(companies: list[dict]):
    """Background task to score a batch of companies."""
    try:
        results = await score_batch(companies)
        logger.info(
            "background_scoring_complete",
            total=len(companies),
            scored=len(results),
        )
    except Exception as e:
        logger.error("background_scoring_error", error=str(e))


@router.post("/{company_id}")
async def score_single_company(company_id: str):
    """Score a single company and persist the result."""
    db = get_service_client()
    result = db.table("companies").select("*").eq("id", company_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")

    company = result.data[0]
    scoring_result = await score_and_persist(company)

    return scoring_result


@router.get("/{company_id}")
async def get_company_score(company_id: str):
    """Get the current scoring breakdown for a company."""
    db = get_service_client()

    company = db.table("companies").select("*").eq("id", company_id).execute()
    if not company.data:
        raise HTTPException(status_code=404, detail="Company not found")

    c = company.data[0]

    # Also get handle data for context
    handles = (
        db.table("platform_handles")
        .select("*")
        .eq("company_id", company_id)
        .execute()
    )

    return {
        "company_id": company_id,
        "brand_name": c.get("brand_name"),
        "scores": {
            "brand_value": c.get("brand_value_score", 0),
            "handle_pain": c.get("handle_pain_score", 0),
            "urgency": c.get("urgency_score", 0),
            "reachability": c.get("reachability_score", 0),
            "total": c.get("total_opportunity_score", 0),
        },
        "priority_bucket": c.get("priority_bucket"),
        "pipeline_stage": c.get("pipeline_stage"),
        "urgency_signals": c.get("urgency_signals", {}),
        "platform_handles": handles.data,
    }


@router.get("/summary/distribution")
async def scoring_distribution():
    """Get the overall scoring distribution and bucket counts."""
    return await get_scoring_summary()
