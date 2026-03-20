"""
Enrichment API routes — trigger contact enrichment and view results.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional

from app.database import get_service_client
from app.engine_b.enrichment import (
    enrich_company_contacts,
    enrich_batch,
)

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/enrichment", tags=["enrichment"])


@router.post("/run")
async def trigger_enrichment_run(
    background_tasks: BackgroundTasks,
    min_score: float = Query(default=0.5, ge=0.0, le=1.0),
    limit: int = Query(default=100, ge=1, le=500),
):
    """
    Trigger enrichment for scored companies above the score threshold.

    Runs in the background. Check individual company contacts for results.
    """
    db = get_service_client()

    result = (
        db.table("companies")
        .select("*")
        .eq("pipeline_stage", "scored")
        .gte("total_opportunity_score", min_score)
        .order("total_opportunity_score", desc=True)
        .limit(limit)
        .execute()
    )

    companies = result.data
    if not companies:
        return {
            "status": "no_companies",
            "message": f"No scored companies above {min_score} threshold",
        }

    background_tasks.add_task(_run_enrichment_batch, companies)

    return {
        "status": "started",
        "companies_queued": len(companies),
        "min_score": min_score,
        "message": f"Enriching {len(companies)} companies in the background",
    }


async def _run_enrichment_batch(companies: list[dict]):
    """Background task to enrich a batch of companies."""
    try:
        results = await enrich_batch(companies)
        total_contacts = sum(r.get("contacts_saved", 0) for r in results)
        logger.info(
            "background_enrichment_complete",
            companies=len(companies),
            total_contacts=total_contacts,
        )
    except Exception as e:
        logger.error("background_enrichment_error", error=str(e))


@router.post("/{company_id}")
async def enrich_single_company(
    company_id: str,
    max_contacts: int = Query(default=5, ge=1, le=20),
):
    """Enrich contacts for a single company."""
    db = get_service_client()
    result = db.table("companies").select("*").eq("id", company_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")

    company = result.data[0]
    enrichment_result = await enrich_company_contacts(
        company=company,
        max_contacts=max_contacts,
    )

    return enrichment_result


@router.get("/{company_id}/contacts")
async def get_company_contacts(company_id: str):
    """Get all enriched contacts for a company."""
    db = get_service_client()

    # Verify company exists
    company = db.table("companies").select("id, brand_name").eq("id", company_id).execute()
    if not company.data:
        raise HTTPException(status_code=404, detail="Company not found")

    contacts = (
        db.table("contacts")
        .select("*")
        .eq("company_id", company_id)
        .order("outreach_priority", desc=False)
        .execute()
    )

    return {
        "company_id": company_id,
        "brand_name": company.data[0].get("brand_name"),
        "contacts": contacts.data,
        "total": len(contacts.data),
    }


@router.get("/stats/summary")
async def enrichment_stats():
    """Get enrichment statistics."""
    db = get_service_client()

    total_contacts = (
        db.table("contacts")
        .select("id", count="exact")
        .execute()
    )

    with_email = (
        db.table("contacts")
        .select("id", count="exact")
        .neq("email", None)
        .execute()
    )

    enriched_companies = (
        db.table("companies")
        .select("id", count="exact")
        .in_("pipeline_stage", ["enriching", "qualified", "outreach", "meeting"])
        .execute()
    )

    return {
        "total_contacts": total_contacts.count or 0,
        "contacts_with_email": with_email.count or 0,
        "enriched_companies": enriched_companies.count or 0,
    }
