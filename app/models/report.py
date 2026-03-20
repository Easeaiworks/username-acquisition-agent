"""Daily report model — pipeline metrics and activity summary."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime


class DailyReport(BaseModel):
    """Daily pipeline activity report."""
    id: Optional[str] = None
    report_date: date

    # Scanner metrics
    companies_scanned: int = 0
    new_companies_discovered: int = 0
    opportunities_found: int = 0
    critical_opportunities: int = 0

    # Enrichment metrics
    contacts_enriched: int = 0
    emails_verified: int = 0

    # Outreach metrics
    emails_sent: int = 0
    linkedin_messages_sent: int = 0
    calls_attempted: int = 0

    # Response metrics
    replies_received: int = 0
    positive_replies: int = 0
    meetings_booked: int = 0

    # Pipeline snapshot
    pipeline_snapshot: dict = Field(default_factory=dict)
    top_opportunities: list = Field(default_factory=list)

    generated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
