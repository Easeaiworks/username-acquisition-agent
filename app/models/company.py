"""Company model — the core entity in the pipeline."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class PipelineStage(str, Enum):
    DISCOVERED = "discovered"
    SCANNED = "scanned"
    SCORED = "scored"
    ENRICHING = "enriching"
    QUALIFIED = "qualified"
    OUTREACH = "outreach"
    MEETING = "meeting"
    CLOSED = "closed"


class PriorityBucket(str, Enum):
    CRITICAL = "critical"         # > 0.8
    VERY_HIGH = "very_high"       # 0.65 - 0.8
    HIGH = "high"                 # 0.5 - 0.65
    MEDIUM = "medium"             # 0.35 - 0.5
    LOW = "low"                   # < 0.35


class CompanyBase(BaseModel):
    """Shared fields for company creation and display."""
    brand_name: str
    legal_name: Optional[str] = None
    aliases: Optional[list[str]] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    vertical: Optional[str] = None
    employee_range: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    founding_year: Optional[int] = None
    is_public: bool = False
    consumer_facing_score: float = 0.0
    source: Optional[str] = None
    notes: Optional[str] = None


class CompanyCreate(CompanyBase):
    """Fields required to create a new company record."""
    pass


class CompanyUpdate(BaseModel):
    """Fields that can be updated on an existing company."""
    brand_name: Optional[str] = None
    legal_name: Optional[str] = None
    aliases: Optional[list[str]] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    vertical: Optional[str] = None
    employee_range: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    founding_year: Optional[int] = None
    is_public: Optional[bool] = None
    consumer_facing_score: Optional[float] = None

    # Scoring (set by scoring engine)
    brand_value_score: Optional[float] = None
    handle_pain_score: Optional[float] = None
    urgency_score: Optional[float] = None
    reachability_score: Optional[float] = None
    total_opportunity_score: Optional[float] = None
    priority_bucket: Optional[PriorityBucket] = None

    # Signals
    urgency_signals: Optional[dict] = None
    enrichment_data: Optional[dict] = None

    # Pipeline state
    pipeline_stage: Optional[PipelineStage] = None
    approved_for_outreach: Optional[bool] = None

    # Metadata
    source: Optional[str] = None
    notes: Optional[str] = None
    scanned_at: Optional[datetime] = None
    scored_at: Optional[datetime] = None


class Company(CompanyBase):
    """Full company record as stored in the database."""
    id: str
    brand_value_score: float = 0.0
    handle_pain_score: float = 0.0
    urgency_score: float = 0.0
    reachability_score: float = 0.0
    total_opportunity_score: float = 0.0
    priority_bucket: Optional[PriorityBucket] = None

    urgency_signals: dict = Field(default_factory=dict)
    enrichment_data: dict = Field(default_factory=dict)

    pipeline_stage: PipelineStage = PipelineStage.DISCOVERED
    approved_for_outreach: bool = False

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    scanned_at: Optional[datetime] = None
    scored_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    """Paginated list of companies."""
    data: list[Company]
    count: int
    page: int
    page_size: int
