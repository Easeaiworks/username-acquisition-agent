"""
Event trigger dispatcher — fires workflow triggers when pipeline events occur.
"""
import structlog
from typing import Any

logger = structlog.get_logger()

# Event types
LEAD_SCORED = "lead_scored"
COMPANY_APPROVED = "company_approved"
OUTREACH_SENT = "outreach_sent"
STAGE_CHANGED = "stage_changed"
SCORE_THRESHOLD = "score_threshold"
COMPANY_ADDED = "company_added"
CONTACT_ENRICHED = "contact_enriched"

ALL_EVENTS = [LEAD_SCORED, COMPANY_APPROVED, OUTREACH_SENT, STAGE_CHANGED, SCORE_THRESHOLD, COMPANY_ADDED, CONTACT_ENRICHED]


async def fire_trigger(event_type: str, data: dict[str, Any]) -> list[str]:
    """
    Fire a trigger event. Finds all enabled workflows matching this trigger type,
    evaluates their conditions, and executes matching ones.

    Returns list of workflow_run IDs that were executed.
    """
    from app.automations.engine import execute_matching_workflows

    logger.info("trigger_fired", event_type=event_type, data_keys=list(data.keys()))

    try:
        run_ids = await execute_matching_workflows(event_type, data)
        logger.info("trigger_completed", event_type=event_type, workflows_executed=len(run_ids))
        return run_ids
    except Exception as e:
        logger.error("trigger_failed", event_type=event_type, error=str(e))
        return []


async def fire_webhook_event(event_type: str, payload: dict) -> int:
    """
    Dispatch a webhook event to all subscribed endpoints.
    Returns number of webhooks dispatched.
    """
    from app.automations.webhooks import dispatch_webhooks

    try:
        count = await dispatch_webhooks(event_type, payload)
        return count
    except Exception as e:
        logger.error("webhook_dispatch_failed", event_type=event_type, error=str(e))
        return 0
