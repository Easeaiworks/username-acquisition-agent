"""
Action handlers — each action type has a handler function that executes
a specific side-effect (email send, webhook fire, stage update, etc.).

Every handler has the signature:

    async def handle_<action_type>(config: dict, trigger_data: dict) -> dict

Returns:
    {"success": bool, "message": str, "details": dict}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

import httpx
import structlog

from app.database import get_service_client

logger = structlog.get_logger()

# Type alias for action handler functions
ActionHandler = Callable[[dict, dict], Awaitable[dict]]


# ---------------------------------------------------------------------------
# Registry — maps action type strings to handler functions
# ---------------------------------------------------------------------------

_ACTION_REGISTRY: dict[str, ActionHandler] = {}


def register_action(action_type: str):
    """Decorator to register an action handler."""
    def decorator(fn: ActionHandler) -> ActionHandler:
        _ACTION_REGISTRY[action_type] = fn
        return fn
    return decorator


def get_action_handler(action_type: str) -> ActionHandler | None:
    """Look up the handler for an action type."""
    return _ACTION_REGISTRY.get(action_type)


def list_action_types() -> list[str]:
    """Return all registered action type names."""
    return sorted(_ACTION_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Action: email_add_contact
# ---------------------------------------------------------------------------

@register_action("email_add_contact")
async def handle_email_add_contact(config: dict, trigger_data: dict) -> dict:
    """
    Add a contact to the email_contacts table and optionally to a list.

    Config keys:
        email (str, optional): Contact email — falls back to trigger_data
        first_name (str, optional): Contact first name
        last_name (str, optional): Contact last name
        company (str, optional): Company name
        tags (list[str], optional): Tags to assign to the contact
        list_id (str, optional): If provided, also add as a member of this list
    """
    try:
        email = (
            config.get("email")
            or trigger_data.get("email")
            or trigger_data.get("contact_email")
        )
        if not email:
            return {"success": False, "message": "No email provided in config or trigger data", "details": {}}

        first_name = config.get("first_name") or trigger_data.get("first_name", "")
        last_name = config.get("last_name") or trigger_data.get("last_name", "")
        company = config.get("company") or trigger_data.get("company_name", "")
        tags = config.get("tags", [])

        now = datetime.now(timezone.utc).isoformat()

        db = get_service_client()

        # Upsert into email_contacts
        contact_data = {
            "email": email.lower().strip(),
            "first_name": first_name,
            "last_name": last_name,
            "company": company,
            "tags": tags,
            "subscribed": True,
            "created_at": now,
            "updated_at": now,
        }

        result = db.table("email_contacts").upsert(
            contact_data,
            on_conflict="email",
        ).execute()

        contact_id = result.data[0]["id"] if result.data else None

        # Optionally add to a list
        list_id = config.get("list_id")
        list_added = False
        if list_id and contact_id:
            db.table("email_list_members").upsert(
                {
                    "list_id": list_id,
                    "contact_id": contact_id,
                    "subscribed": True,
                    "joined_at": now,
                },
                on_conflict="list_id,contact_id",
            ).execute()
            list_added = True

        return {
            "success": True,
            "message": f"Contact {email} added" + (f" and joined list {list_id}" if list_added else ""),
            "details": {
                "contact_id": contact_id,
                "email": email,
                "list_id": list_id if list_added else None,
            },
        }

    except Exception as e:
        logger.error("email_add_contact_error", error=str(e))
        return {"success": False, "message": str(e), "details": {}}


# ---------------------------------------------------------------------------
# Action: email_add_tags
# ---------------------------------------------------------------------------

@register_action("email_add_tags")
async def handle_email_add_tags(config: dict, trigger_data: dict) -> dict:
    """
    Add tags to an existing contact in the email_contacts table.

    Config keys:
        email (str, optional): Contact email — falls back to trigger_data
        tags (list[str], required): Tags to add
    """
    try:
        tags = config.get("tags", [])
        if not tags:
            return {"success": False, "message": "tags list is required and must not be empty", "details": {}}

        email = (
            config.get("email")
            or trigger_data.get("email")
            or trigger_data.get("contact_email")
        )
        if not email:
            return {"success": False, "message": "No email provided in config or trigger data", "details": {}}

        email = email.lower().strip()
        db = get_service_client()

        # Fetch existing contact to merge tags
        existing = (
            db.table("email_contacts")
            .select("id, tags")
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        if not existing.data:
            return {
                "success": False,
                "message": f"Contact {email} not found — add them first",
                "details": {},
            }

        current_tags = existing.data.get("tags") or []
        merged_tags = list(set(current_tags + tags))

        db.table("email_contacts").update({
            "tags": merged_tags,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("email", email).execute()

        new_tags = [t for t in tags if t not in current_tags]

        return {
            "success": True,
            "message": f"Tags updated for {email}: added {new_tags}" if new_tags else f"Tags for {email} unchanged (already present)",
            "details": {
                "email": email,
                "tags_added": new_tags,
                "all_tags": merged_tags,
            },
        }

    except Exception as e:
        logger.error("email_add_tags_error", error=str(e))
        return {"success": False, "message": str(e), "details": {}}


# ---------------------------------------------------------------------------
# Action: email_send
# ---------------------------------------------------------------------------

@register_action("email_send")
async def handle_email_send(config: dict, trigger_data: dict) -> dict:
    """
    Send a one-off email using the built-in email sender.

    Config keys:
        to_email (str, optional): Recipient — falls back to trigger_data
        subject (str, required): Email subject line
        html_content (str, required): HTML body of the email
        from_name (str, optional): Sender display name
        from_email (str, optional): Sender email address
    """
    try:
        to_email = (
            config.get("to_email")
            or trigger_data.get("email")
            or trigger_data.get("contact_email")
        )
        if not to_email:
            return {"success": False, "message": "No recipient email provided", "details": {}}

        subject = config.get("subject")
        html_content = config.get("html_content")
        if not subject or not html_content:
            return {"success": False, "message": "subject and html_content are required", "details": {}}

        from app.email.sender import get_default_sender, EmailMessage
        from app.email.tracking import inject_tracking, generate_unsubscribe_url
        from app.email.template_engine import strip_html

        sender = get_default_sender()

        # Inject tracking pixels and unsubscribe link into the HTML
        unsubscribe_url = generate_unsubscribe_url(to_email)
        tracked_html = inject_tracking(html_content, metadata={
            "to_email": to_email,
            "subject": subject,
        })

        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html_content=tracked_html,
            text_content=strip_html(html_content),
            from_name=config.get("from_name"),
            from_email=config.get("from_email"),
            unsubscribe_url=unsubscribe_url,
        )

        result = await sender.send(message)

        # Log the send event in the database
        try:
            db = get_service_client()
            db.table("email_events").insert({
                "email": to_email,
                "event_type": "sent",
                "subject": subject,
                "message_id": getattr(result, "message_id", None),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception as log_err:
            logger.warning("email_event_log_failed", error=str(log_err))

        return {
            "success": result.success,
            "message": f"Email sent to {to_email}: {subject}" if result.success else f"Email send failed: {result.error}",
            "details": {
                "to_email": to_email,
                "subject": subject,
                "message_id": getattr(result, "message_id", None),
            },
        }

    except Exception as e:
        logger.error("email_send_error", error=str(e))
        return {"success": False, "message": str(e), "details": {}}


# ---------------------------------------------------------------------------
# Action: email_enroll_sequence
# ---------------------------------------------------------------------------

@register_action("email_enroll_sequence")
async def handle_email_enroll_sequence(config: dict, trigger_data: dict) -> dict:
    """
    Enroll a contact into a drip email sequence.

    Config keys:
        email (str, optional): Contact email — falls back to trigger_data
        sequence_id (str, required): ID of the email sequence to enroll in
    """
    try:
        sequence_id = config.get("sequence_id")
        if not sequence_id:
            return {"success": False, "message": "sequence_id is required", "details": {}}

        email = (
            config.get("email")
            or trigger_data.get("email")
            or trigger_data.get("contact_email")
        )
        if not email:
            return {"success": False, "message": "No email provided in config or trigger data", "details": {}}

        email = email.lower().strip()
        db = get_service_client()

        # Verify the contact exists
        contact = (
            db.table("email_contacts")
            .select("id")
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        if not contact.data:
            return {
                "success": False,
                "message": f"Contact {email} not found — add them first",
                "details": {},
            }

        contact_id = contact.data["id"]

        # Verify the sequence exists
        sequence = (
            db.table("email_sequences")
            .select("id, name")
            .eq("id", sequence_id)
            .maybe_single()
            .execute()
        )
        if not sequence.data:
            return {
                "success": False,
                "message": f"Sequence {sequence_id} not found",
                "details": {},
            }

        now = datetime.now(timezone.utc).isoformat()

        # Check for existing enrollment to avoid duplicates
        existing = (
            db.table("email_sequence_enrollments")
            .select("id, status")
            .eq("contact_id", contact_id)
            .eq("sequence_id", sequence_id)
            .maybe_single()
            .execute()
        )
        if existing.data and existing.data.get("status") == "active":
            return {
                "success": True,
                "message": f"{email} is already enrolled in sequence '{sequence.data['name']}'",
                "details": {
                    "enrollment_id": existing.data["id"],
                    "already_enrolled": True,
                },
            }

        # Create or re-activate enrollment
        enrollment_data = {
            "contact_id": contact_id,
            "sequence_id": sequence_id,
            "status": "active",
            "current_step": 0,
            "enrolled_at": now,
            "updated_at": now,
        }

        if existing.data:
            # Re-enroll: reset and reactivate
            result = (
                db.table("email_sequence_enrollments")
                .update(enrollment_data)
                .eq("id", existing.data["id"])
                .execute()
            )
        else:
            result = (
                db.table("email_sequence_enrollments")
                .insert(enrollment_data)
                .execute()
            )

        enrollment_id = result.data[0]["id"] if result.data else None

        return {
            "success": True,
            "message": f"{email} enrolled in sequence '{sequence.data['name']}'",
            "details": {
                "enrollment_id": enrollment_id,
                "contact_id": contact_id,
                "sequence_id": sequence_id,
                "sequence_name": sequence.data["name"],
            },
        }

    except Exception as e:
        logger.error("email_enroll_sequence_error", error=str(e))
        return {"success": False, "message": str(e), "details": {}}


# ---------------------------------------------------------------------------
# Action: email_remove_contact
# ---------------------------------------------------------------------------

@register_action("email_remove_contact")
async def handle_email_remove_contact(config: dict, trigger_data: dict) -> dict:
    """
    Remove a contact from a specific list, or unsubscribe them entirely.

    Config keys:
        email (str, optional): Contact email — falls back to trigger_data
        list_id (str, optional): Remove from this specific list only
        unsubscribe (bool, optional): If True, mark the contact as unsubscribed
            globally. Default False.
    """
    try:
        email = (
            config.get("email")
            or trigger_data.get("email")
            or trigger_data.get("contact_email")
        )
        if not email:
            return {"success": False, "message": "No email provided in config or trigger data", "details": {}}

        email = email.lower().strip()
        list_id = config.get("list_id")
        unsubscribe = config.get("unsubscribe", False)

        db = get_service_client()

        # Look up the contact
        contact = (
            db.table("email_contacts")
            .select("id")
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        if not contact.data:
            return {
                "success": False,
                "message": f"Contact {email} not found",
                "details": {},
            }

        contact_id = contact.data["id"]
        now = datetime.now(timezone.utc).isoformat()
        actions_taken = []

        # Remove from specific list
        if list_id:
            db.table("email_list_members").delete().eq(
                "contact_id", contact_id
            ).eq("list_id", list_id).execute()
            actions_taken.append(f"removed from list {list_id}")

        # Global unsubscribe
        if unsubscribe:
            db.table("email_contacts").update({
                "subscribed": False,
                "updated_at": now,
            }).eq("id", contact_id).execute()

            # Cancel any active sequence enrollments
            db.table("email_sequence_enrollments").update({
                "status": "cancelled",
                "updated_at": now,
            }).eq("contact_id", contact_id).eq("status", "active").execute()

            actions_taken.append("unsubscribed globally")

        if not actions_taken:
            return {
                "success": False,
                "message": "Specify list_id to remove from a list, or unsubscribe=true to unsubscribe globally",
                "details": {},
            }

        return {
            "success": True,
            "message": f"Contact {email}: {', '.join(actions_taken)}",
            "details": {
                "email": email,
                "contact_id": contact_id,
                "actions": actions_taken,
            },
        }

    except Exception as e:
        logger.error("email_remove_contact_error", error=str(e))
        return {"success": False, "message": str(e), "details": {}}


# ---------------------------------------------------------------------------
# Action: email_update_contact
# ---------------------------------------------------------------------------

@register_action("email_update_contact")
async def handle_email_update_contact(config: dict, trigger_data: dict) -> dict:
    """
    Update fields on an existing email contact.

    Config keys:
        email (str, optional): Contact email — falls back to trigger_data
        fields (dict, required): Fields to update. Supported keys:
            first_name, last_name, company, custom_fields (dict)
    """
    try:
        email = (
            config.get("email")
            or trigger_data.get("email")
            or trigger_data.get("contact_email")
        )
        if not email:
            return {"success": False, "message": "No email provided in config or trigger data", "details": {}}

        fields = config.get("fields")
        if not fields or not isinstance(fields, dict):
            return {"success": False, "message": "fields dict is required", "details": {}}

        email = email.lower().strip()
        db = get_service_client()

        # Verify contact exists
        existing = (
            db.table("email_contacts")
            .select("id, custom_fields")
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        if not existing.data:
            return {
                "success": False,
                "message": f"Contact {email} not found",
                "details": {},
            }

        # Build update payload from allowed fields
        allowed_direct_fields = {"first_name", "last_name", "company"}
        update_data: dict[str, Any] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        updated_keys = []

        for key in allowed_direct_fields:
            if key in fields:
                update_data[key] = fields[key]
                updated_keys.append(key)

        # Merge custom_fields
        if "custom_fields" in fields and isinstance(fields["custom_fields"], dict):
            current_custom = existing.data.get("custom_fields") or {}
            merged_custom = {**current_custom, **fields["custom_fields"]}
            update_data["custom_fields"] = merged_custom
            updated_keys.append("custom_fields")

        if not updated_keys:
            return {
                "success": False,
                "message": "No recognized fields to update (allowed: first_name, last_name, company, custom_fields)",
                "details": {},
            }

        db.table("email_contacts").update(update_data).eq("email", email).execute()

        return {
            "success": True,
            "message": f"Contact {email} updated: {', '.join(updated_keys)}",
            "details": {
                "email": email,
                "fields_updated": updated_keys,
            },
        }

    except Exception as e:
        logger.error("email_update_contact_error", error=str(e))
        return {"success": False, "message": str(e), "details": {}}


# ---------------------------------------------------------------------------
# Action: webhook_fire
# ---------------------------------------------------------------------------

@register_action("webhook_fire")
async def handle_webhook_fire(config: dict, trigger_data: dict) -> dict:
    """
    Fire a one-off webhook to a URL with the trigger data as payload.

    Config keys:
        url (str, required): Target URL
        method (str, optional): HTTP method — default POST
        headers (dict, optional): Extra headers
        include_trigger_data (bool, optional): Include full trigger data — default True
        custom_payload (dict, optional): Override payload entirely
    """
    try:
        url = config.get("url")
        if not url:
            return {"success": False, "message": "url is required", "details": {}}

        method = config.get("method", "POST").upper()
        headers = dict(config.get("headers", {}))
        headers.setdefault("Content-Type", "application/json")

        if config.get("custom_payload"):
            payload = config["custom_payload"]
        elif config.get("include_trigger_data", True):
            payload = trigger_data
        else:
            payload = {}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.request(method, url, json=payload, headers=headers)

        success = 200 <= resp.status_code < 300

        return {
            "success": success,
            "message": f"Webhook {method} {url} -> {resp.status_code}",
            "details": {
                "status_code": resp.status_code,
                "response_body": resp.text[:500],
            },
        }

    except Exception as e:
        logger.error("webhook_fire_error", error=str(e))
        return {"success": False, "message": str(e), "details": {}}


# ---------------------------------------------------------------------------
# Action: update_stage
# ---------------------------------------------------------------------------

@register_action("update_stage")
async def handle_update_stage(config: dict, trigger_data: dict) -> dict:
    """
    Update a company's pipeline stage in the database.

    Config keys:
        stage (str, required): New pipeline stage value
        company_id (str, optional): Override — defaults to trigger_data["company_id"]
    """
    try:
        stage = config.get("stage")
        if not stage:
            return {"success": False, "message": "stage is required", "details": {}}

        company_id = config.get("company_id") or trigger_data.get("company_id")
        if not company_id:
            return {"success": False, "message": "No company_id available", "details": {}}

        db = get_service_client()
        db.table("companies").update({
            "pipeline_stage": stage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", company_id).execute()

        return {
            "success": True,
            "message": f"Company {company_id} moved to stage '{stage}'",
            "details": {"company_id": company_id, "new_stage": stage},
        }

    except Exception as e:
        logger.error("update_stage_error", error=str(e))
        return {"success": False, "message": str(e), "details": {}}


# ---------------------------------------------------------------------------
# Action: send_notification
# ---------------------------------------------------------------------------

@register_action("send_notification")
async def handle_send_notification(config: dict, trigger_data: dict) -> dict:
    """
    Log a notification. Placeholder for future Slack/email integration.

    Config keys:
        channel (str, optional): 'log' | 'slack' | 'email' — default 'log'
        message (str, required): Notification text
        level (str, optional): 'info' | 'warning' | 'error' — default 'info'
    """
    try:
        message = config.get("message", "Automation notification")
        channel = config.get("channel", "log")
        level = config.get("level", "info")

        # Substitute basic placeholders from trigger data
        for key, value in trigger_data.items():
            if isinstance(value, str):
                message = message.replace(f"{{{{{key}}}}}", value)

        if channel == "log":
            log_fn = getattr(logger, level, logger.info)
            log_fn(
                "automation_notification",
                message=message,
                trigger_data_keys=list(trigger_data.keys()),
            )

        # Future: Slack webhook, email, etc.
        # elif channel == "slack":
        #     await _send_slack_notification(config, message)
        # elif channel == "email":
        #     await _send_email_notification(config, message)

        return {
            "success": True,
            "message": f"Notification sent via {channel}: {message[:100]}",
            "details": {"channel": channel, "level": level},
        }

    except Exception as e:
        logger.error("send_notification_error", error=str(e))
        return {"success": False, "message": str(e), "details": {}}


# ---------------------------------------------------------------------------
# Action: enrich_company
# ---------------------------------------------------------------------------

@register_action("enrich_company")
async def handle_enrich_company(config: dict, trigger_data: dict) -> dict:
    """
    Trigger contact enrichment for a company.

    Config keys:
        company_id (str, optional): Override — defaults to trigger_data["company_id"]
        max_contacts (int, optional): Max contacts to find — default 5
    """
    try:
        company_id = config.get("company_id") or trigger_data.get("company_id")
        if not company_id:
            return {"success": False, "message": "No company_id available", "details": {}}

        max_contacts = config.get("max_contacts", 5)

        # Fetch company record
        db = get_service_client()
        result = db.table("companies").select("*").eq("id", company_id).maybe_single().execute()
        if not result.data:
            return {"success": False, "message": f"Company {company_id} not found", "details": {}}

        company = result.data

        try:
            from app.engine_b.enrichment import enrich_company_contacts
        except ImportError:
            return {
                "success": False,
                "message": "Enrichment module (app.engine_b.enrichment) is not available. "
                           "Ensure the enrichment package is installed and configured.",
                "details": {"company_id": company_id},
            }

        enrichment_result = await enrich_company_contacts(
            company=company,
            max_contacts=max_contacts,
        )

        return {
            "success": True,
            "message": f"Enrichment complete: {enrichment_result.get('contacts_saved', 0)} contacts found",
            "details": enrichment_result,
        }

    except Exception as e:
        logger.error("enrich_company_error", error=str(e))
        return {"success": False, "message": str(e), "details": {}}


# ---------------------------------------------------------------------------
# Action: score_company
# ---------------------------------------------------------------------------

@register_action("score_company")
async def handle_score_company(config: dict, trigger_data: dict) -> dict:
    """
    Trigger scoring for a company.

    Config keys:
        company_id (str, optional): Override — defaults to trigger_data["company_id"]
    """
    try:
        company_id = config.get("company_id") or trigger_data.get("company_id")
        if not company_id:
            return {"success": False, "message": "No company_id available", "details": {}}

        # Fetch company record
        db = get_service_client()
        result = db.table("companies").select("*").eq("id", company_id).maybe_single().execute()
        if not result.data:
            return {"success": False, "message": f"Company {company_id} not found", "details": {}}

        company = result.data

        try:
            from app.engine_a.scoring import score_and_persist
        except ImportError:
            return {
                "success": False,
                "message": "Scoring module (app.engine_a.scoring) is not available. "
                           "Ensure the scoring package is installed and configured.",
                "details": {"company_id": company_id},
            }

        score_result = await score_and_persist(company)

        return {
            "success": True,
            "message": f"Scored {company_id}: {score_result.get('total_opportunity_score', 0)} ({score_result.get('priority_bucket', 'unknown')})",
            "details": {
                "total_score": score_result.get("total_opportunity_score"),
                "priority_bucket": score_result.get("priority_bucket"),
            },
        }

    except Exception as e:
        logger.error("score_company_error", error=str(e))
        return {"success": False, "message": str(e), "details": {}}
