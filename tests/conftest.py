"""Test configuration — sets up environment variables before any imports."""

import os

# Set required env vars BEFORE any app imports happen
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("REQUIRE_AUTH", "false")
os.environ.setdefault("DASHBOARD_API_KEY", "test-dashboard-key")
