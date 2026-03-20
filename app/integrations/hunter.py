"""
Hunter.io Integration — email finding and verification.

Hunter.io provides:
- Domain search: find all email addresses at a company domain
- Email finder: find a specific person's email by name + domain
- Email verifier: check if an email is valid/deliverable

Used as a complement to RocketReach — Hunter excels at email discovery
while RocketReach is better for person/title search.

Rate limits: 15 req/sec, monthly credit cap.
"""

import httpx
from typing import Optional

import structlog

from app.config import settings
from app.integrations.rate_limiter import rate_limiter

logger = structlog.get_logger()

BASE_URL = "https://api.hunter.io/v2"


async def domain_search(
    domain: str,
    department: Optional[str] = None,
    seniority: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """
    Find email addresses associated with a company domain.

    Args:
        domain: Company domain (e.g., "stripe.com")
        department: Filter by department (executive, marketing, etc.)
        seniority: Filter by seniority (senior, junior)
        limit: Max results to return

    Returns:
        List of email result dicts
    """
    if not settings.hunter_api_key:
        logger.warning("hunter_api_key_not_set")
        return []

    if not rate_limiter.check_daily_limit("hunter", settings.max_hunter_calls_per_month // 30):
        logger.warning("hunter_daily_limit_reached")
        return []

    await rate_limiter.acquire("hunter")
    rate_limiter.track_daily_usage("hunter")

    params = {
        "domain": domain,
        "api_key": settings.hunter_api_key,
        "limit": limit,
    }
    if department:
        params["department"] = department
    if seniority:
        params["seniority"] = seniority

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{BASE_URL}/domain-search",
                params=params,
            )

            if response.status_code == 429:
                logger.warning("hunter_rate_limited")
                return []

            if response.status_code != 200:
                logger.error(
                    "hunter_domain_search_error",
                    status=response.status_code,
                    body=response.text[:500],
                )
                return []

            data = response.json().get("data", {})
            emails = data.get("emails", [])

            results = []
            for email_entry in emails:
                parsed = _parse_email_result(email_entry, domain)
                if parsed:
                    results.append(parsed)

            logger.info(
                "hunter_domain_search_complete",
                domain=domain,
                results=len(results),
                total_available=data.get("total", 0),
            )

            return results

    except httpx.TimeoutException:
        logger.error("hunter_timeout", domain=domain)
        return []
    except Exception as e:
        logger.error("hunter_error", domain=domain, error=str(e))
        return []


async def find_email(
    domain: str,
    first_name: str,
    last_name: str,
) -> Optional[dict]:
    """
    Find a specific person's email address by name and company domain.

    Args:
        domain: Company domain
        first_name: Person's first name
        last_name: Person's last name

    Returns:
        Email result dict or None
    """
    if not settings.hunter_api_key:
        return None

    if not rate_limiter.check_daily_limit("hunter", settings.max_hunter_calls_per_month // 30):
        return None

    await rate_limiter.acquire("hunter")
    rate_limiter.track_daily_usage("hunter")

    params = {
        "domain": domain,
        "first_name": first_name,
        "last_name": last_name,
        "api_key": settings.hunter_api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{BASE_URL}/email-finder",
                params=params,
            )

            if response.status_code != 200:
                logger.warning(
                    "hunter_find_email_failed",
                    status=response.status_code,
                    name=f"{first_name} {last_name}",
                )
                return None

            data = response.json().get("data", {})

            if not data.get("email"):
                return None

            return {
                "email": data["email"],
                "email_confidence": (data.get("score", 0)) / 100,
                "email_source": "hunter",
                "email_type": data.get("type", "unknown"),
                "first_name": data.get("first_name", first_name),
                "last_name": data.get("last_name", last_name),
                "full_name": f"{first_name} {last_name}",
                "position": data.get("position"),
                "department": data.get("department"),
                "linkedin_url": data.get("linkedin"),
                "verification_status": data.get("verification", {}).get("status"),
            }

    except Exception as e:
        logger.error(
            "hunter_find_email_error",
            name=f"{first_name} {last_name}",
            error=str(e),
        )
        return None


async def verify_email(email: str) -> Optional[dict]:
    """
    Verify if an email address is valid and deliverable.

    Args:
        email: Email address to verify

    Returns:
        Verification result dict or None
    """
    if not settings.hunter_api_key:
        return None

    await rate_limiter.acquire("hunter")
    rate_limiter.track_daily_usage("hunter")

    params = {
        "email": email,
        "api_key": settings.hunter_api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{BASE_URL}/email-verifier",
                params=params,
            )

            if response.status_code != 200:
                return None

            data = response.json().get("data", {})

            return {
                "email": email,
                "status": data.get("status"),  # valid, invalid, accept_all, webmail, disposable, unknown
                "result": data.get("result"),  # deliverable, undeliverable, risky
                "score": data.get("score", 0),
                "is_disposable": data.get("disposable", False),
                "is_webmail": data.get("webmail", False),
                "mx_records": data.get("mx_records", False),
                "smtp_check": data.get("smtp_check", False),
            }

    except Exception as e:
        logger.error("hunter_verify_error", email=email, error=str(e))
        return None


def _parse_email_result(entry: dict, domain: str) -> Optional[dict]:
    """Parse a Hunter.io email result into our contact format."""
    if not entry or not entry.get("value"):
        return None

    first_name = entry.get("first_name", "")
    last_name = entry.get("last_name", "")

    return {
        "email": entry["value"],
        "email_confidence": (entry.get("confidence", 0)) / 100,
        "email_source": "hunter",
        "email_type": entry.get("type", "unknown"),  # personal or generic
        "first_name": first_name,
        "last_name": last_name,
        "full_name": f"{first_name} {last_name}".strip() if (first_name or last_name) else None,
        "title": entry.get("position"),
        "department": entry.get("department"),
        "seniority": entry.get("seniority"),
        "linkedin_url": entry.get("linkedin"),
        "phone_number": entry.get("phone_number"),
        "domain": domain,
        "sources_count": len(entry.get("sources", [])),
    }
