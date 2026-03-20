"""
Application configuration loaded from environment variables.
All secrets live in Railway env vars or local .env file — never in code.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Central configuration for the entire application."""

    # --- Environment ---
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Supabase ---
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_anon_key: str = Field(..., alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(..., alias="SUPABASE_SERVICE_ROLE_KEY")

    # --- Claude API ---
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")

    # --- YouTube Data API v3 ---
    youtube_api_key: Optional[str] = Field(default=None, alias="YOUTUBE_API_KEY")

    # --- Twitch Helix API ---
    twitch_client_id: Optional[str] = Field(default=None, alias="TWITCH_CLIENT_ID")
    twitch_client_secret: Optional[str] = Field(default=None, alias="TWITCH_CLIENT_SECRET")

    # --- Apify ---
    apify_api_token: Optional[str] = Field(default=None, alias="APIFY_API_TOKEN")

    # --- RocketReach ---
    rocketreach_api_key: Optional[str] = Field(default=None, alias="ROCKETREACH_API_KEY")

    # --- Hunter.io ---
    hunter_api_key: Optional[str] = Field(default=None, alias="HUNTER_API_KEY")

    # --- Email Sending ---
    instantly_api_key: Optional[str] = Field(default=None, alias="INSTANTLY_API_KEY")
    smartlead_api_key: Optional[str] = Field(default=None, alias="SMARTLEAD_API_KEY")

    # --- Calendly ---
    calendly_api_key: Optional[str] = Field(default=None, alias="CALENDLY_API_KEY")
    calendly_event_url: Optional[str] = Field(default=None, alias="CALENDLY_EVENT_URL")

    # --- Autonomy Thresholds ---
    auto_outreach_threshold: float = Field(default=0.65, alias="AUTO_OUTREACH_THRESHOLD")
    approval_queue_threshold: float = Field(default=0.50, alias="APPROVAL_QUEUE_THRESHOLD")
    daily_scan_hour: int = Field(default=6, alias="DAILY_SCAN_HOUR")
    daily_scan_minute: int = Field(default=0, alias="DAILY_SCAN_MINUTE")

    # --- Rate Limits ---
    max_youtube_calls_per_day: int = Field(default=9000, alias="MAX_YOUTUBE_CALLS_PER_DAY")
    max_twitch_calls_per_minute: int = Field(default=25, alias="MAX_TWITCH_CALLS_PER_MINUTE")
    max_apify_concurrent_runs: int = Field(default=3, alias="MAX_APIFY_CONCURRENT_RUNS")
    max_rocketreach_calls_per_month: int = Field(default=3000, alias="MAX_ROCKETREACH_CALLS_PER_MONTH")
    max_hunter_calls_per_month: int = Field(default=2500, alias="MAX_HUNTER_CALLS_PER_MONTH")

    # --- Compliance ---
    max_touches_per_contact: int = Field(default=4, alias="MAX_TOUCHES_PER_CONTACT")
    outreach_cooldown_days: int = Field(default=30, alias="OUTREACH_COOLDOWN_DAYS")
    sender_email: Optional[str] = Field(default=None, alias="SENDER_EMAIL")
    sender_name: str = Field(default="Sean", alias="SENDER_NAME")
    physical_address: Optional[str] = Field(default=None, alias="PHYSICAL_ADDRESS")

    # --- Scoring Weights ---
    weight_brand_value: float = 0.35
    weight_handle_pain: float = 0.30
    weight_urgency: float = 0.20
    weight_reachability: float = 0.15

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


# Singleton instance
settings = Settings()
