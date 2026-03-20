"""
RocketReach Integration — find decision-maker contacts at target companies.

RocketReach provides:
- Person search by company + title/role
- Email lookup and verification
- LinkedIn profile matching
- Phone number discovery

We target marketing/brand/social/digital/executive roles since those
are the decision-makers for username acquisitions.

Rate limits: ~15 req/sec, monthly credit cap (tracked by rate_limiter).
"""

import httpx
from typing import Optional

import structlog

from app.config import settings
from app.integrations.rate_limiter import rate_limiter

logger = structlog.get_logger()

BASE_URL = "https://api.rocketreach.co/api/v2"

# Target titles for username acquisition outreach (ordered by priority)
TARGET_TITLES = [
    "Chief Marketing Officer",
    "CMO",
    "VP Marketing",
    "VP Brand",
    "VP Digital",
    "Head of Marketing",
    "Head of Brand",
    "Head of Social Media",
    "Head of Digital",
    "Director of Marketing",
    "Director of Brand",
    "Director of Social Media",
    "Director of Digital Marketing",
    "Social Media Manager",
    "Brand Manager",
    "Digital Marketing Manager",
    "CEO",
    "Founder",
    "Co-Founder",
    "Chief Executive Officer",
]

# Departments to search
TARGET_DEPARTMENTS = ["marketing", "executive", "operations"]


def _get_headers() -> dict:
    """Build auth headers for RocketReach API."""
    return {
        "Api-Key": settings.rocketreach_api_key or "",
        "Content-Type": "application/json",
    }


async def search_contacts(
    company_name: str,
    domain: Optional[str] = None,
    titles: Optional[list[str]] = None,
    limit: int = 5,
) -> list[dict]:
    """
    Search for decision-maker contacts at a company.

    Args:
        company_name: Company name to search
        domain: Company domain for more precise matching
        titles: Specific titles to search (default: TARGET_TITLES)
        limit: Max contacts to return

    Returns:
        List of contact dicts with name, title, email, linkedin, etc.
    """
    if not settings.rocketreach_api_key:
        logger.warning("rocketreach_api_key_not_set")
        return []

    # Check monthly limit
    if not rate_limiter.check_daily_limit("rocketreach", settings.max_rocketreach_calls_per_month // 30):
        logger.warning("rocketreach_daily_limit_reached")
        return []

    await rate_limiter.acquire("rocketreach")
    rate_limiter.track_daily_usage("rocketreach")

    titles = titles or TARGET_TITLES[:10]  # Top 10 titles by priority

    # Build search query
    query = {
        "current_employer": [company_name],
        "current_title": titles,
        "page_size": limit,
    }

    if domain:
        query["company_domain"] = [domain]

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{BASE_URL}/person/search",
                headers=_get_headers(),
                json={"query": query},
            )

            if response.status_code == 429:
                logger.warning("rocketreach_rate_limited")
                return []

            if response.status_code != 200:
                logger.error(
                    "rocketreach_search_error",
                    status=response.status_code,
                    body=response.text[:500],
                )
                return []

            data = response.json()
            profiles = data.get("profiles", [])

            contacts = []
            for profile in profiles:
                contact = _parse_profile(profile)
                if contact:
                    contacts.append(contact)

            logger.info(
                "rocketreach_search_complete",
                company=company_name,
                results=len(contacts),
            )

            return contacts

    except httpx.TimeoutException:
        logger.error("rocketreach_timeout", company=company_name)
        return []
    except Exception as e:
        logger.error("rocketreach_error", company=company_name, error=str(e))
        return []


async def lookup_person(
    name: str,
    company_name: Optional[str] = None,
    linkedin_url: Optional[str] = None,
) -> Optional[dict]:
    """
    Look up a specific person's contact details.

    Args:
        name: Person's full name
        company_name: Current employer
        linkedin_url: LinkedIn profile URL (most reliable lookup)

    Returns:
        Contact dict or None
    """
    if not settings.rocketreach_api_key:
        return None

    if not rate_limiter.check_daily_limit("rocketreach", settings.max_rocketreach_calls_per_month // 30):
        return None

    await rate_limiter.acquire("rocketreach")
    rate_limiter.track_daily_usage("rocketreach")

    params = {"name": name}
    if company_name:
        params["current_employer"] = company_name
    if linkedin_url:
        params["linkedin_url"] = linkedin_url

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{BASE_URL}/person/lookup",
                headers=_get_headers(),
                params=params,
            )

            if response.status_code != 200:
                logger.warning(
                    "rocketreach_lookup_failed",
                    status=response.status_code,
                    name=name,
                )
                return None

            data = response.json()
            return _parse_profile(data)

    except Exception as e:
        logger.error("rocketreach_lookup_error", name=name, error=str(e))
        return None


