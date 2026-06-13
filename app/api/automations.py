"""
Automation workflow API routes — CRUD, manual triggers, execution history.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_service_client
from app.automations.engine import run_workflow_manually
from app.automations.actions import list_action_types, get_action_handler

import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/automations", tags=["Automations"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    trigger_type: str = Field(..., min_length=1)
    trigger_config: dict[str, Any] = Field(default_factory=dict)
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    is_enabled: bool = True


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict[str, Any]] = None
    conditions: Optional[list[dict[str, Any]]] = None
    actions: Optional[list[dict[str, Any]]] = None
    is_enabled: Optional[bool] = None


# ---------------------------------------------------------------------------
# Trigger-type catalogue
# ---------------------------------------------------------------------------

TRIGGER_TYPES = [
    {
        "type": "lead_scored",
        "label": "Lead Scored",
        "description": "Fires when a company receives a new score",
        "config_fields": [],
    },
    {
        "type": "company_approved",
        "label": "Company Approved",
        "description": "Fires when a company is approved in the pipeline",
        "config_fields": [],
    },
    {
        "type": "score_threshold",
        "label": "Score Threshold",
        "description": "Fires when a company score crosses a threshold",
        "config_fields": [
            {"name": "min_score", "type": "number", "label": "Minimum Score"},
        ],
    },
    {
        "type": "stage_changed",
        "label": "Stage Changed",
        "description": "Fires when a company moves pipeline stages",
        "config_fields": [
            {"name": "from_stage", "type": "text", "label": "From Stage"},
            {"name": "to_stage", "type": "text", "label": "To Stage"},
        ],
    },
    {
        "type": "outreach_sent",
        "label": "Outreach Sent",
        "description": "Fires when outreach email is sent",
        "config_fields": [],
    },
    {
        "type": "company_added",
        "label": "Company Added",
        "description": "Fires when a new company enters the pipeline",
        "config_fields": [],
    },
    {
        "type": "contact_enriched",
        "label": "Contact Enriched",
        "description": "Fires when contact info is found for a company",
        "config_fields": [],
    },
    {
        "type": "manual",
        "label": "Manual",
        "description": "Only runs when manually triggered",
        "config_fields": [],
    },
    {
        "type": "schedule",
        "label": "Scheduled",
        "description": "Runs on a schedule",
        "config_fields": [
            {"name": "cron", "type": "text", "label": "Cron Expression"},
        ],
    },
]


# ---------------------------------------------------------------------------
# Action-type catalogue (built dynamically from the action registry)
# ---------------------------------------------------------------------------

# Static metadata for each registered action — label, description, config fields
ACTION_TYPE_META: dict[str, dict[str, Any]] = {
    "email_add_contact": {
        "label": "Add Email Contact",
        "description": "Add a contact to the email_contacts table and optionally to a list",
        "config_fields": [
            {"name": "email", "type": "text", "label": "Email (optional, falls back to trigger data)"},
            {"name": "first_name", "type": "text", "label": "First Name"},
            {"name": "last_name", "type": "text", "label": "Last Name"},
            {"name": "company", "type": "text", "label": "Company"},
            {"name": "tags", "type": "array", "label": "Tags"},
            {"name": "list_id", "type": "text", "label": "List ID (optional)"},
        ],
    },
    "email_add_tags": {
        "label": "Add Tags to Contact",
        "description": "Add tags to an existing email contact",
        "config_fields": [
            {"name": "email", "type": "text", "label": "Email (optional)"},
            {"name": "tags", "type": "array", "label": "Tags", "required": True},
        ],
    },
    "email_send": {
        "label": "Send Email",
        "description": "Send a one-off email to a contact",
        "config_fields": [
            {"name": "to_email", "type": "text", "label": "Recipient Email (optional)"},
            {"name": "subject", "type": "text", "label": "Subject", "required": True},
            {"name": "html_content", "type": "textarea", "label": "HTML Content", "required": True},
            {"name": "from_name", "type": "text", "label": "From Name"},
            {"name": "from_email", "type": "text", "label": "From Email"},
        ],
    },
    "email_enroll_sequence": {
        "label": "Enroll in Email Sequence",
        "description": "Enroll a contact into a drip email sequence",
        "config_fields": [
            {"name": "email", "type": "text", "label": "Email (optional)"},
            {"name": "sequence_id", "type": "text", "label": "Sequence ID", "required": True},
        ],
    },
    "email_remove_contact": {
        "label": "Remove / Unsubscribe Contact",
        "description": "Remove a contact from a list or unsubscribe globally",
        "config_fields": [
            {"name": "email", "type": "text", "label": "Email (optional)"},
            {"name": "list_id", "type": "text", "label": "List ID (remove from specific list)"},
            {"name": "unsubscribe", "type": "boolean", "label": "Unsubscribe Globally"},
        ],
    },
    "email_update_contact": {
        "label": "Update Contact",
        "description": "Update fields on an existing email contact",
        "config_fields": [
            {"name": "email", "type": "text", "label": "Email (optional)"},
            {"name": "fields", "type": "object", "label": "Fields to Update", "required": True},
        ],
    },
    "webhook_fire": {
        "label": "Fire Webhook",
        "description": "Send an HTTP request to an external URL with trigger data",
        "config_fields": [
            {"name": "url", "type": "text", "label": "Target URL", "required": True},
            {"name": "method", "type": "text", "label": "HTTP Method (default POST)"},
            {"name": "headers", "type": "object", "label": "Extra Headers"},
            {"name": "include_trigger_data", "type": "boolean", "label": "Include Trigger Data (default true)"},
            {"name": "custom_payload", "type": "object", "label": "Custom Payload (overrides trigger data)"},
        ],
    },
    "update_stage": {
        "label": "Update Pipeline Stage",
        "description": "Move a company to a different pipeline stage",
        "config_fields": [
            {"name": "stage", "type": "text", "label": "New Stage", "required": True},
            {"name": "company_id", "type": "text", "label": "Company ID (optional)"},
        ],
    },
    "send_notification": {
        "label": "Send Notification",
        "description": "Log a notification (Slack/email integration placeholder)",
        "config_fields": [
            {"name": "message", "type": "text", "label": "Message", "required": True},
            {"name": "channel", "type": "text", "label": "Channel (log, slack, email)"},
            {"name": "level", "type": "text", "label": "Level (info, warning, error)"},
        ],
    },
    "enrich_company": {
        "label": "Enrich Company",
        "description": "Trigger contact enrichment for a company",
        "config_fields": [
            {"name": "company_id", "type": "text", "label": "Company ID (optional)"},
            {"name": "max_contacts", "type": "number", "label": "Max Contacts (default 5)"},
        ],
    },
    "score_company": {
        "label": "Score Company",
        "description": "Trigger scoring for a company",
        "config_fields": [
            {"name": "company_id", "type": "text", "label": "Company ID (optional)"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------

@router.get("/workflows")
async def list_workflows():
    """List all workflows with last run status."""
    db = get_service_client()

    try:
        result = (
            db.table("workflows")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as e:
        logger.error("list_workflows_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch workflows")

    workflows = result.data or []

    # Attach the most recent run status for each workflow
    for wf in workflows:
        try:
            run_result = (
                db.table("workflow_runs")
                .select("id, status, started_at, completed_at, duration_ms, error_message")
                .eq("workflow_id", wf["id"])
                .order("started_at", desc=True)
                .limit(1)
                .execute()
            )
            wf["last_run"] = run_result.data[0] if run_result.data else None
        except Exception:
            wf["last_run"] = None

    return {"data": workflows}


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get workflow details."""
    db = get_service_client()

    try:
        result = (
            db.table("workflows")
            .select("*")
            .eq("id", workflow_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        logger.error("get_workflow_failed", workflow_id=workflow_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch workflow")

    if not result.data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = result.data

    # Attach recent runs
    try:
        runs_result = (
            db.table("workflow_runs")
            .select("id, status, started_at, completed_at, duration_ms, error_message")
            .eq("workflow_id", workflow_id)
            .order("started_at", desc=True)
            .limit(5)
            .execute()
        )
        workflow["recent_runs"] = runs_result.data or []
    except Exception:
        workflow["recent_runs"] = []

    return workflow


@router.post("/workflows")
async def create_workflow(body: WorkflowCreate):
    """Create a new automation workflow."""
    db = get_service_client()

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "name": body.name,
        "description": body.description,
        "trigger_type": body.trigger_type,
        "trigger_config": body.trigger_config,
        "conditions": body.conditions,
        "actions": body.actions,
        "is_enabled": body.is_enabled,
        "created_at": now,
        "updated_at": now,
        "trigger_count": 0,
    }

    try:
        result = db.table("workflows").insert(record).execute()
    except Exception as e:
        logger.error("create_workflow_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create workflow")

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create workflow")

    logger.info("workflow_created", workflow_id=result.data[0]["id"], name=body.name)
    return result.data[0]


@router.put("/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, body: WorkflowUpdate):
    """Update an existing workflow."""
    db = get_service_client()

    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        result = (
            db.table("workflows")
            .update(data)
            .eq("id", workflow_id)
            .execute()
        )
    except Exception as e:
        logger.error("update_workflow_failed", workflow_id=workflow_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update workflow")

    if not result.data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    logger.info("workflow_updated", workflow_id=workflow_id)
    return result.data[0]


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete a workflow and its run history (cascade)."""
    db = get_service_client()

    try:
        result = (
            db.table("workflows")
            .delete()
            .eq("id", workflow_id)
            .execute()
        )
    except Exception as e:
        logger.error("delete_workflow_failed", workflow_id=workflow_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete workflow")

    if not result.data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    logger.info("workflow_deleted", workflow_id=workflow_id)
    return {"status": "deleted", "workflow_id": workflow_id}


@router.post("/workflows/{workflow_id}/toggle")
async def toggle_workflow(workflow_id: str):
    """Enable or disable a workflow."""
    db = get_service_client()

    # Fetch current state
    try:
        current = (
            db.table("workflows")
            .select("id, is_enabled")
            .eq("id", workflow_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        logger.error("toggle_workflow_query_failed", workflow_id=workflow_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch workflow")

    if not current.data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    new_state = not current.data["is_enabled"]

    try:
        result = (
            db.table("workflows")
            .update({
                "is_enabled": new_state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", workflow_id)
            .execute()
        )
    except Exception as e:
        logger.error("toggle_workflow_update_failed", workflow_id=workflow_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to toggle workflow")

    logger.info("workflow_toggled", workflow_id=workflow_id, is_enabled=new_state)
    return {"workflow_id": workflow_id, "is_enabled": new_state}


# ---------------------------------------------------------------------------
# Manual run
# ---------------------------------------------------------------------------

@router.post("/workflows/{workflow_id}/run")
async def trigger_workflow_run(workflow_id: str):
    """Manually trigger a workflow execution."""
    try:
        run_id = await run_workflow_manually(workflow_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("manual_run_failed", workflow_id=workflow_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to run workflow")

    return {"workflow_id": workflow_id, "run_id": run_id, "status": "started"}


# ---------------------------------------------------------------------------
# Execution history
# ---------------------------------------------------------------------------

@router.get("/workflows/{workflow_id}/runs")
async def list_workflow_runs(
    workflow_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    """List execution history for a workflow with pagination."""
    db = get_service_client()
    offset = (page - 1) * page_size

    # Verify workflow exists
    try:
        wf = (
            db.table("workflows")
            .select("id")
            .eq("id", workflow_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        logger.error("list_runs_wf_check_failed", workflow_id=workflow_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to verify workflow")

    if not wf.data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        result = (
            db.table("workflow_runs")
            .select("*", count="exact")
            .eq("workflow_id", workflow_id)
            .order("started_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
    except Exception as e:
        logger.error("list_runs_failed", workflow_id=workflow_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch runs")

    return {
        "data": result.data or [],
        "count": result.count or 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get details of a single workflow run."""
    db = get_service_client()

    try:
        result = (
            db.table("workflow_runs")
            .select("*")
            .eq("id", run_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        logger.error("get_run_failed", run_id=run_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch run")

    if not result.data:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    return result.data


# ---------------------------------------------------------------------------
# Catalogue endpoints
# ---------------------------------------------------------------------------

@router.get("/trigger-types")
async def get_trigger_types():
    """Return available trigger types with descriptions and config schemas."""
    return {"data": TRIGGER_TYPES}


@router.get("/action-types")
async def get_action_types():
    """Return available action types with descriptions and config schemas."""
    registered = list_action_types()

    result = []
    for action_type in registered:
        meta = ACTION_TYPE_META.get(action_type, {})
        result.append({
            "type": action_type,
            "label": meta.get("label", action_type.replace("_", " ").title()),
            "description": meta.get("description", ""),
            "config_fields": meta.get("config_fields", []),
        })

    return {"data": result}
