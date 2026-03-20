"""Contact model — decision makers at target companies."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class SeniorityLevel(str, Enum):
    C_SUITE = "c_suite"
    VP = "vp"
    DIRECTOR = "director"
    MANAGER = "manager"
    INDIVIDUAL = "individual"


class Department(str, Enum):
    MARKETING = "marketing"
    BRAND = "brand"
    SOCIAL = "social"
    DIGITAL = "digital"
    EXECUTIVE = "executive"
    OTHER = "other"


class ContactCreate(BaseModel):
    """Fields to create a contact after enrichment."""
    company_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    title: Optional[str] = None
    seniority_level: Optional[SeniorityLevel] = None
    department: Optional[Department] = None

    email: Optional[str] = None
    email_confidence: Optional[float] = None
    email_source: Optional[str] = None
    email_type: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None

    rocketreach_id: Optional[str] = None
    hunter_result: Optional[dict] = None
    enrichment_data: Optional[dict] = None

    outreach_priority: int = 0
    do_not_contact: bool = False
    suppressed_reason: Optional[str] = None


class Contact(ContactCreate):
    """Full contact record from the database."""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
