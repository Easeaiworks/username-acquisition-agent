"""
Outreach Sequence Manager — orchestrates multi-step email sequences.

This is Engine B's core: it takes qualified companies with enriched contacts,
generates personalized outreach, sends via Instantly.ai/Smartlead, tracks
delivery/opens/replies, classifies responses, and books meetings.

Autonomy model:
    Critical (>0.8) + Very High (0.65-0.8) → auto-send, no approval needed
    High (0.5-0.65) → requires manual approval from dashboard
    Medium/Low (<0.5) → parked, not outreached

Sequence flow per contact:
    1. Generate message → 2. Compliance check → 3. Send → 4. Track
    → 5. If reply: classify → 6. If positive: book meeting
    → 7. If no reply after delay: next step (up to 4 touches)

Follow-up delays: Step 1→2: 3 days, Step 2→3: 4 days, Step 3→4: 5 days
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

import structlog

from app.config import settings
from app.database import get_service_client
from app.engine_b.message_generator import generate_outreach_message
from app.engine_b.reply_classifier import classify_reply
from app.utils.compliance import can_send_outreach, add_to_suppression_list

logger = structlog.get_logger()

# Follow-up delays in days (step_number → days to wait)
FOLLOWUP_DELAYS = {
    1: 3,   # After step 1, wait 3 days for step 2
    2: 4,   # After step 2, wait 4 days for step 3
    3: 5,   # After step 3, wait 5 days for step 4
}

MAX_SEQUENCE_STEPS = 4


async def create_outreach_sequence(
    company: dict,
    contact: dict,
    auto_send: bool = False,
) -> Optional[dict]:
    """
    Create the first outreach message for a contact.

    Args:
        company: Company dict with handle/platform data
        contact: Contact dict with name, email, title
        auto_send: If True, send immediately (for Critical/Very High)

    Returns:
        Outreach record dict or None if blocked by compliance
    """
    contact_id = contact["id"]
    company_id = company["id"]
    email = contact.get("email")

    if not email:
        logger.warning("no_email_for_contact", contact_id=contact_id)
        return None

    # Run compliance checks
    allowed, reason = await can_send_outreach(contact_id, email, "email")
    if not allowed:
        logger.info(
            "outreach_blocked_compliance",
            contact_id=contact_id,
            reason=reason,
        )
        return None

    # Gather platform details for message personalization
    platform_details = await _get_platform_details(company_id)

    # Generate the first message
    message = await generate_outreach_message(
        company_name=company.get("brand_name", ""),
        contact_name=contact.get("full_name", ""),
        contact_title=contact.get("title", ""),
        platform_details=platform_details,
        sequence_step=1,
        industry=company.get("industry"),
        company_size=company.get("employee_range"),
    )

    # Create outreach record
    now = datetime.now(timezone.utc)
    record = {
        "contact_id": contact_id,
        "company_id": company_id,
        "channel": "email",
        "sequence_step": 1,
        "max_steps": MAX_SEQUENCE_STEPS,
        "subject": message.get("subject", ""),
        "message_body": message.get("body", ""),
        "message_variant": message.get("model", "unknown"),
        "personalization_data": {
            "platform_details": platform_details,
            "brand_name": company.get("brand_name"),
            "industry": company.get("industry"),
        },
        "status": "draft",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    if auto_send:
        record["status"] = "scheduled"
        record["scheduled_at"] = now.isoformat()

    # Save to database
    try:
        db = get_service_client()
        result = db.table("outreach_sequences").insert(record).execute()

        if result.data:
            outreach_id = result.data[0]["id"]
            logger.info(
                "outreach_created",
                outreach_id=outreach_id,
                company=company.get("brand_name"),
                contact=contact.get("full_name"),
                auto_send=auto_send,
            )

            # If auto-send, dispatch immediately
            if auto_send:
                await _send_email(outreach_id, record)

            return result.data[0]

    except Exception as e:
        logger.error("outreach_create_error", error=str(e))
        return None


async def process_followups() -> dict:
    """
    Process scheduled follow-ups for all active sequences.

    Called by the daily pipeline. Finds contacts where:
    - Last message was sent
    - No reply received
    - Enough time has passed (per FOLLOWUP_DELAYS)
    - Haven't reached MAX_SEQUENCE_STEPS

    Returns:
        Summary of follow-ups processed
    """
    db = get_service_client()
    now = datetime.now(timezone.utc)

    sent_count = 0
    skipped_count = 0
    errors = 0

    try:
        # Find outreach records that need follow-up
        result = (
            db.table("outreach_sequences")
            .select("*, contacts(*), companies(*)")
            .in_("status", ["sent", "delivered", "opened"])
            .lt("sequence_step", MAX_SEQUENCE_STEPS)
            .is_("next_followup_at", "null")  # Not yet scheduled
            .order("sent_at", desc=False)
            .limit(200)
            .execute()
        )

        for outreach in result.data:
            step = outreach.get("sequence_step", 1)
            sent_at = outreach.get("sent_at")

            if not sent_at:
                continue

            # Calculate if enough time has passed
            delay_days = FOLLOWUP_DELAYS.get(step, 4)
            sent_time = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
            followup_due = sent_time + timedelta(days=delay_days)

            if now < followup_due:
                continue  # Not time yet

            # Create the next step
            try:
                contact = outreach.get("contacts", {})
                company = outreach.get("companies", {})

                if not contact or not company:
                    skipped_count += 1
                    continue

                next_step = step + 1

                # Compliance re-check before follow-up
                email = contact.get("email")
                allowed, reason = await can_send_outreach(
                    contact["id"], email, "email"
                )
                if not allowed:
                    skipped_count += 1
                    continue

                # Generate follow-up message
                platform_details = await _get_platform_details(company["id"])
                message = await generate_outreach_message(
                    company_name=company.get("brand_name", ""),
                    contact_name=contact.get("full_name", ""),
                    contact_title=contact.get("title", ""),
                    platform_details=platform_details,
                    sequence_step=next_step,
                    industry=company.get("industry"),
                    company_size=company.get("employee_range"),
                )

                # Create follow-up record
                followup_record = {
                    "contact_id": contact["id"],
                    "company_id": company["id"],
                    "channel": "email",
                    "sequence_step": next_step,
                    "max_steps": MAX_SEQUENCE_STEPS,
                    "subject": message.get("subject", ""),
                    "message_body": message.get("body", ""),
                    "message_variant": message.get("model", "unknown"),
                    "personalization_data": outreach.get("personalization_data", {}),
                    "status": "scheduled",
                    "scheduled_at": now.isoformat(),
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }

                db.table("outreach_sequences").insert(followup_record).execute()
                sent_count += 1

                # Mark original as having scheduled follow-up
                db.table("outreach_sequences").update({
                    "next_followup_at": now.isoformat(),
                }).eq("id", outreach["id"]).execute()

            except Exception as e:
                logger.error("followup_error", outreach_id=outreach.get("id"), error=str(e))
                errors += 1

    except Exception as e:
        logger.error("process_followups_error", error=str(e))
        return {"status": "error", "error": str(e)}

    summary = {
        "followups_sent": sent_count,
        "skipped": skipped_count,
        "errors": errors,
    }

    logger.info("followups_processed", **summary)
    return summary


async def handle_reply(
    outreach_id: str,
    reply_text: str,
) -> dict:
    """
    Process an incoming reply to an outreach message.

    1. Classify the reply
    2. Update the outreach record
    3. Take the appropriate action (book meeting, stop sequence, suppress, etc.)

    Args:
        outreach_id: The outreach sequence record ID
        reply_text: The reply email content

    Returns:
        Processing result dict
    """
    db = get_service_client()

    # Get the outreach record
    outreach = db.table("outreach_sequences").select("*").eq("id", outreach_id).execute()
    if not outreach.data:
        return {"error": "outreach_not_found"}

    record = outreach.data[0]

    # Classify the reply
    classification = await classify_reply(
        reply_text=reply_text,
        original_subject=record.get("subject"),
        original_body=record.get("message_body"),
    )

    sentiment = classification.get("classification", "neutral")
    now = datetime.now(timezone.utc)

    # Map classification to our sentiment enum
    sentiment_map = {
        "positive": "positive",
        "neutral": "neutral",
        "negative": "negative",
        "objection": "objection",
        "ooo": "neutral",
        "unsubscribe": "negative",
    }

    # Update the outreach record
    update_data = {
        "status": "replied",
        "response_text": reply_text[:2000],  # Truncate for storage
        "response_sentiment": sentiment_map.get(sentiment, "neutral"),
        "response_classified_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    db.table("outreach_sequences").update(update_data).eq("id", outreach_id).execute()

    # Take action based on classification
    action_result = await _execute_reply_action(
        record=record,
        classification=classification,
    )

    logger.info(
        "reply_processed",
        outreach_id=outreach_id,
        sentiment=sentiment,
        action=action_result.get("action"),
    )

    return {
        "outreach_id": outreach_id,
        "classification": classification,
        "action_taken": action_result,
    }


async def run_auto_outreach(
    threshold: Optional[float] = None,
) -> dict:
    """
    Run auto-outreach for all qualified companies above the threshold.

    This is called by the daily pipeline. It:
    1. Finds companies that are qualified + approved for outreach
    2. Gets their top-priority contacts
    3. Creates and sends outreach sequences

    Args:
        threshold: Min score for auto-send (default: settings.auto_outreach_threshold)

    Returns:
        Auto-outreach run summary
    """
    threshold = threshold or settings.auto_outreach_threshold
    db = get_service_client()

    try:
        # Find qualified companies ready for outreach
        companies = (
            db.table("companies")
            .select("*")
            .eq("pipeline_stage", "qualified")
            .eq("approved_for_outreach", True)
            .gte("total_opportunity_score", threshold)
            .order("total_opportunity_score", desc=True)
            .limit(50)
            .execute()
        )

        if not companies.data:
            return {"status": "completed", "sequences_created": 0}

        sequences_created = 0
        errors = 0

        for company in companies.data:
            try:
                # Get top contact for this company
                contacts = (
                    db.table("contacts")
                    .select("*")
                    .eq("company_id", company["id"])
                    .eq("do_not_contact", False)
                    .order("outreach_priority", desc=False)
                    .limit(1)
                    .execute()
                )

                if not contacts.data:
                    continue

                contact = contacts.data[0]

                # Check if we already have an active sequence for this contact
                existing = (
                    db.table("outreach_sequences")
                    .select("id")
                    .eq("contact_id", contact["id"])
                    .in_("status", ["draft", "scheduled", "sent", "delivered", "opened"])
                    .limit(1)
                    .execute()
                )

                if existing.data:
                    continue  # Already has active outreach

                # Create and auto-send
                result = await create_outreach_sequence(
                    company=company,
                    contact=contact,
                    auto_send=True,
                )

                if result:
                    sequences_created += 1

                    # Move company to outreach stage
                    db.table("companies").update({
                        "pipeline_stage": "outreach",
                    }).eq("id", company["id"]).execute()

            except Exception as e:
                logger.error("auto_outreach_company_error", company_id=company["id"], error=str(e))
                errors += 1

        summary = {
            "status": "completed",
            "companies_processed": len(companies.data),
            "sequences_created": sequences_created,
            "errors": errors,
        }

        logger.info("auto_outreach_complete", **summary)
        return summary

    except Exception as e:
        logger.error("auto_outreach_error", error=str(e))
        return {"status": "error", "error": str(e)}


async def _get_platform_details(company_id: str) -> list[dict]:
    """Fetch platform handle details for message personalization."""
    try:
        db = get_service_client()
        result = (
            db.table("platform_handles")
            .select("platform, mismatch_type, mismatch_severity, handle_available, account_dormant")
            .eq("company_id", company_id)
            .gt("mismatch_severity", 0)
            .order("mismatch_severity", desc=True)
            .execute()
        )

        details = []
        for h in result.data:
            mtype = h.get("mismatch_type", "none")
            issue = {
                "modifier": "uses a modified version of the brand handle",
                "different": "uses a completely different handle than the brand name",
                "inactive_holder": "ideal handle held by an inactive account",
                "unavailable": "ideal handle taken by another account",
                "not_present": "has no presence on this platform",
            }.get(mtype, "handle mismatch detected")

            details.append({
                "platform": h.get("platform"),
                "issue": issue,
                "handle_available": h.get("handle_available"),
                "dormant": h.get("account_dormant"),
            })

        return details

    except Exception as e:
        logger.error("get_platform_details_error", error=str(e))
        return []


async def _send_email(outreach_id: str, record: dict) -> bool:
    """
    Send an email via Instantly.ai or Smartlead.

    For now, this marks the record as 'sent' in the DB.
    The actual email sending integration will use the Instantly.ai or
    Smartlead API when those keys are configured.
    """
    try:
        db = get_service_client()
        now = datetime.now(timezone.utc)

        # TODO: Integrate with Instantly.ai or Smartlead API
        # For now, mark as sent (actual sending happens when API keys are configured)
        if settings.instantly_api_key or settings.smartlead_api_key:
            # Placeholder for actual API call
            logger.info("email_sending_via_provider", outreach_id=outreach_id)
            # await _send_via_instantly(record)  # TODO
            # await _send_via_smartlead(record)  # TODO

        db.table("outreach_sequences").update({
            "status": "sent",
            "sent_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }).eq("id", outreach_id).execute()

        logger.info("email_sent", outreach_id=outreach_id)
        return True

    except Exception as e:
        logger.error("send_email_error", outreach_id=outreach_id, error=str(e))

        db = get_service_client()
        db.table("outreach_sequences").update({
            "status": "failed",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", outreach_id).execute()

        return False


async def _execute_reply_action(record: dict, classification: dict) -> dict:
    """Execute the appropriate action based on reply classification."""
    sentiment = classification.get("classification", "neutral")
    contact_id = record.get("contact_id")
    company_id = record.get("company_id")
    db = get_service_client()

    if sentiment == "positive":
        # Book meeting — update company stage
        calendly_url = settings.calendly_event_url or "https://calendly.com/sean"
        db.table("companies").update({
            "pipeline_stage": "meeting",
        }).eq("id", company_id).execute()

        return {
            "action": "meeting_requested",
            "calendly_url": calendly_url,
            "message": "Positive reply — send Calendly link to book meeting",
        }

    elif sentiment == "negative":
        # Stop all outreach, add cooldown
        return {
            "action": "sequence_stopped",
            "message": "Negative reply — stopping outreach sequence",
        }

    elif sentiment == "unsubscribe":
        # Immediately suppress
        contact = db.table("contacts").select("email").eq("id", contact_id).execute()
        if contact.data:
            email = contact.data[0].get("email")
            if email:
                await add_to_suppression_list(
                    email=email,
                    reason="unsubscribe_reply",
                )
        return {
            "action": "suppressed",
            "message": "Unsubscribe request — added to suppression list",
        }

    elif sentiment == "objection":
        return {
            "action": "flagged_for_review",
            "objection_type": classification.get("objection_type"),
            "message": "Objection raised — flagged for Sean's review",
        }

    elif sentiment == "ooo":
        return {
            "action": "sequence_paused",
            "return_date": classification.get("return_date"),
            "message": "Out of office — sequence paused",
        }

    else:
        return {
            "action": "continue_sequence",
            "message": "Neutral reply — continuing sequence",
        }