def _parse_profile(profile: dict) -> Optional[dict]:
    """Parse a RocketReach profile into our contact format."""
    if not profile:
        return None

    # Extract best email
    emails = profile.get("emails", [])
    best_email = None
    email_confidence = 0.0

    if emails:
        # RocketReach returns emails as list of dicts or strings
        if isinstance(emails[0], dict):
            # Sort by confidence, prefer professional emails
            professional = [e for e in emails if e.get("type") == "professional"]
            sorted_emails = sorted(
                professional or emails,
                key=lambda e: e.get("confidence", 0),
                reverse=True,
            )
            if sorted_emails:
                best_email = sorted_emails[0].get("email")
                email_confidence = sorted_emails[0].get("confidence", 0)
        elif isinstance(emails[0], str):
            best_email = emails[0]
            email_confidence = 0.5

    # Classify seniority from title
    title = profile.get("current_title", "")
    seniority = _classify_seniority(title)
    department = _classify_department(title)

    return {
        "first_name": profile.get("first_name"),
        "last_name": profile.get("last_name"),
        "full_name": profile.get("name") or f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
        "title": title,
        "seniority_level": seniority,
        "department": department,
        "email": best_email,
        "email_confidence": email_confidence / 100 if email_confidence > 1 else email_confidence,
        "email_source": "rocketreach",
        "email_type": "professional",
        "linkedin_url": profile.get("linkedin_url"),
        "phone": profile.get("phones", [None])[0] if profile.get("phones") else None,
        "rocketreach_id": str(profile.get("id", "")),
        "enrichment_data": {
            "city": profile.get("city"),
            "region": profile.get("region"),
            "country": profile.get("country_code"),
            "company_name": profile.get("current_employer"),
        },
    }


def _classify_seniority(title: str) -> str:
    """Classify a job title into a seniority level."""
    import re
    title_lower = title.lower()

    # Use word boundary matching to avoid substring false positives (e.g., "director" matching "cto")
    c_suite_patterns = [r"\bchief\b", r"\bceo\b", r"\bcmo\b", r"\bcto\b", r"\bcfo\b", r"\bcoo\b",
                        r"\bc-suite\b", r"\bfounder\b", r"\bco-founder\b", r"\bpresident\b"]
    if any(re.search(p, title_lower) for p in c_suite_patterns):
        return "c_suite"

    vp_patterns = [r"\bvp\b", r"\bvice president\b", r"\bsvp\b", r"\bevp\b"]
    if any(re.search(p, title_lower) for p in vp_patterns):
        return "vp"

    if any(re.search(p, title_lower) for p in [r"\bdirector\b", r"\bhead of\b"]):
        return "director"

    if any(re.search(p, title_lower) for p in [r"\bmanager\b", r"\blead\b", r"\bsenior\b"]):
        return "manager"

    return "individual"


def _classify_department(title: str) -> str:
    """Classify a job title into a department."""
    import re
    title_lower = title.lower()

    if any(re.search(p, title_lower) for p in [r"\bsocial\b", r"\bcommunity\b"]):
        return "social"
    elif any(re.search(p, title_lower) for p in [r"\bbrand\b", r"\bcreative\b"]):
        return "brand"
    elif any(re.search(p, title_lower) for p in [r"\bdigital\b", r"\bgrowth\b", r"\bacquisition\b"]):
        return "digital"
    elif any(re.search(p, title_lower) for p in [r"\bmarketing\b", r"\bcontent\b", r"\bcommunications\b", r"\bpr\b", r"\bcmo\b"]):
        return "marketing"
    elif any(re.search(p, title_lower) for p in [r"\bceo\b", r"\bcoo\b", r"\bfounder\b", r"\bpresident\b", r"\bchief\b", r"\bexecutive\b"]):
        return "executive"
    else:
        return "other"
