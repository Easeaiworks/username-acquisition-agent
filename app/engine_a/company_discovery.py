"""
Company Discovery — finds companies to scan for handle opportunities.

Sources:
1. CSV import (manual seed lists, LinkedIn Sales Nav exports)
2. Web scraping of public directories (future: Crunchbase, Product Hunt, etc.)
3. Social platform exploration (future: find brand accounts, reverse-lookup)

For MVP, CSV import is the primary ingest method.
Additional automated discovery sources will be added in later phases.
"""

import csv
import io
from datetime import datetime
from typing import Optional

import structlog

from app.database import get_service_client
from app.engine_a.brand_normalizer import build_canonical_record

logger = structlog.get_logger()


async def import_companies_from_csv(
    csv_content: str,
    source: str = "csv_import",
    column_mapping: Optional[dict] = None,
) -> dict:
    """
    Import companies from CSV content into the database.

    Expected CSV columns (flexible mapping):
        - company_name (required)
        - legal_name (optional)
        - domain (optional)
        - industry (optional)
        - employee_range (optional)
        - country (optional)
        - city (optional)

    Args:
        csv_content: Raw CSV string content
        source: Source label for tracking
        column_mapping: Optional dict mapping CSV column names to our field names

    Returns:
        Dict with import stats: {imported, skipped, errors, total}
    """
    db = get_service_client()
    reader = csv.DictReader(io.StringIO(csv_content))

    # Default column mapping
    mapping = {
        "company_name": "company_name",
        "legal_name": "legal_name",
        "domain": "domain",
        "industry": "industry",
        "employee_range": "employee_range",
        "country": "country",
        "city": "city",
        "vertical": "vertical",
        "founding_year": "founding_year",
    }
    if column_mapping:
        mapping.update(column_mapping)

    stats = {"imported": 0, "skipped": 0, "errors": 0, "total": 0}

    for row in reader:
        stats["total"] += 1

        try:
            # Get company name from mapped column
            raw_name = None
            for possible_key in ["company_name", "name", "company", "brand", "brand_name"]:
                mapped_key = mapping.get(possible_key, possible_key)
                if mapped_key in row and row[mapped_key]:
                    raw_name = row[mapped_key].strip()
                    break

            if not raw_name:
                logger.warning("csv_row_no_name", row_num=stats["total"])
                stats["skipped"] += 1
                continue

            # Build canonical record
            domain = row.get(mapping.get("domain", "domain"), "").strip() or None
            legal_name = row.get(mapping.get("legal_name", "legal_name"), "").strip() or None

            canonical = build_canonical_record(
                raw_name=raw_name,
                legal_name=legal_name,
                domain=domain,
            )

            # Check if company already exists (by domain or brand name)
            existing = None
            if canonical["domain"]:
                result = (
                    db.table("companies")
                    .select("id")
                    .eq("domain", canonical["domain"])
                    .limit(1)
                    .execute()
                )
                if result.data:
                    existing = result.data[0]

            if not existing:
                result = (
                    db.table("companies")
                    .select("id")
                    .eq("brand_name", canonical["brand_name"])
                    .limit(1)
                    .execute()
                )
                if result.data:
                    existing = result.data[0]

            if existing:
                logger.debug("company_exists", brand=canonical["brand_name"])
                stats["skipped"] += 1
                continue

            # Insert new company
            record = {
                "brand_name": canonical["brand_name"],
                "legal_name": canonical["legal_name"],
                "aliases": canonical["aliases"],
                "domain": canonical["domain"],
                "industry": row.get(mapping.get("industry", "industry"), "").strip() or None,
                "vertical": row.get(mapping.get("vertical", "vertical"), "").strip() or None,
                "employee_range": row.get(mapping.get("employee_range", "employee_range"), "").strip() or None,
                "country": row.get(mapping.get("country", "country"), "").strip() or None,
                "city": row.get(mapping.get("city", "city"), "").strip() or None,
                "source": source,
                "pipeline_stage": "discovered",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            # Parse founding_year if present
            founding_year = row.get(mapping.get("founding_year", "founding_year"), "").strip()
            if founding_year and founding_year.isdigit():
                record["founding_year"] = int(founding_year)

            db.table("companies").insert(record).execute()
            stats["imported"] += 1

            logger.info(
                "company_imported",
                brand=canonical["brand_name"],
                domain=canonical["domain"],
            )

        except Exception as e:
            logger.error("csv_import_error", row_num=stats["total"], error=str(e))
            stats["errors"] += 1

    logger.info("csv_import_complete", **stats)
    return stats


async def get_companies_for_scanning(
    limit: int = 500,
    stage: str = "discovered",
) -> list[dict]:
    """
    Fetch companies that need handle scanning.

    Args:
        limit: Maximum number of companies to return
        stage: Pipeline stage to filter by

    Returns:
        List of company dicts ready for scanning
    """
    db = get_service_client()

    result = (
        db.table("companies")
        .select("*")
        .eq("pipeline_stage", stage)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )

    logger.info("companies_fetched_for_scanning", count=len(result.data))
    return result.data


async def get_companies_for_enrichment(
    score_threshold: float = 0.5,
    limit: int = 100,
) -> list[dict]:
    """
    Fetch scored companies that qualify for Tier 2 contact enrichment.

    Args:
        score_threshold: Minimum total_opportunity_score
        limit: Maximum number of companies to return

    Returns:
        List of company dicts ready for enrichment
    """
    db = get_service_client()

    result = (
        db.table("companies")
        .select("*")
        .eq("pipeline_stage", "scored")
        .gte("total_opportunity_score", score_threshold)
        .order("total_opportunity_score", desc=True)
        .limit(limit)
        .execute()
    )

    logger.info(
        "companies_fetched_for_enrichment",
        count=len(result.data),
        threshold=score_threshold,
    )
    return result.data
