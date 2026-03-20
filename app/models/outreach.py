"""Outreach sequence model — tracks multi-step, multi-channel outreach."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class OutreachStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"


class ResponseSentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    OBJECTION = "objection"


class OutreachChannel(str, Enum):
    EMAIL = "email"
    LINKEDIN = "linkedin"
    PHONE = "phone"
    SMS = "sms"


class OutreachCreate(BaseModel):
    """Fields to create an outreach sequence step."""
    contact_id: str
    company_id: str
    channel: OutreachChannel
    sequence_step: int = 1
    max_steps: int = 4

    subject: Optional[str] = None
    message_body: Optional[str] = None
    message_variant: Optional[str] = None
    personalization_data: Optional[dict] = None

    scheduled_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None


class OutreachSequence(OutreachCreate):
    """Full outreach record from the database."""
    id: str
    status: OutreachStatus = OutreachStatus.DRAFT
    sent_at: Optional[datetime] = None

    response_text: Optional[str] = None
    response_sentiment: Optional[ResponseSentiment] = None
    response_classified_at: Optional[datetime] = None

    meeting_booked: bool = False
    meeting_datetime: Optional[datetime] = None
    meeting_link: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
