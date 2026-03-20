"""
Scoring Engine — ranks companies by username acquisition opportunity value.

Weighted model (from build plan):
    0.35 × Brand Value      How big/valuable is this brand?
    0.30 × Handle Pain       How bad is their current handle situation?
    0.20 × Urgency           Are there time-sensitive signals?
    0.15 × Reachability      Can we actually reach decision-makers?

Each component scores 0.0–1.0. The total_opportunity_score determines
which priority bucket the company falls into:
    > 0.80  → Critical    (auto-outreach)
    0.65–0.80 → Very High  (auto-outreach)
    0.50–0.65 → High       (approval queue)
    0.35–0.50 → Medium     (parked, revisit)
    < 0.35  → Low         (parked)

The scoring engine uses:
    - Claude Haiku for fast brand value assessment (~$0.001/call)
    - Database handle records for handle pain calculation
    - Heuristic signals for urgency and reachability
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

import structlog

from app.config import settings
from app.database import get_service_client
from app.models.company import PriorityBucket

logger = structlog.get_logger()


# ──────────────────────────────────────────────────────────────────────────────
# 1. BRAND VALUE (weight: 0.35)
# ──────────────────────────────────────────────────────────────────────────────

async def calculate_brand_value(company: dict) -> tuple[float, dict]:
    """
    Assess how valuable a brand's username would be to them.

    Factors:
    - Company size (employees, public status)
    - Consumer-facing score (B2C brands care more about handles)
    - Industry relevance (tech, media, DTC brands value handles most)
    - Founding year (established brands have more at stake)

    Returns:
        (score: float, reasoning: dict)
    """
    score = 0.0
    signals = {}

    # Employee range scoring
    emp_range = (company.get("employee_range") or "").lower()
    emp_scores = {
        "10000+": 1.0, "5001-10000": 0.9, "1001-5000": 0.8,
        "501-1000": 0.7, "201-500": 0.6, "51-200": 0.5,
        "11-50": 0.35, "1-10": 0.2,
    }
    emp_score = 0.3  # default for unknown
    for range_key, s in emp_scores.items():
        if range_key in emp_range:
            emp_score = s
            break
    signals["employee_size"] = emp_score

    # Public company bonus
    is_public = company.get("is_public", False)
    public_bonus = 0.15 if is_public else 0.0
    signals["is_public"] = public_bonus

    # Consumer-facing score (pre-set during import or enrichment)
    consumer_score = company.get("consumer_facing_score", 0.5)
    signals["consumer_facing"] = consumer_score

    # Industry relevance — some industries value social handles far more
    industry = (company.get("industry") or "").lower()
    high_value_industries = [
        "technology", "software", "saas", "media", "entertainment",
        "e-commerce", "ecommerce", "retail", "consumer goods", "fashion",
        "beauty", "food", "beverage", "gaming", "sports", "fitness",
        "travel", "hospitality", "fintech", "crypto", "web3",
    ]
    medium_value_industries = [
        "finance", "banking", "insurance", "healthcare", "education",
        "real estate", "automotive", "telecom", "telecommunications",
    ]

    industry_score = 0.3  # default
    if any(ind in industry for ind in high_value_industries):
        industry_score = 0.85
    elif any(ind in industry for ind in medium_value_industries):
        industry_score = 0.55
    signals["industry_relevance"] = industry_score

    # Founding year — older = more established = more brand equity
    founding_year = company.get("founding_year")
    if founding_year:
        years_old = datetime.now().year - founding_year
        if years_old >= 20:
            age_score = 0.9
        elif years_old >= 10:
            age_score = 0.7
        elif years_old >= 5:
            age_score = 0.5
        else:
            age_score = 0.3
    else:
        age_score = 0.4  # unknown age
    signals["company_age"] = age_score

    # Composite brand value
    score = (
        emp_score * 0.30
        + public_bonus * 0.10
        + consumer_score * 0.25
        + industry_score * 0.20
        + age_score * 0.15
    )

    return round(min(score, 1.0), 4), signals


# ──────────────────────────────────────────────────────────────────────────────
# 2. HANDLE PAIN (weight: 0.30)
# ──────────────────────────────────────────────────────────────────────────────

async def calculate_handle_pain(company_id: str) -> tuple[float, dict]:
    """
    Calculate how painful the company's current handle situation is.

    Uses the platform_handles table populated by the scanner in Phase 2.
    Aggregates mismatch severity across all platforms with bonuses for
    cross-platform inconsistency and dormant holders.

    Returns:
        (score: float, reasoning: dict)
    """
    try:
        db = get_service_client()
        result = (
            db.table("platform_handles")
            .select("*")
            .eq("company_id", company_id)
            .execute()
        )
        handles = result.data
    except Exception as e:
        logger.error("handle_pain_db_error", company_id=company_id, error=str(e))
        return 0.0, {"error": str(e)}

    if not handles:
        return 0.0, {"reason": "no_handle_data"}

    signals = {
        "platform_count": len(handles),
        "platforms": {},
    }

    severities = []
    has_dormant = False
    available_count = 0
    mismatch_count = 0

    for h in handles:
        platform = h.get("platform", "unknown")
        severity = h.get("mismatch_severity", 0.0)
        severities.append(severity)

        if severity > 0:
            mismatch_count += 1
        if h.get("account_dormant"):
            has_dormant = True
        if h.get("handle_available"):
            available_count += 1

        signals["platforms"][platform] = {
            "mismatch_type": h.get("mismatch_type"),
            "mismatch_severity": severity,
            "dormant": h.get("account_dormant", False),
            "available": h.get("handle_available"),
        }

    # Base score: average severity across platforms
    avg_severity = sum(severities) / len(severities) if severities else 0

    # Inconsistency bonus: mismatches on multiple platforms = more pain
    inconsistency_bonus = min(mismatch_count * 0.08, 0.25)

    # Dormant holder bonus: easier acquisition = more valuable opportunity
    dormant_bonus = 0.15 if has_dormant else 0.0

    # Available handle bonus: if the handle is free, that's high pain
    # (they SHOULD have it but don't)
    available_bonus = min(available_count * 0.05, 0.15)

    score = min(avg_severity + inconsistency_bonus + dormant_bonus + available_bonus, 1.0)

    signals["avg_severity"] = round(avg_severity, 3)
    signals["inconsistency_bonus"] = round(inconsistency_bonus, 3)
    signals["dormant_bonus"] = round(dormant_bonus, 3)
    signals["available_bonus"] = round(available_bonus, 3)

    return round(score, 4), signals


# ──────────────────────────────────────────────────────────────────────────────
# 3. URGENCY (weight: 0.20)
# ──────────────────────────────────────────────────────────────────────────────

async def calculate_urgency(company: dict, handle_signals: dict) -> tuple[float, dict]:
    """
    Estimate time-sensitivity of the opportunity.

    Urgency signals:
    - Dormant holder that could come back alive any day
    - Available handle that anyone could register
    - Recent funding / IPO signals (from enrichment data)
    - Rebranding indicators
    - Platform growth (e.g., TikTok adoption wave)

    Returns:
        (score: float, reasoning: dict)
    """
    signals = {}
    score = 0.0

    # Available handles are urgent — someone else could grab them
    platforms = handle_signals.get("platforms", {})
    available_platforms = [
        p for p, data in platforms.items()
        if data.get("available")
    ]
    if available_platforms:
        urgency_add = min(len(available_platforms) * 0.15, 0.4)
        score += urgency_add
        signals["available_handles"] = {
            "platforms": available_platforms,
            "urgency_contribution": round(urgency_add, 3),
        }

    # Dormant holders are moderately urgent — they might wake up
    dormant_platforms = [
        p for p, data in platforms.items()
        if data.get("dormant")
    ]
    if dormant_platforms:
        urgency_add = min(len(dormant_platforms) * 0.12, 0.3)
        score += urgency_add
        signals["dormant_holders"] = {
            "platforms": dormant_platforms,
            "urgency_contribution": round(urgency_add, 3),
        }

    # Enrichment-based urgency signals (populated in Phase 4)
    enrichment = company.get("enrichment_data") or {}
    urgency_data = company.get("urgency_signals") or {}

    # Recent funding
    if urgency_data.get("recent_funding") or enrichment.get("recent_funding"):
        score += 0.2
        signals["recent_funding"] = True

    # IPO or going public
    if urgency_data.get("ipo_planned") or enrichment.get("ipo_planned"):
        score += 0.25
        signals["ipo_planned"] = True

    # Rebranding
    if urgency_data.get("rebranding") or enrichment.get("rebranding"):
        score += 0.3
        signals["rebranding"] = True

    # New product launch
    if urgency_data.get("product_launch") or enrichment.get("product_launch"):
        score += 0.15
        signals["product_launch"] = True

    return round(min(score, 1.0), 4), signals


# ──────────────────────────────────────────────────────────────────────────────
# 4. REACHABILITY (weight: 0.15)
# ──────────────────────────────────────────────────────────────────────────────

async def calculate_reachability(company: dict) -> tuple[float, dict]:
    """
    Estimate how easily we can reach decision-makers.

    Factors:
    - Domain available (for email finding)
    - Company size (smaller = easier to reach founders)
    - Country (English-speaking markets preferred for outreach)
    - Enrichment data availability (will be filled in Phase 4)

    Returns:
        (score: float, reasoning: dict)
    """
    signals = {}
    score = 0.0

    # Has domain — essential for email discovery
    has_domain = bool(company.get("domain"))
    domain_score = 0.3 if has_domain else 0.0
    signals["has_domain"] = has_domain
    score += domain_score

    # Company size — sweet spot is 11-500 (accessible but has budget)
    emp_range = (company.get("employee_range") or "").lower()
    reach_by_size = {
        "1-10": 0.25,       # Very small — easy to reach but may lack budget
        "11-50": 0.35,      # Startup — very reachable
        "51-200": 0.30,     # Growth stage — good balance
        "201-500": 0.25,    # Mid-market — harder to reach right person
        "501-1000": 0.15,   # Enterprise — gatekeepers
        "1001-5000": 0.10,  # Large enterprise — very hard
        "5001-10000": 0.05, # Mega corp — extremely hard
        "10000+": 0.02,     # Global — almost unreachable directly
    }
    size_score = 0.15  # default
    for range_key, s in reach_by_size.items():
        if range_key in emp_range:
            size_score = s
            break
    signals["size_reachability"] = size_score
    score += size_score

    # Country — English-speaking markets are easier for outreach
    country = (company.get("country") or "").lower()
    english_markets = ["us", "usa", "united states", "uk", "united kingdom",
                       "canada", "australia", "new zealand", "ireland"]
    if any(m in country for m in english_markets):
        geo_score = 0.2
    elif country:
        geo_score = 0.1
    else:
        geo_score = 0.1  # unknown — neutral
    signals["geo_reachability"] = geo_score
    score += geo_score

    # Has enrichment data (contacts already found — Phase 4)
    enrichment = company.get("enrichment_data") or {}
    contacts_found = enrichment.get("contacts_found", 0)
    if contacts_found > 0:
        contact_score = min(contacts_found * 0.05, 0.2)
        score += contact_score
        signals["contacts_available"] = contacts_found
    else:
        signals["contacts_available"] = 0

    return round(min(score, 1.0), 4), signals


# ──────────────────────────────────────────────────────────────────────────────
# COMPOSITE SCORING
# ──────────────────────────────────────────────────────────────────────────────

def classify_priority_bucket(total_score: float) -> PriorityBucket:
    """Map a total opportunity score to a priority bucket."""
    if total_score > 0.80:
        return PriorityBucket.CRITICAL
    elif total_score >= 0.65:
        return PriorityBucket.VERY_HIGH
    elif total_score >= 0.50:
        return PriorityBucket.HIGH
    elif total_score >= 0.35:
        return PriorityBucket.MEDIUM
    else:
        return PriorityBucket.LOW


async def score_company(company: dict) -> dict:
    """
    Run the full scoring pipeline on a single company.

    This is the main entry point for Phase 3 scoring.

    Args:
        company: Company dict from the database (must include 'id')

    Returns:
        {
            "company_id": str,
            "brand_value_score": float,
            "handle_pain_score": float,
            "urgency_score": float,
            "reachability_score": float,
            "total_opportunity_score": float,
            "priority_bucket": str,
            "component_signals": dict,
        }
    """
    company_id = company["id"]
    brand_name = company.get("brand_name", "Unknown")

    logger.info("scoring_started", company_id=company_id, brand_name=brand_name)

    # Calculate all four components (brand_value and handle_pain can run concurrently)
    brand_value_task = calculate_brand_value(company)
    handle_pain_task = calculate_handle_pain(company_id)

    (brand_value, bv_signals), (handle_pain, hp_signals) = await asyncio.gather(
        brand_value_task, handle_pain_task
    )

    # Urgency depends on handle signals
    urgency, urg_signals = await calculate_urgency(company, hp_signals)

    # Reachability
    reachability, reach_signals = await calculate_reachability(company)

    # Weighted composite
    total = (
        brand_value * settings.weight_brand_value
        + handle_pain * settings.weight_handle_pain
        + urgency * settings.weight_urgency
        + reachability * settings.weight_reachability
    )
    total = round(total, 4)

    priority = classify_priority_bucket(total)

    result = {
        "company_id": company_id,
        "brand_value_score": brand_value,
        "handle_pain_score": handle_pain,
        "urgency_score": urgency,
        "reachability_score": reachability,
        "total_opportunity_score": total,
        "priority_bucket": priority.value,
        "component_signals": {
            "brand_value": bv_signals,
            "handle_pain": hp_signals,
            "urgency": urg_signals,
            "reachability": reach_signals,
        },
    }

    logger.info(
        "scoring_complete",
        company_id=company_id,
        brand_name=brand_name,
        total_score=total,
        priority=priority.value,
    )

    return result


async def score_and_persist(company: dict) -> dict:
    """Score a company and save results to the database."""
    result = await score_company(company)

    try:
        db = get_service_client()
        db.table("companies").update({
            "brand_value_score": result["brand_value_score"],
            "handle_pain_score": result["handle_pain_score"],
            "urgency_score": result["urgency_score"],
            "reachability_score": result["reachability_score"],
            "total_opportunity_score": result["total_opportunity_score"],
            "priority_bucket": result["priority_bucket"],
            "urgency_signals": result["component_signals"].get("urgency", {}),
            "pipeline_stage": "scored",
            "scored_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", result["company_id"]).execute()

        logger.info("score_persisted", company_id=result["company_id"])

    except Exception as e:
        logger.error("score_persist_error", company_id=result["company_id"], error=str(e))

    return result


async def score_batch(companies: list[dict], concurrency: int = 10) -> list[dict]:
    """
    Score a batch of companies with controlled concurrency.

    Args:
        companies: List of company dicts
        concurrency: Max concurrent scoring operations

    Returns:
        List of scoring result dicts
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _score_with_limit(company: dict):
        async with semaphore:
            return await score_and_persist(company)

    tasks = [_score_with_limit(c) for c in companies]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    scored = []
    errors = 0
    for company, result in zip(companies, results):
        if isinstance(result, Exception):
            logger.error("batch_score_error", company_id=company["id"], error=str(result))
            errors += 1
        else:
            scored.append(result)

    logger.info(
        "batch_scoring_complete",
        total=len(companies),
        scored=len(scored),
        errors=errors,
    )

    return scored


async def get_scoring_summary() -> dict:
    """Get distribution of scores across all scored companies."""
    try:
        db = get_service_client()
        result = (
            db.table("companies")
            .select("total_opportunity_score, priority_bucket")
            .eq("pipeline_stage", "scored")
            .execute()
        )

        companies = result.data
        if not companies:
            return {"total_scored": 0}

        scores = [c["total_opportunity_score"] for c in companies if c.get("total_opportunity_score")]
        buckets = {}
        for c in companies:
            bucket = c.get("priority_bucket", "unknown")
            buckets[bucket] = buckets.get(bucket, 0) + 1

        return {
            "total_scored": len(companies),
            "avg_score": round(sum(scores) / len(scores), 3) if scores else 0,
            "max_score": round(max(scores), 3) if scores else 0,
            "min_score": round(min(scores), 3) if scores else 0,
            "bucket_distribution": buckets,
        }

    except Exception as e:
        logger.error("scoring_summary_error", error=str(e))
        return {"error": str(e)}
