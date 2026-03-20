"""
Mismatch Detector — classifies the type and severity of handle mismatches.

This is the core "commercial mismatch detection" that Document 2 emphasized
as the real secret sauce. Not just "is the handle taken?" but
"is this mismatch commercially meaningful enough to monetize?"
"""

from datetime import datetime, timezone
from typing import Optional

import structlog

from app.engine_a.handle_candidates import classify_observed_handle
from app.models.platform_handle import MismatchType

logger = structlog.get_logger()

# Dormancy threshold in months
DORMANCY_THRESHOLD_MONTHS = 12


def detect_mismatch(
    brand_slug: str,
    observed_handle: Optional[str],
    platform: str,
    account_exists: Optional[bool] = None,
    last_post_date: Optional[datetime] = None,
    follower_count: Optional[int] = None,
    post_count: Optional[int] = None,
    ideal_handle_available: Optional[bool] = None,
    ideal_handle_holder_info: Optional[dict] = None,
) -> dict:
    """
    Analyze a handle finding and classify the mismatch.

    Returns a comprehensive mismatch analysis dict:
        - mismatch_type: MismatchType enum value
        - mismatch_severity: 0.0-1.0 (how bad is this)
        - account_dormant: bool (is the ideal handle holder dormant?)
        - dormancy_months: int or None
        - commercial_reasoning: str (why this matters for monetization)
        - acquisition_difficulty: str (easy | medium | hard | very_hard)
    """
    result = {
        "mismatch_type": MismatchType.NONE,
        "mismatch_severity": 0.0,
        "account_dormant": False,
        "dormancy_months": None,
        "commercial_reasoning": "",
        "acquisition_difficulty": "unknown",
    }

    # Case 1: Company has no presence on this platform
    if not observed_handle and not account_exists:
        result["mismatch_type"] = MismatchType.NOT_PRESENT
        result["mismatch_severity"] = 0.2  # Low severity — they may not care about this platform

        if ideal_handle_available:
            result["mismatch_severity"] = 0.4
            result["commercial_reasoning"] = (
                f"Company has no {platform} presence. "
                f"The exact brand handle @{brand_slug} appears available — "
                f"this is a proactive acquisition opportunity."
            )
            result["acquisition_difficulty"] = "easy"
        else:
            result["commercial_reasoning"] = (
                f"Company has no {platform} presence. "
                f"The exact brand handle is taken by another account."
            )
        return result

    # Case 2: Company has a handle — classify it
    if observed_handle:
        classification = classify_observed_handle(brand_slug, observed_handle)

        if classification["match_type"] == "exact":
            # Perfect match — no opportunity
            result["mismatch_type"] = MismatchType.NONE
            result["mismatch_severity"] = 0.0
            result["commercial_reasoning"] = (
                f"Company already has the exact brand handle @{brand_slug} on {platform}. "
                f"No acquisition opportunity."
            )
            return result

        elif classification["match_type"] in ("suffix_modified", "prefix_modified"):
            # Has a modified handle (e.g., @stripehq instead of @stripe)
            result["mismatch_type"] = MismatchType.MODIFIER
            result["mismatch_severity"] = classification["severity"]
            modifier = classification["modifier"]
            result["commercial_reasoning"] = (
                f"Company uses @{observed_handle} instead of @{brand_slug} on {platform}. "
                f"The '{modifier}' modifier weakens brand consistency. "
            )

        elif classification["match_type"] == "contains_brand":
            result["mismatch_type"] = MismatchType.DIFFERENT
            result["mismatch_severity"] = 0.6
            result["commercial_reasoning"] = (
                f"Company uses @{observed_handle} which contains the brand name but "
                f"is not the clean handle @{brand_slug} on {platform}."
            )

        elif classification["match_type"] == "unrelated":
            result["mismatch_type"] = MismatchType.DIFFERENT
            result["mismatch_severity"] = 0.8
            result["commercial_reasoning"] = (
                f"Company uses @{observed_handle} which does not match brand name "
                f"'{brand_slug}' on {platform}. This is a significant brand inconsistency."
            )

    # Case 3: Check if the ideal handle is held by a dormant account
    if not ideal_handle_available and ideal_handle_holder_info:
        dormancy = _check_dormancy(
            last_post_date=ideal_handle_holder_info.get("last_post_date"),
            follower_count=ideal_handle_holder_info.get("follower_count"),
            post_count=ideal_handle_holder_info.get("post_count"),
        )

        if dormancy["is_dormant"]:
            result["mismatch_type"] = MismatchType.INACTIVE_HOLDER
            result["account_dormant"] = True
            result["dormancy_months"] = dormancy["months_dormant"]

            # Dormant holder BOOSTS severity — this is the highest-value signal
            result["mismatch_severity"] = min(result["mismatch_severity"] + 0.3, 1.0)
            result["acquisition_difficulty"] = "easy" if dormancy["months_dormant"] > 24 else "medium"

            result["commercial_reasoning"] += (
                f" The exact handle @{brand_slug} is held by a dormant account "
                f"(inactive for {dormancy['months_dormant']} months). "
                f"Dormant handles are significantly easier and cheaper to acquire."
            )
        else:
            result["mismatch_type"] = MismatchType.UNAVAILABLE
            result["acquisition_difficulty"] = "hard"
            result["commercial_reasoning"] += (
                f" The exact handle @{brand_slug} is held by an active account, "
                f"making acquisition more difficult and expensive."
            )

    elif ideal_handle_available:
        result["acquisition_difficulty"] = "easy"
        result["commercial_reasoning"] += (
            f" The exact handle @{brand_slug} appears to be available for registration."
        )

    return result


