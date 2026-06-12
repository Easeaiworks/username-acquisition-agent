"""
Authentication API — email + password login for the admin dashboard.

Prefix: /api/auth

Endpoints:
  POST /api/auth/login   — authenticate with email + password, returns API key
  POST /api/auth/logout   — (client-side only, included for completeness)
"""

import bcrypt
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_service_client

import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    api_key: str
    user_id: str
    email: str
    name: str
    role: str


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """
    Authenticate with email + password.

    Returns the user's API key (used for all subsequent requests via
    X-API-Key header) plus user profile info.
    """
    db = get_service_client()

    # Look up user by email
    result = (
        db.table("admin_users")
        .select("id, email, name, role, is_active, api_key, password_hash")
        .eq("email", body.email.lower().strip())
        .execute()
    )

    if not result.data:
        logger.warning("login_failed_unknown_email", email=body.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = result.data[0]

    # Check account is active
    if not user.get("is_active", False):
        logger.warning("login_failed_inactive", user_id=user["id"])
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Check password
    password_hash = user.get("password_hash")
    if not password_hash:
        logger.warning("login_failed_no_password", user_id=user["id"])
        raise HTTPException(
            status_code=401,
            detail="Password not set for this account. Contact your administrator.",
        )

    if not verify_password(body.password, password_hash):
        logger.warning("login_failed_wrong_password", user_id=user["id"])
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Ensure user has an API key (generate one if missing)
    api_key = user.get("api_key")
    if not api_key:
        api_key = secrets.token_urlsafe(32)
        db.table("admin_users").update({
            "api_key": api_key,
        }).eq("id", user["id"]).execute()

    # Update last login
    try:
        db.table("admin_users").update({
            "last_login_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", user["id"]).execute()
    except Exception:
        pass  # Non-critical

    logger.info("login_success", user_id=user["id"], email=user["email"], role=user["role"])

    return LoginResponse(
        api_key=api_key,
        user_id=user["id"],
        email=user["email"],
        name=user.get("name", ""),
        role=user["role"],
    )
