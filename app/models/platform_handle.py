"""Platform handle model — tracks social media handles per company per platform."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class Platform(str, Enum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    TWITCH = "twitch"
    YOUTUBE = "youtube"


class MismatchType(str, Enum):
    NONE = "none"                    # exact match, no opportunity
    MODIFIER = "modifier"            # has hq, official, inc, etc.
    DIFFERENT = "different"          # completely different handle
    INACTIVE_HOLDER = "inactive_holder"  # exact handle exists but dormant
    UNAVAILABLE = "unavailable"      # handle taken by unrelated active account
    NOT_PRESENT = "not_present"      # company has no presence on this platform


class PlatformHandleCreate(BaseModel):
    """Fields to create a handle record after scanning."""
    company_id: str
    platform: Platform
    observed_handle: Optional[str] = None
    observed_display_name: Optional[str] = None

    # Analysis
    normalized_candidates: Optional[list[str]] = None
    exact_match: bool = False
    mismatch_type: MismatchType = MismatchType.NONE
    mismatch_severity: float = 0.0
    handle_available: Optional[bool] = None
    current_holder_info: Optional[dict] = None

    # Account activity (dormant holder detection)
    account_exists: Optional[bool] = None
    last_post_date: Optional[datetime] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    account_dormant: bool = False
    dormancy_months: Optional[int] = None
    account_created_at: Optional[datetime] = None

    # Confidence
    confidence: float = 0.0
    data_source: Optional[str] = None
    raw_response: Optional[dict] = None


class PlatformHandle(PlatformHandleCreate):
    """Full handle record from the database."""
    id: str
    checked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
