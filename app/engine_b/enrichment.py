"""
Contact Enrichment Engine — finds decision-maker contacts for scored companies.

This is the Tier 2 step: after scoring identifies high-value opportunities,
we spend credits to find the right people to contact.

Strategy:
1. RocketReach first: search by company + target titles (marketing/brand/exec)
2. Hunter.io supplement: domain search for additional emails, verification
3. Merge & deduplicate: combine results, pick best email per person
4. Rank contacts: prioritize by seniority + department relevance
5. Store in contacts table with outreach_priority ordering

Cost: ~$0.10-0.50 per company depending on number of lookups needed.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import structlog

from app.config import settings
from app.database import get_service_client
from app.integrations.rocketreach import search_contacts as rr_search
from app.integrations.hunter import domain_search as hunter_domain_search, verify_email

logger = structlog.get_logger()

# Priority weights for contact ranking
SENIORITY_WEIGHTS = {
    "c_suite": 5,
    "vp": 4,
    "director": 3,
    "manager": 2,
    "individual": 1,
}

DEPARTMENT_WEIGHTS = {
    "brand": 5,       # Brand managers are the #1 target
    "social": 5,      # Social media managers equally relevant
    "marketing": 4,   # Marketing leaders make budget decisions
    "digital": 3,     # Digital team handles handles
    "executive": 3,   # Executives can approve but may not own
    "other": 1,
}


async def enrich_company_contacts(
    company: dict,
    max_contacts: int = 5,
    verify_emails: bool = True,
) -> dict:
    """
    Find and store decision-maker contacts for a company.

    This is the main entry point for Tier 2 enrichment.

    Args:
        company: Company dict (must include 'id', 'brand_name', 'domain')
        max_contacts: Max contacts to store per company
        verify_emails: Whether to verify emails via Hunter

    Returns:
        Enrichment result summary
    """
    company_id = company["id"]
    brand_name = company.get("brand_name", "Unknown")
    domain = company.get("domain")

    logger.info(
        "enrichment_started",
        company_id=company_id,
        brand_name=brand_name,
        domain=domain,
    )

    all_contacts = []

    # Step 1: RocketReach person search
    rr_contacts = await rr_search(
        company_name=brand_name,
        domain=domain,
        limit=max_contacts + 2,  # Get a few extra to filter
    )
    all_contacts.extend(rr_contacts)
    logger.debug("rocketreach_results", count=len(rr_contacts))

    # Step 2: Hunter.io domain search (if we have a domain)
    hunter_contacts = []
    if domain:
        hunter_contacts = await hunter_domain_search(
            domain=domain,
            department="marketing",
            limit=max_contacts,
        )

        # Also search executive department
        exec_contacts = await hunter_domain_search(
            domain=domain,
            department="executive",
            seniority="senior",
            limit=3,
        )
        hunter_contacts.extend(exec_contacts)

    all_contacts.extend(hunter_contacts)
    logger.debug("hunter_results", count=len(hunter_contacts))

    # Step 3: Merge and deduplicate
    merged = _merge_contacts(all_contacts)
    logger.debug("merged_contacts", count=len(merged))

    # Step 4: Verify emails (if enabled and we have Hunter API)
    if verify_emails and settings.hunter_api_key:
        merged = await _verify_contact_emails(merged)

    # Step 5: Rank by priority and take top N
    ranked = _rank_contacts(merged)
    top_contacts = ranked[:max_contacts]

    # Step 6: Persist to database
    saved_count = await _save_contacts(company_id, top_contacts)

    # Step 7: Update company enrichment status
    await _update_company_enrichment(company_id, len(top_contacts))

    result = {
        "company_id": company_id,
        "brand_name": brand_name,
        "rocketreach_found": len(rr_contacts),
        "hunter_found": len(hunter_contacts),
        "merged_unique": len(merged),
        "contacts_saved": saved_count,
        "top_contact": top_contacts[0] if top_contacts else None,
    }

    logger.info(
        "enrichment_complete",
        company_id=company_id,
        contacts_saved=saved_count,
    )

    return result


def _merge_contacts(contacts: list[dict]) -> list[dict]:
    """
    Merge and deduplicate contacts from multiple sources.

    Dedup strategy: match by email (primary) or by full name (secondary).
    When merging, prefer the record with higher email confidence.
    """
    seen_emails = {}
    seen_names = {}
    merged = []

    for contact in contacts:
        email = (contact.get("email") or "").lower().strip()
        name = (contact.get("full_name") or "").lower().strip()

        # Skip contacts with no email and no name
        if not email and not name:
            continue

        # Check email dedup
        if email and email in seen_emails:
            existing = seen_emails[email]
            # Merge: take higher confidence data
            if (contact.get("email_confidence") or 0) > (existing.get("email_confidence") or 0):
                existing["email_confidence"] = contact["email_confidence"]
                existing["email_source"] = contact.get("email_source")

            # Fill in missing fields
            for key in ["title", "linkedin_url", "phone", "department", "seniority_level"]:
                if not existing.get(key) and contact.get(key):
                    existing[key] = contact[key]
            continue

        # Check name dedup
        if name and name in seen_names:
            existing = seen_names[name]
            # If we found an email for someone we already have
            if email and not existing.get("email"):
                existing["email"] = email
                existing["email_confidence"] = contact.get("email_confidence")
                existing["email_source"] = contact.get("email_source")
            continue

        # New contact
        if email:
            seen_emails[email] = contact
        if name:
            seen_names[name] = contact
        merged.append(contact)

    return merged


def _rank_contacts(contacts: list[dict]) -> list[dict]:
    """
    Rank contacts by outreach priority.

    Score = seniority_weight × department_weight × email_confidence_factor
    Higher score = contact earlier in the sequence.
    """
    for contact in contacts:
        seniority = contact.get("seniority_level", "individual")
        department = contact.get("department", "other")
        email_conf = contact.get("email_confidence", 0)

        # Calculate priority score
        seniority_score = SENIORITY_WEIGHTS.get(seniority, 1)
        dept_score = DEPARTMENT_WEIGHTS.get(department, 1)
        email_factor = 1.0 + (email_conf * 0.5)  # 1.0–1.5x boost

        priority = round(seniority_score * dept_score * email_factor, 2)
        contact["outreach_priority"] = priority

    # Sort by priority descending
    contacts.sort(key=lambda c: c.get("outreach_priority", 0), reverse=True)

    return contacts


async def _verify_contact_emails(contacts: list[dict]) -> list[dict]:
    """Verify email addresses using Hunter.io and update confidence."""
    verified = []

    for contact in contacts:
        email = contact.get("email")
        if not email:
            verified.append(contact)
            continue

        verification = await verify_email(email)
        if verification:
            status = verification.get("result", "unknown")
            if status == "undeliverable":
                # Skip undeliverable emails
                logger.debug("email_undeliverable", email=email)
                contact["email"] = None
                contact["email_confidence"] = 0
            elif status == "deliverable":
                contact["email_confidence"] = max(
                    contact.get("email_confidence", 0),
                    verification.get("score", 0) / 100,
                )
            elif status == "risky":
                contact["email_confidence"] = min(
                    contact.get("email_confidence", 0.5),
                    0.5,
                )

            contact["verification_status"] = status

        verified.append(contact)

    return verified


async def _save_contacts(company_id: str, contacts: list[dict]) -> int:
    """Persist enriched contacts to the database."""
    saved = 0

    try:
        db = get_service_client()

        for i, contact in enumerate(contacts):
            record = {
                "company_id": company_id,
                "first_name": contact.get("first_name"),
                "last_name": contact.get("last_name"),
                "full_name": contact.get("full_name"),
                "title": contact.get("title"),
                "seniority_level": contact.get("seniority_level", "individual"),
                "department": contact.get("department", "other"),
                "email": contact.get("email"),
                "email_confidence": contact.get("email_confidence", 0),
                "email_source": contact.get("email_source"),
                "email_type": contact.get("email_type"),
                "linkedin_url": contact.get("linkedin_url"),
                "phone": contact.get("phone"),
                "rocketreach_id": contact.get("rocketreach_id"),
                "hunter_result": {
                    "verification_status": contact.get("verification_status"),
                },
                "enrichment_data": contact.get("enrichment_data", {}),
                "outreach_priority": i + 1,  # 1 = highest priority
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            db.table("contacts").upsert(
                record,
                on_conflict="company_id,email",
            ).execute()
            saved += 1

    except Exception as e:
        logger.error("save_contacts_error", company_id=company_id, error=str(e))

    return saved


async def _update_company_enrichment(company_id: str, contacts_found: int) -> None:
    """Update company record after enrichment."""
    try:
        db = get_service_client()

        update_data = {
            "pipeline_stage": "enriching" if contacts_found > 0 else "scored",
            "enrichment_data": {
                "contacts_found": contacts_found,
                "enriched_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # If contacts found and score qualifies, move to qualified
        company = db.table("companies").select("total_opportunity_score, priority_bucket").eq("id", company_id).execute()
        if company.data:
            score = company.data[0].get("total_opportunity_score", 0)
            bucket = company.data[0].get("priority_bucket", "")

            if contacts_found > 0:
                if bucket in ("critical", "very_high"):
                    # Auto-qualify for outreach
                    update_data["pipeline_stage"] = "qualified"
                    update_data["approved_for_outreach"] = True
                elif bucket == "high":
                    # Move to approval queue
                    update_data["pipeline_stage"] = "qualified"
                    update_data["approved_for_outreach"] = False
                else:
                    update_data["pipeline_stage"] = "enriching"

        db.table("companies").update(update_data).eq("id", company_id).execute()

    except Exception as e:
        logger.error("update_enrichment_error", company_id=company_id, error=str(e))


async def enrich_batch(
    companies: list[dict],
    concurrency: int = 3,
    max_contacts_per_company: int = 5,
) -> list[dict]:
    """
    Enrich contacts for a batch of companies.

    Lower concurrency than scanning since enrichment uses paid API credits.

    Args:
        companies: List of company dicts
        concurrency: Max concurrent enrichments
        max_contacts_per_company: Max contacts per company

    Returns:
        List of enrichment result dicts
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _enrich_with_limit(company: dict):
        async with semaphore:
            return await enrich_company_contacts(
                company=company,
                max_contacts=max_contacts_per_company,
            )

    tasks = [_enrich_with_limit(c) for c in companies]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    enriched = []
    errors = 0

    for company, result in zip(companies, results):
        if isinstance(result, Exception):
            logger.error("batch_enrich_error", company_id=company["id"], error=str(result))
            errors += 1
        else:
            enriched.append(result)

    logger.info(
        "batch_enrichment_complete",
        total=len(companies),
        enriched=len(enriched),
        errors=errors,
    )

    return enriched
