"""
Company API routes — CRUD operations and pipeline management.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from typing import Optional
from datetime import datetime

from app.database import get_service_client
from app.models.company import (
    Company,
    CompanyCreate,
    CompanyUpdate,
    CompanyListResponse,
    PipelineStage,
    PriorityBucket,
)
from app.engine_a.company_discovery import import_companies_from_csv

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/", response_model=CompanyListResponse)
async def list_companies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    pipeline_stage: Optional[PipelineStage] = None,
    priority_bucket: Optional[PriorityBucket] = None,
    min_score: Optional[float] = None,
    search: Optional[str] = None,
    sort_by: str = Query(default="total_opportunity_score"),
    sort_desc: bool = True,
):
    """List companies with filtering, sorting, and pagination."""
    db = get_service_client()
    offset = (page - 1) * page_size

    query = db.table("companies").select("*", count="exact")

    if pipeline_stage:
        query = query.eq("pipeline_stage", pipeline_stage.value)
    if priority_bucket:
        query = query.eq("priority_bucket", priority_bucket.value)
    if min_score is not None:
        query = query.gte("total_opportunity_score", min_score)
    if search:
        query = query.or_(f"brand_name.ilike.%{search}%,domain.ilike.%{search}%,legal_name.ilike.%{search}%")

    query = query.order(sort_by, desc=sort_desc)
    query = query.range(offset, offset + page_size - 1)

    result = query.execute()

    return CompanyListResponse(
        data=[Company(**row) for row in result.data],
        count=result.count or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/{company_id}", response_model=Company)
async def get_company(company_id: str):
    """Get a single company by ID."""
    db = get_service_client()
    result = db.table("companies").select("*").eq("id", company_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")

    return Company(**result.data[0])


@router.post("/", response_model=Company)
async def create_company(company: CompanyCreate):
    """Create a new company record."""
    db = get_service_client()

    record = company.model_dump(exclude_none=True)
    record["created_at"] = datetime.utcnow().isoformat()
    record["updated_at"] = datetime.utcnow().isoformat()
    record["pipeline_stage"] = "discovered"

    result = db.table("companies").insert(record).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create company")

    logger.info("company_created", brand=company.brand_name)
    return Company(**result.data[0])


@router.patch("/{company_id}", response_model=Company)
async def update_company(company_id: str, update: CompanyUpdate):
    """Update a company record."""
    db = get_service_client()

    data = update.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = (
        db.table("companies")
        .update(data)
        .eq("id", company_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")

    return Company(**result.data[0])


@router.post("/{company_id}/approve")
async def approve_for_outreach(company_id: str):
    """Approve a company for outreach (from the approval queue)."""
    db = get_service_client()

    result = (
        db.table("companies")
        .update({
            "approved_for_outreach": True,
            "pipeline_stage": "qualified",
        })
        .eq("id", company_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")

    logger.info("company_approved_for_outreach", company_id=company_id)
    return {"status": "approved", "company_id": company_id}


@router.post("/{company_id}/reject")
async def reject_for_outreach(company_id: str):
    """Reject a company from the outreach queue."""
    db = get_service_client()

    result = (
        db.table("companies")
        .update({
            "approved_for_outreach": False,
            "pipeline_stage": "scored",
            "notes": "Rejected from outreach queue",
        })
        .eq("id", company_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")

    logger.info("company_rejected_from_outreach", company_id=company_id)
    return {"status": "rejected", "company_id": company_id}


@router.post("/import/csv")
async def import_csv(file: UploadFile = File(...)):
    """Import companies from a CSV file upload."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    csv_content = content.decode("utf-8")

    stats = await import_companies_from_csv(
        csv_content=csv_content,
        source=f"csv_upload:{file.filename}",
    )

    return stats


@router.get("/pipeline/summary")
async def pipeline_summary():
    """Get a summary of companies by pipeline stage."""
    db = get_service_client()

    stages = [stage.value for stage in PipelineStage]
    summary = {}

    for stage in stages:
        result = (
            db.table("companies")
            .select("id", count="exact")
            .eq("pipeline_stage", stage)
            .execute()
        )
        summary[stage] = result.count or 0

    # Also get counts by priority bucket
    buckets = {}
    for bucket in PriorityBucket:
        result = (
            db.table("companies")
            .select("id", count="exact")
            .eq("priority_bucket", bucket.value)
            .execute()
        )
        buckets[bucket.value] = result.count or 0

    return {
        "pipeline_stages": summary,
        "priority_buckets": buckets,
        "total_companies": sum(summary.values()),
    }
