"""
Workflow execution engine — evaluates conditions and runs action sequences.

When a trigger fires (via app.automations.triggers.fire_trigger), this module:
1. Queries the workflows table for enabled workflows matching the trigger type
2. Evaluates each workflow's conditions against the trigger data
3. For matching workflows, creates a workflow_run record and executes actions sequentially
4. Updates the run record with results, timing, and status
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import structlog

from app.database import get_service_client
from app.automations.actions import get_action_handler

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------

def _resolve_field(data: dict, field: str) -> Any:
    """
    Resolve a dotted field path from a nested dict.

    Examples:
        _resolve_field({"score": 0.8}, "score") -> 0.8
        _resolve_field({"company": {"name": "Acme"}}, "company.name") -> "Acme"
    """
    parts = field.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


async def evaluate_conditions(conditions: list[dict], data: dict) -> bool:
    """
    Evaluate a list of conditions against trigger data. All must pass (AND logic).

    Each condition is a dict:
        {"field": "score", "op": "gte", "value": 0.8}

    Supported operators:
        eq, neq, gt, gte, lt, lte,
        contains, not_contains,
        in, not_in,
        exists, not_exists
    """
    if not conditions:
        return True

    for condition in conditions:
        field = condition.get("field", "")
        op = condition.get("op", "eq")
        expected = condition.get("value")
        actual = _resolve_field(data, field)

        try:
            if op == "eq":
                if actual != expected:
                    return False
            elif op == "neq":
                if actual == expected:
                    return False
            elif op == "gt":
                if actual is None or actual <= expected:
                    return False
            elif op == "gte":
                if actual is None or actual < expected:
                    return False
            elif op == "lt":
                if actual is None or actual >= expected:
                    return False
            elif op == "lte":
                if actual is None or actual > expected:
                    return False
            elif op == "contains":
                if actual is None or expected not in actual:
                    return False
            elif op == "not_contains":
                if actual is not None and expected in actual:
                    return False
            elif op == "in":
                if actual not in (expected or []):
                    return False
            elif op == "not_in":
                if actual in (expected or []):
                    return False
            elif op == "exists":
                if actual is None:
                    return False
            elif op == "not_exists":
                if actual is not None:
                    return False
            else:
                logger.warning("unknown_condition_operator", op=op)
                return False
        except (TypeError, ValueError) as e:
            logger.warning(
                "condition_eval_error",
                field=field,
                op=op,
                error=str(e),
            )
            return False

    return True


# ---------------------------------------------------------------------------
# Workflow execution
# ---------------------------------------------------------------------------

async def execute_workflow(workflow: dict, trigger_data: dict) -> str:
    """
    Execute a single workflow: create run record, iterate actions, persist results.

    Args:
        workflow: Row from the workflows table
        trigger_data: Dict of event data passed from the trigger

    Returns:
        The workflow_run ID (UUID string)
    """
    db = get_service_client()
    workflow_id = workflow["id"]
    actions = workflow.get("actions") or []

    start_ts = time.monotonic()
    started_at = datetime.now(timezone.utc)

    # Create the run record
    run_record = {
        "workflow_id": workflow_id,
        "trigger_event": workflow.get("trigger_type", "unknown"),
        "trigger_data": trigger_data,
        "status": "running",
        "actions_executed": [],
        "started_at": started_at.isoformat(),
    }

    try:
        insert_result = db.table("workflow_runs").insert(run_record).execute()
        run_id = insert_result.data[0]["id"]
    except Exception as e:
        logger.error("workflow_run_create_failed", workflow_id=workflow_id, error=str(e))
        raise

    logger.info(
        "workflow_execution_started",
        workflow_id=workflow_id,
        run_id=run_id,
        action_count=len(actions),
    )

    # Execute actions sequentially
    actions_log: list[dict] = []
    overall_status = "completed"
    error_message = None

    for i, action_def in enumerate(actions):
        action_type = action_def.get("type", "")
        action_config = action_def.get("config", {})

        handler = get_action_handler(action_type)
        if handler is None:
            action_result = {
                "success": False,
                "message": f"Unknown action type: {action_type}",
                "details": {},
            }
            logger.warning("unknown_action_type", action_type=action_type, workflow_id=workflow_id)
        else:
            try:
                action_result = await handler(action_config, trigger_data)
            except Exception as e:
                action_result = {
                    "success": False,
                    "message": f"Action error: {str(e)}",
                    "details": {},
                }
                logger.error(
                    "action_execution_error",
                    action_type=action_type,
                    workflow_id=workflow_id,
                    error=str(e),
                )

        actions_log.append({
            "step": i + 1,
            "type": action_type,
            "result": action_result,
        })

        if not action_result.get("success"):
            overall_status = "failed"
            error_message = action_result.get("message", "Action failed")
            # Continue executing remaining actions even if one fails
            # (the status will still be 'failed' to indicate partial failure)

    # Calculate duration
    elapsed_ms = int((time.monotonic() - start_ts) * 1000)

    # Update the run record
    try:
        db.table("workflow_runs").update({
            "status": overall_status,
            "actions_executed": actions_log,
            "error_message": error_message,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": elapsed_ms,
        }).eq("id", run_id).execute()
    except Exception as e:
        logger.error("workflow_run_update_failed", run_id=run_id, error=str(e))

    # Update the workflow's trigger stats
    try:
        db.table("workflows").update({
            "last_triggered_at": datetime.now(timezone.utc).isoformat(),
            "trigger_count": workflow.get("trigger_count", 0) + 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", workflow_id).execute()
    except Exception as e:
        logger.error("workflow_stats_update_failed", workflow_id=workflow_id, error=str(e))

    logger.info(
        "workflow_execution_complete",
        workflow_id=workflow_id,
        run_id=run_id,
        status=overall_status,
        duration_ms=elapsed_ms,
        actions_total=len(actions),
        actions_succeeded=sum(1 for a in actions_log if a["result"].get("success")),
    )

    return run_id


# ---------------------------------------------------------------------------
# Trigger matching
# ---------------------------------------------------------------------------

async def execute_matching_workflows(event_type: str, trigger_data: dict) -> list[str]:
    """
    Find all enabled workflows matching a trigger type, evaluate conditions,
    and execute those that match.

    Args:
        event_type: The trigger event type (e.g. 'lead_scored', 'stage_changed')
        trigger_data: Dict of event data

    Returns:
        List of workflow_run IDs for executed workflows
    """
    db = get_service_client()

    try:
        result = (
            db.table("workflows")
            .select("*")
            .eq("trigger_type", event_type)
            .eq("is_enabled", True)
            .execute()
        )
        workflows = result.data or []
    except Exception as e:
        logger.error("workflow_query_failed", event_type=event_type, error=str(e))
        return []

    if not workflows:
        logger.debug("no_matching_workflows", event_type=event_type)
        return []

    logger.info(
        "workflows_matched",
        event_type=event_type,
        candidate_count=len(workflows),
    )

    run_ids: list[str] = []

    for workflow in workflows:
        workflow_id = workflow["id"]
        conditions = workflow.get("conditions") or []

        # Evaluate conditions
        try:
            conditions_met = await evaluate_conditions(conditions, trigger_data)
        except Exception as e:
            logger.error(
                "condition_eval_failed",
                workflow_id=workflow_id,
                error=str(e),
            )
            continue

        if not conditions_met:
            logger.debug(
                "workflow_conditions_not_met",
                workflow_id=workflow_id,
                event_type=event_type,
            )
            continue

        # Execute the workflow
        try:
            run_id = await execute_workflow(workflow, trigger_data)
            run_ids.append(run_id)
        except Exception as e:
            logger.error(
                "workflow_execution_failed",
                workflow_id=workflow_id,
                error=str(e),
            )

    return run_ids


# ---------------------------------------------------------------------------
# Manual trigger
# ---------------------------------------------------------------------------

async def run_workflow_manually(workflow_id: str) -> str:
    """
    Execute a workflow manually (for manual triggers or testing from the UI).

    Args:
        workflow_id: UUID of the workflow to run

    Returns:
        The workflow_run ID

    Raises:
        ValueError: If workflow not found or not enabled
    """
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
        logger.error("manual_run_query_failed", workflow_id=workflow_id, error=str(e))
        raise

    if not result.data:
        raise ValueError(f"Workflow {workflow_id} not found")

    workflow = result.data

    if not workflow.get("is_enabled", True):
        raise ValueError(f"Workflow {workflow_id} is disabled")

    # For manual triggers, the trigger data comes from trigger_config
    trigger_data = dict(workflow.get("trigger_config") or {})
    trigger_data["_manual"] = True
    trigger_data["_triggered_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("manual_workflow_trigger", workflow_id=workflow_id)

    return await execute_workflow(workflow, trigger_data)
