"""
Admin Panel API — RBAC-protected endpoints for user management,
integrations, file uploads, and email templates.

Prefix: /api/admin

NOTE: This module assumes the following DB migration has been applied
on top of migration 005_admin_panel.sql:

    ALTER TABLE file_uploads ADD COLUMN IF NOT EXISTS file_content TEXT;

This column stores base64-encoded file content since we bypass
Supabase Storage for simplicity.
"""

import base64
import csv
import io
import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from app.config import settings
from app.database import get_service_client
from app.integrations.credentials import invalidate_cache as invalidate_credential_cache

import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/api/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {
    "csv", "xlsx", "xls", "json", "html", "txt", "pdf",
    "png", "jpg", "jpeg", "gif", "svg",
}

MIME_TYPE_MAP = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "json": "application/json",
    "html": "text/html",
    "txt": "text/plain",
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "svg": "image/svg+xml",
}

MAX_UPLOAD_BYTES = settings.max_upload_size_mb * 1024 * 1024


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

# --- Users ---

class UserCreate(BaseModel):
    email: str
    name: str = ""
    role: str = Field(default="viewer", pattern=r"^(super_admin|admin|viewer)$")
    password: Optional[str] = None  # If provided, enables email+password login


class UserUpdate(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = Field(default=None, pattern=r"^(super_admin|admin|viewer)$")
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    api_key_preview: Optional[str] = None
    last_login_at: Optional[str] = None
    created_at: str
    updated_at: str


# --- Integrations ---

class IntegrationCreate(BaseModel):
    service_name: str
    service_category: str = "custom"
    display_name: str
    api_key_encrypted: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None


class IntegrationUpdate(BaseModel):
    api_key_encrypted: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None
    display_name: Optional[str] = None


class IntegrationResponse(BaseModel):
    id: str
    service_name: str
    service_category: str
    display_name: str
    api_key_masked: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None
    is_connected: bool
    last_tested_at: Optional[str] = None
    test_result: Optional[str] = None
    created_at: str
    updated_at: str


# --- File Uploads ---

class UploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    category: str
    description: Optional[str] = None
    row_count: Optional[int] = None
    column_headers: Optional[List[str]] = None
    processing_status: str
    processing_error: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: str
    updated_at: str


# --- Email Templates ---

class TemplateCreate(BaseModel):
    name: str
    subject_template: str = ""
    body_template: str = ""
    template_type: str = Field(default="outreach", pattern=r"^(outreach|follow_up|meeting_request|custom)$")
    sequence_step: int = Field(default=1, ge=1, le=10)
    merge_tags: Optional[List[str]] = None
    is_active: bool = True
    is_default: bool = False


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    template_type: Optional[str] = Field(default=None, pattern=r"^(outreach|follow_up|meeting_request|custom)$")
    sequence_step: Optional[int] = Field(default=None, ge=1, le=10)
    merge_tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class TemplatePreviewRequest(BaseModel):
    subject_template: str = ""
    body_template: str = ""
    merge_data: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def require_role(request: Request, *allowed_roles: str):
    """Raise 403 if the authenticated user's role is not in allowed_roles."""
    role = getattr(request.state, "user_role", None)
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _mask_key(key: Optional[str]) -> Optional[str]:
    """Mask an API key, showing only the last 4 characters."""
    if not key:
        return None
    if len(key) <= 4:
        return "****"
    return "*" * (len(key) - 4) + key[-4:]


def _get_file_extension(filename: str) -> str:
    """Extract and lowercase file extension from a filename."""
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _detect_file_type(extension: str) -> str:
    """Map a file extension to a logical file_type category."""
    if extension in ("csv", "xlsx", "xls"):
        return "email_list"
    if extension in ("json",):
        return "document"
    if extension in ("html", "txt", "pdf"):
        return "document"
    if extension in ("png", "jpg", "jpeg", "gif", "svg"):
        return "image"
    return "other"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_csv_content(content: bytes) -> tuple[int, List[str], List[List[str]]]:
    """Parse CSV bytes and return (row_count, headers, all_rows)."""
    text = content.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return 0, [], []
    headers = rows[0]
    data_rows = rows[1:]
    return len(data_rows), headers, data_rows


def _render_template(template_str: str, merge_data: Dict[str, str]) -> str:
    """Replace {{tag}} placeholders with values from merge_data."""
    result = template_str
    for tag, value in merge_data.items():
        # Support both "first_name" and "{{first_name}}" as keys
        clean_tag = tag.strip("{} ")
        result = result.replace("{{" + clean_tag + "}}", value)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# 1. USER MANAGEMENT (super_admin only)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/users")
async def list_users(request: Request):
    """List all admin users. Requires super_admin role."""
    require_role(request, "super_admin")
    db = get_service_client()

    result = db.table("admin_users").select("*").order("created_at", desc=True).execute()

    users = []
    for u in (result.data or []):
        users.append({
            "id": u["id"],
            "email": u["email"],
            "name": u.get("name", ""),
            "role": u["role"],
            "is_active": u["is_active"],
            "api_key_preview": _mask_key(u.get("api_key")),
            "last_login_at": u.get("last_login_at"),
            "created_at": u["created_at"],
            "updated_at": u["updated_at"],
        })

    return {"users": users, "count": len(users)}


@router.post("/users", status_code=201)
async def create_user(request: Request, body: UserCreate):
    """Create a new admin user with a generated API key. Requires super_admin."""
    require_role(request, "super_admin")
    db = get_service_client()

    # Check for duplicate email
    existing = db.table("admin_users").select("id").eq("email", body.email).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    api_key = secrets.token_urlsafe(32)
    now = _now_iso()

    new_user = {
        "email": body.email.lower().strip(),
        "name": body.name,
        "role": body.role,
        "api_key": api_key,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }

    # Hash password if provided (enables email+password login)
    if body.password:
        from app.api.auth import hash_password
        new_user["password_hash"] = hash_password(body.password)

    result = db.table("admin_users").insert(new_user).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create user")

    created = result.data[0]
    logger.info("admin_user_created", email=body.email, role=body.role)

    return {
        "id": created["id"],
        "email": created["email"],
        "name": created.get("name", ""),
        "role": created["role"],
        "api_key": api_key,  # Show full key only on creation
        "is_active": created["is_active"],
        "created_at": created["created_at"],
        "updated_at": created["updated_at"],
    }


@router.put("/users/{user_id}")
async def update_user(request: Request, user_id: str, body: UserUpdate):
    """Update an admin user's profile. Requires super_admin."""
    require_role(request, "super_admin")
    db = get_service_client()

    # Verify user exists
    existing = db.table("admin_users").select("id").eq("id", user_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="User not found")

    updates: Dict[str, Any] = {"updated_at": _now_iso()}
    if body.email is not None:
        updates["email"] = body.email
    if body.name is not None:
        updates["name"] = body.name
    if body.role is not None:
        updates["role"] = body.role
    if body.is_active is not None:
        updates["is_active"] = body.is_active

    result = db.table("admin_users").update(updates).eq("id", user_id).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update user")

    logger.info("admin_user_updated", user_id=user_id, fields=list(updates.keys()))
    return result.data[0]


@router.delete("/users/{user_id}")
async def delete_user(request: Request, user_id: str):
    """Soft-delete an admin user (set is_active=false). Requires super_admin."""
    require_role(request, "super_admin")
    db = get_service_client()

    existing = db.table("admin_users").select("id").eq("id", user_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="User not found")

    db.table("admin_users").update({
        "is_active": False,
        "updated_at": _now_iso(),
    }).eq("id", user_id).execute()

    logger.info("admin_user_deactivated", user_id=user_id)
    return {"status": "deactivated", "user_id": user_id}


@router.post("/users/{user_id}/regenerate-key")
async def regenerate_user_key(request: Request, user_id: str):
    """Regenerate API key for an admin user. Requires super_admin."""
    require_role(request, "super_admin")
    db = get_service_client()

    existing = db.table("admin_users").select("id").eq("id", user_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="User not found")

    new_key = secrets.token_urlsafe(32)
    db.table("admin_users").update({
        "api_key": new_key,
        "updated_at": _now_iso(),
    }).eq("id", user_id).execute()

    logger.info("admin_user_key_regenerated", user_id=user_id)
    return {"user_id": user_id, "api_key": new_key}


# ═══════════════════════════════════════════════════════════════════════════
# 2. API INTEGRATIONS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/integrations")
async def list_integrations(request: Request):
    """List all API integrations with masked keys. Admin or super_admin."""
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    result = (
        db.table("api_integrations")
        .select("*")
        .order("service_category")
        .order("display_name")
        .execute()
    )

    integrations = []
    for i in (result.data or []):
        integrations.append({
            "id": i["id"],
            "service_name": i["service_name"],
            "service_category": i["service_category"],
            "display_name": i["display_name"],
            "api_key_masked": _mask_key(i.get("api_key_encrypted")),
            "extra_config": i.get("extra_config"),
            "is_connected": i["is_connected"],
            "last_tested_at": i.get("last_tested_at"),
            "test_result": i.get("test_result"),
            "created_at": i["created_at"],
            "updated_at": i["updated_at"],
        })

    return {"integrations": integrations, "count": len(integrations)}


@router.post("/integrations", status_code=201)
async def create_integration(request: Request, body: IntegrationCreate):
    """Add a custom API integration. Requires super_admin."""
    require_role(request, "super_admin")
    db = get_service_client()

    # Check for duplicate service_name
    existing = (
        db.table("api_integrations")
        .select("id")
        .eq("service_name", body.service_name)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="An integration with this service_name already exists")

    now = _now_iso()
    user_id = getattr(request.state, "user_id", None)

    new_integration = {
        "service_name": body.service_name,
        "service_category": body.service_category,
        "display_name": body.display_name,
        "api_key_encrypted": body.api_key_encrypted,
        "extra_config": body.extra_config or {},
        "is_connected": bool(body.api_key_encrypted),
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }

    result = db.table("api_integrations").insert(new_integration).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create integration")

    created = result.data[0]
    logger.info("integration_created", service_name=body.service_name)

    return {
        "id": created["id"],
        "service_name": created["service_name"],
        "service_category": created["service_category"],
        "display_name": created["display_name"],
        "is_connected": created["is_connected"],
        "created_at": created["created_at"],
    }


@router.put("/integrations/{integration_id}")
async def update_integration(request: Request, integration_id: str, body: IntegrationUpdate):
    """Update an integration's key / config. Requires super_admin for keys."""
    # Any key change requires super_admin; display_name can be admin
    if body.api_key_encrypted is not None:
        require_role(request, "super_admin")
    else:
        require_role(request, "super_admin", "admin")

    db = get_service_client()

    existing = db.table("api_integrations").select("id").eq("id", integration_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Integration not found")

    updates: Dict[str, Any] = {"updated_at": _now_iso()}

    if body.api_key_encrypted is not None:
        updates["api_key_encrypted"] = body.api_key_encrypted
        updates["is_connected"] = True
    if body.extra_config is not None:
        updates["extra_config"] = body.extra_config
    if body.display_name is not None:
        updates["display_name"] = body.display_name

    result = db.table("api_integrations").update(updates).eq("id", integration_id).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update integration")

    # Clear credential cache so the new key takes effect immediately
    service_name = result.data[0].get("service_name")
    invalidate_credential_cache(service_name)

    logger.info("integration_updated", integration_id=integration_id, service=service_name)
    return result.data[0]


@router.post("/integrations/{integration_id}/test")
async def test_integration(request: Request, integration_id: str):
    """Test an integration connection. Marks as tested. Admin or super_admin."""
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    existing = db.table("api_integrations").select("*").eq("id", integration_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration = existing.data[0]
    now = _now_iso()

    # For now, just mark as tested — actual connection testing can be added per service
    has_key = bool(integration.get("api_key_encrypted"))
    test_result = "ok" if has_key else "no_key_configured"

    db.table("api_integrations").update({
        "last_tested_at": now,
        "test_result": test_result,
        "updated_at": now,
    }).eq("id", integration_id).execute()

    logger.info(
        "integration_tested",
        integration_id=integration_id,
        service=integration["service_name"],
        result=test_result,
    )

    return {
        "integration_id": integration_id,
        "service_name": integration["service_name"],
        "test_result": test_result,
        "tested_at": now,
    }


@router.delete("/integrations/{integration_id}/disconnect")
async def disconnect_integration(request: Request, integration_id: str):
    """Disconnect an integration — clear key, set is_connected=false. Requires super_admin."""
    require_role(request, "super_admin")
    db = get_service_client()

    existing = db.table("api_integrations").select("id").eq("id", integration_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Integration not found")

    # Get service_name before clearing
    svc = db.table("api_integrations").select("service_name").eq("id", integration_id).execute()
    service_name = svc.data[0]["service_name"] if svc.data else None

    db.table("api_integrations").update({
        "api_key_encrypted": None,
        "is_connected": False,
        "test_result": None,
        "last_tested_at": None,
        "updated_at": _now_iso(),
    }).eq("id", integration_id).execute()

    # Clear credential cache so the backend stops using the old key
    invalidate_credential_cache(service_name)

    logger.info("integration_disconnected", integration_id=integration_id, service=service_name)
    return {"status": "disconnected", "integration_id": integration_id}


# ═══════════════════════════════════════════════════════════════════════════
# 3. FILE UPLOADS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/uploads")
async def list_uploads(
    request: Request,
    category: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List all file uploads with optional category filter. Admin or super_admin."""
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    offset = (page - 1) * page_size

    query = db.table("file_uploads").select(
        "id, filename, file_type, mime_type, file_size_bytes, category, "
        "description, row_count, column_headers, processing_status, "
        "processing_error, uploaded_by, created_at, updated_at",
        count="exact",
    )

    if category:
        query = query.eq("category", category)

    result = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()

    return {
        "uploads": result.data or [],
        "count": result.count or 0,
        "page": page,
        "page_size": page_size,
    }


@router.post("/uploads", status_code=201)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form(default="general"),
    description: str = Form(default=""),
):
    """
    Upload a file. CSV/Excel files are parsed for headers and row count.
    File content is stored as base64 in the file_content column.
    Admin or super_admin.
    """
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    filename = file.filename or "unknown"
    extension = _get_file_extension(filename)

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '.{extension}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File size ({file_size} bytes) exceeds maximum ({MAX_UPLOAD_BYTES} bytes / {settings.max_upload_size_mb} MB)",
        )

    # Encode content as base64 for storage
    content_b64 = base64.b64encode(content).decode("ascii")

    file_type = _detect_file_type(extension)
    mime_type = MIME_TYPE_MAP.get(extension, "application/octet-stream")
    user_id = getattr(request.state, "user_id", None)
    now = _now_iso()

    row_count = None
    column_headers = None
    processing_status = "ready"
    processing_error = None

    # Parse CSV for metadata
    if extension == "csv":
        try:
            parsed_rows, headers, _ = _parse_csv_content(content)
            row_count = parsed_rows
            column_headers = headers
        except Exception as e:
            processing_status = "error"
            processing_error = f"CSV parse error: {str(e)}"
            logger.warning("csv_parse_error", filename=filename, error=str(e))

    # Parse Excel for metadata (requires pandas)
    elif extension in ("xlsx", "xls"):
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(content), nrows=None)
            row_count = len(df)
            column_headers = list(df.columns.astype(str))
        except Exception as e:
            processing_status = "error"
            processing_error = f"Excel parse error: {str(e)}"
            logger.warning("excel_parse_error", filename=filename, error=str(e))

    storage_path = f"uploads/{now.replace(':', '-')}_{filename}"

    record = {
        "filename": filename,
        "storage_path": storage_path,
        "file_type": file_type,
        "mime_type": mime_type,
        "file_size_bytes": file_size,
        "category": category,
        "description": description,
        "row_count": row_count,
        "column_headers": column_headers,
        "processing_status": processing_status,
        "processing_error": processing_error,
        "uploaded_by": user_id,
        "file_content": content_b64,
        "created_at": now,
        "updated_at": now,
    }

    result = db.table("file_uploads").insert(record).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to save upload record")

    created = result.data[0]
    logger.info(
        "file_uploaded",
        filename=filename,
        size=file_size,
        extension=extension,
        rows=row_count,
    )

    return {
        "id": created["id"],
        "filename": created["filename"],
        "file_type": created["file_type"],
        "mime_type": created.get("mime_type"),
        "file_size_bytes": created.get("file_size_bytes"),
        "category": created["category"],
        "row_count": created.get("row_count"),
        "column_headers": created.get("column_headers"),
        "processing_status": created["processing_status"],
        "processing_error": created.get("processing_error"),
        "created_at": created["created_at"],
    }


@router.get("/uploads/{upload_id}")
async def get_upload(request: Request, upload_id: str):
    """Get details for a single upload. Admin or super_admin."""
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    result = (
        db.table("file_uploads")
        .select(
            "id, filename, storage_path, file_type, mime_type, file_size_bytes, "
            "category, description, row_count, column_headers, processing_status, "
            "processing_error, uploaded_by, created_at, updated_at"
        )
        .eq("id", upload_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Upload not found")

    return result.data[0]


@router.delete("/uploads/{upload_id}")
async def delete_upload(request: Request, upload_id: str):
    """Delete an upload record. Admin or super_admin."""
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    existing = db.table("file_uploads").select("id").eq("id", upload_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Upload not found")

    db.table("file_uploads").delete().eq("id", upload_id).execute()

    logger.info("file_deleted", upload_id=upload_id)
    return {"status": "deleted", "upload_id": upload_id}


@router.get("/uploads/{upload_id}/preview")
async def preview_upload(request: Request, upload_id: str):
    """
    Preview the first 10 rows of a CSV or Excel upload.
    Returns headers and row data. Admin or super_admin.
    """
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    result = (
        db.table("file_uploads")
        .select("id, filename, file_type, mime_type, column_headers, file_content")
        .eq("id", upload_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Upload not found")

    upload = result.data[0]
    extension = _get_file_extension(upload["filename"])

    if extension not in ("csv", "xlsx", "xls"):
        raise HTTPException(
            status_code=400,
            detail="Preview is only available for CSV and Excel files",
        )

    file_content_b64 = upload.get("file_content")
    if not file_content_b64:
        raise HTTPException(status_code=404, detail="File content not available for preview")

    content = base64.b64decode(file_content_b64)

    if extension == "csv":
        try:
            _, headers, data_rows = _parse_csv_content(content)
            preview_rows = data_rows[:10]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse CSV: {str(e)}")
    else:
        # Excel
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(content), nrows=10)
            headers = list(df.columns.astype(str))
            preview_rows = df.fillna("").astype(str).values.tolist()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse Excel: {str(e)}")

    return {
        "upload_id": upload_id,
        "filename": upload["filename"],
        "headers": headers,
        "rows": preview_rows,
        "preview_row_count": len(preview_rows),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 4. EMAIL TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/templates")
async def list_templates(
    request: Request,
    template_type: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
):
    """List all email templates. Admin or super_admin."""
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    query = db.table("email_templates").select("*")

    if template_type:
        query = query.eq("template_type", template_type)
    if is_active is not None:
        query = query.eq("is_active", is_active)

    result = query.order("sequence_step").order("created_at", desc=True).execute()

    return {"templates": result.data or [], "count": len(result.data or [])}


@router.post("/templates", status_code=201)
async def create_template(request: Request, body: TemplateCreate):
    """Create a new email template. Admin or super_admin."""
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    user_id = getattr(request.state, "user_id", None)
    now = _now_iso()

    record = {
        "name": body.name,
        "subject_template": body.subject_template,
        "body_template": body.body_template,
        "template_type": body.template_type,
        "sequence_step": body.sequence_step,
        "merge_tags": body.merge_tags or [],
        "is_active": body.is_active,
        "is_default": body.is_default,
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }

    result = db.table("email_templates").insert(record).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create template")

    logger.info("template_created", name=body.name, type=body.template_type)
    return result.data[0]


@router.put("/templates/{template_id}")
async def update_template(request: Request, template_id: str, body: TemplateUpdate):
    """Update an email template. Admin or super_admin."""
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    existing = db.table("email_templates").select("id").eq("id", template_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Template not found")

    updates: Dict[str, Any] = {"updated_at": _now_iso()}

    if body.name is not None:
        updates["name"] = body.name
    if body.subject_template is not None:
        updates["subject_template"] = body.subject_template
    if body.body_template is not None:
        updates["body_template"] = body.body_template
    if body.template_type is not None:
        updates["template_type"] = body.template_type
    if body.sequence_step is not None:
        updates["sequence_step"] = body.sequence_step
    if body.merge_tags is not None:
        updates["merge_tags"] = body.merge_tags
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if body.is_default is not None:
        updates["is_default"] = body.is_default

    result = db.table("email_templates").update(updates).eq("id", template_id).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update template")

    logger.info("template_updated", template_id=template_id)
    return result.data[0]


@router.delete("/templates/{template_id}")
async def delete_template(request: Request, template_id: str):
    """Delete an email template. Admin or super_admin."""
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    existing = db.table("email_templates").select("id").eq("id", template_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Template not found")

    db.table("email_templates").delete().eq("id", template_id).execute()

    logger.info("template_deleted", template_id=template_id)
    return {"status": "deleted", "template_id": template_id}


@router.post("/templates/{template_id}/duplicate", status_code=201)
async def duplicate_template(request: Request, template_id: str):
    """Duplicate an email template. Admin or super_admin."""
    require_role(request, "super_admin", "admin")
    db = get_service_client()

    existing = db.table("email_templates").select("*").eq("id", template_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Template not found")

    original = existing.data[0]
    user_id = getattr(request.state, "user_id", None)
    now = _now_iso()

    duplicate = {
        "name": f"{original['name']} (Copy)",
        "subject_template": original["subject_template"],
        "body_template": original["body_template"],
        "template_type": original["template_type"],
        "sequence_step": original["sequence_step"],
        "merge_tags": original.get("merge_tags", []),
        "is_active": False,  # Duplicates start inactive
        "is_default": False,  # Never duplicate as default
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
    }

    result = db.table("email_templates").insert(duplicate).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to duplicate template")

    logger.info("template_duplicated", original_id=template_id, new_id=result.data[0]["id"])
    return result.data[0]


@router.post("/templates/preview")
async def preview_template(request: Request, body: TemplatePreviewRequest):
    """
    Preview a template with sample merge data.
    Replaces {{tag}} placeholders with provided values.
    Admin or super_admin.
    """
    require_role(request, "super_admin", "admin")

    rendered_subject = _render_template(body.subject_template, body.merge_data)
    rendered_body = _render_template(body.body_template, body.merge_data)

    # Find any remaining unresolved tags
    unresolved_subject = re.findall(r"\{\{(\w+)\}\}", rendered_subject)
    unresolved_body = re.findall(r"\{\{(\w+)\}\}", rendered_body)
    unresolved = list(set(unresolved_subject + unresolved_body))

    return {
        "subject": rendered_subject,
        "body": rendered_body,
        "unresolved_tags": unresolved,
    }
