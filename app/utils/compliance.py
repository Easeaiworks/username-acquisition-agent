"""
Compliance utilities — CAN-SPAM, GDPR, suppression list management.
Every outreach action passes through these checks before execution.
"""

from datetime import datetime, timedelta
from app.database import get_service_client
from app.config import settings
import structlog

logger = structlog.get_logger()


async def is_suppressed(email: str = None, domain: str = None) -> bool:
    """Check if an email or domain is on the suppression list.
    Returns True if the contact should NOT be contacted.
    """
    db = get_service_client()

    if email:
        result = db.table("suppression_list").select("id").eq("email", email.lower()).execute()
        if result.data:
            logger.info("contact_suppressed", email=email, reason="suppression_list")
            return True

    if domain:
        result = db.table("suppression_list").select("id").eq("domain", domain.lower()).execute()
        if result.data:
            logger.info("domain_suppressed", domain=domain, reason="suppression_list")
            return True

    return False


async def check_touch_limit(contact_id: str) -> bool:
    """Check if a contact has reached the maximum number of outreach touches.
    Returns True if MORE outreach is allowed, False if limit reached.
    """
    db = get_service_client()
    result = (
        db.table("outreach_sequences")
        .select("id", count="exact")
        .eq("contact_id", contact_id)
        .in_("status", ["sent", "delivered", "opened", "clicked", "replied"])
        .execute()
    )
    touch_count = result.count or 0
    allowed = touch_count < settings.max_touches_per_contact

    if not allowed:
        logger.info(
            "touch_limit_reached",
            contact_id=contact_id,
            touches=touch_count,
            max=settings.max_touches_per_contact,
        )

    return allowed


async def check_cooldown(contact_id: str) -> bool:
    """Check if a contact is within the cooldown period after last outreach.
    Returns True if outreach is allowed, False if still in cooldown.
    """
    db = get_service_client()
    cutoff = datetime.utcnow() - timedelta(days=settings.outreach_cooldown_days)

    result = (
        db.table("outreach_sequences")
        .select("sent_at")
        .eq("contact_id", contact_id)
        .eq("status", "replied")
        .gte("sent_at", cutoff.isoformat())
        .order("sent_at", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        logger.info(
            "contact_in_cooldown",
            contact_id=contact_id,
            last_reply=result.data[0]["sent_at"],
        )
        return False

    return True


async def check_same_day_multi_channel(contact_id: str, channel: str) -> bool:
    """Prevent sending on multiple channels on the same day.
    Returns True if this channel is allowed today, False if another channel was used.
    """
    db = get_service_client()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    result = (
        db.table("outreach_sequences")
        .select("channel")
        .eq("contact_id", contact_id)
        .neq("channel", channel)
        .gte("sent_at", today_start.isoformat())
        .in_("status", ["sent", "delivered", "opened", "clicked"])
        .limit(1)
        .execute()
    )

    if result.data:
        logger.info(
            "multi_channel_same_day_blocked",
            contact_id=contact_id,
            requested_channel=channel,
            already_used=result.data[0]["channel"],
        )
        return False

    return True


async def add_to_suppression_list(
    email: str = None,
    domain: str = None,
    company_name: str = None,
    reason: str = "manual",
) -> None:
    """Add an email or domain to the suppression list."""
    db = get_service_client()
    record = {
        "reason": reason,
        "added_at": datetime.utcnow().isoformat(),
    }
    if email:
        record["email"] = email.lower()
    if domain:
        record["domain"] = domain.lower()
    if company_name:
        record["company_name"] = company_name

    db.table("suppression_list").insert(record).execute()
    logger.info("added_to_suppression", email=email, domain=domain, reason=reason)


async def can_send_outreach(contact_id: str, email: str, channel: str) -> tuple[bool, str]:
    """Master compliance check — run all checks before any outreach.
    Returns (allowed: bool, reason: str).
    """
    # Check suppression list
    if await is_suppressed(email=email):
        return False, "suppressed"

    # Check domain suppression
    if email and "@" in email:
        domain = email.split("@")[1]
        if await is_suppressed(domain=domain):
            return False, "domain_suppressed"

    # Check touch limit
    if not await check_touch_limit(contact_id):
        return False, "touch_limit_reached"

    # Check cooldown
    if not await check_cooldown(contact_id):
        return False, "in_cooldown"

    # Check same-day multi-channel
    if not await check_same_day_multi_channel(contact_id, channel):
        return False, "multi_channel_same_day"

    return True, "approved"