def _check_dormancy(
    last_post_date: Optional[str] = None,
    follower_count: Optional[int] = None,
    post_count: Optional[int] = None,
) -> dict:
    """
    Determine if an account is dormant based on activity signals.

    Returns:
        {is_dormant: bool, months_dormant: int or None, confidence: float}
    """
    result = {"is_dormant": False, "months_dormant": None, "confidence": 0.0}

    if last_post_date:
        try:
            if isinstance(last_post_date, str):
                # Handle various ISO format strings
                date_str = last_post_date.replace("Z", "+00:00")
                # Ensure timezone info for Python 3.10 compatibility
                last_post = datetime.fromisoformat(date_str)
                if last_post.tzinfo is None:
                    last_post = last_post.replace(tzinfo=timezone.utc)
            else:
                last_post = last_post_date
                if last_post.tzinfo is None:
                    last_post = last_post.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            months_since = (now.year - last_post.year) * 12 + (now.month - last_post.month)

            result["months_dormant"] = months_since

            if months_since >= DORMANCY_THRESHOLD_MONTHS:
                result["is_dormant"] = True
                result["confidence"] = min(0.5 + (months_since - DORMANCY_THRESHOLD_MONTHS) * 0.05, 1.0)

        except (ValueError, TypeError) as e:
            logger.warning("dormancy_date_parse_error", error=str(e))
            pass

    # Low post count + low followers = likely dormant even without date
    if post_count is not None and post_count <= 5:
        if follower_count is not None and follower_count < 100:
            result["is_dormant"] = True
            result["confidence"] = max(result["confidence"], 0.6)

    return result


def calculate_cross_platform_severity(handle_records: list[dict]) -> float:
    """
    Calculate an aggregate severity score across all platforms for a company.

    Inconsistency across platforms is worse than a single platform mismatch.

    Args:
        handle_records: List of handle analysis dicts (from detect_mismatch)

    Returns:
        Cross-platform severity score (0.0-1.0)
    """
    if not handle_records:
        return 0.0

    severities = [r.get("mismatch_severity", 0) for r in handle_records]
    mismatch_count = sum(1 for s in severities if s > 0)
    has_dormant = any(r.get("account_dormant", False) for r in handle_records)

    # Base: average severity
    avg_severity = sum(severities) / len(severities) if severities else 0

    # Bonus for inconsistency across platforms
    inconsistency_bonus = min(mismatch_count * 0.1, 0.3)

    # Bonus for having a dormant holder on any platform
    dormant_bonus = 0.15 if has_dormant else 0

    total = min(avg_severity + inconsistency_bonus + dormant_bonus, 1.0)

    logger.debug(
        "cross_platform_severity",
        avg_severity=round(avg_severity, 3),
        mismatch_count=mismatch_count,
        has_dormant=has_dormant,
        total=round(total, 3),
    )

    return total
