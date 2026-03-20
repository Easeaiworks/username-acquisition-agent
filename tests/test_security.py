"""
Tests for security middleware — auth, rate limiting, security headers, input validation.
"""

import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Auth Middleware Tests
# ---------------------------------------------------------------------------

class TestAuthMiddleware:
    def test_constant_time_compare_equal(self):
        from app.middleware.auth import _constant_time_compare
        assert _constant_time_compare("abc123", "abc123") is True

    def test_constant_time_compare_not_equal(self):
        from app.middleware.auth import _constant_time_compare
        assert _constant_time_compare("abc123", "xyz789") is False

    def test_constant_time_compare_empty(self):
        from app.middleware.auth import _constant_time_compare
        assert _constant_time_compare("", "") is True
        assert _constant_time_compare("a", "") is False

    def test_public_paths_defined(self):
        from app.middleware.auth import PUBLIC_PATHS
        assert "/health" in PUBLIC_PATHS
        assert "/docs" in PUBLIC_PATHS
        assert "/openapi.json" in PUBLIC_PATHS

    def test_public_prefixes_defined(self):
        from app.middleware.auth import PUBLIC_PREFIXES
        assert any("/assets/" in p for p in PUBLIC_PREFIXES)


# ---------------------------------------------------------------------------
# Rate Limit Middleware Tests
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:
    def test_strict_paths_defined(self):
        from app.middleware.rate_limit import STRICT_PATHS
        assert "/api/outreach/auto-run" in STRICT_PATHS
        assert "/api/reports/generate" in STRICT_PATHS
        assert "/api/scoring/run" in STRICT_PATHS

    def test_rate_limiter_initialization(self):
        from app.middleware.rate_limit import RateLimitMiddleware
        mock_app = MagicMock()
        limiter = RateLimitMiddleware(mock_app, general_limit=100, mutation_limit=30, strict_limit=10, window=60)
        assert limiter.general_limit == 100
        assert limiter.mutation_limit == 30
        assert limiter.strict_limit == 10
        assert limiter.window == 60

    def test_clean_window_removes_old(self):
        from app.middleware.rate_limit import RateLimitMiddleware
        mock_app = MagicMock()
        limiter = RateLimitMiddleware(mock_app)
        now = time.time()
        limiter._requests["test"] = [now - 120, now - 90, now - 10, now - 5]
        limiter._clean_window("test", now)
        # Only entries within the 60s window should remain
        assert len(limiter._requests["test"]) == 2

    def test_get_limit_general(self):
        from app.middleware.rate_limit import RateLimitMiddleware
        mock_app = MagicMock()
        limiter = RateLimitMiddleware(mock_app, general_limit=60, mutation_limit=20, strict_limit=5)

        mock_request = MagicMock()
        mock_request.url.path = "/api/dashboard/overview"
        mock_request.method = "GET"

        assert limiter._get_limit(mock_request) == 60

    def test_get_limit_mutation(self):
        from app.middleware.rate_limit import RateLimitMiddleware
        mock_app = MagicMock()
        limiter = RateLimitMiddleware(mock_app, general_limit=60, mutation_limit=20, strict_limit=5)

        mock_request = MagicMock()
        mock_request.url.path = "/api/companies/"
        mock_request.method = "POST"

        assert limiter._get_limit(mock_request) == 20

    def test_get_limit_strict(self):
        from app.middleware.rate_limit import RateLimitMiddleware
        mock_app = MagicMock()
        limiter = RateLimitMiddleware(mock_app, general_limit=60, mutation_limit=20, strict_limit=5)

        mock_request = MagicMock()
        mock_request.url.path = "/api/outreach/auto-run"
        mock_request.method = "POST"

        assert limiter._get_limit(mock_request) == 5

    def test_get_client_key_direct(self):
        from app.middleware.rate_limit import RateLimitMiddleware
        mock_app = MagicMock()
        limiter = RateLimitMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "192.168.1.1"

        assert limiter._get_client_key(mock_request) == "192.168.1.1"

    def test_get_client_key_forwarded(self):
        from app.middleware.rate_limit import RateLimitMiddleware
        mock_app = MagicMock()
        limiter = RateLimitMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2"}

        assert limiter._get_client_key(mock_request) == "10.0.0.1"


# ---------------------------------------------------------------------------
# Security Headers Tests
# ---------------------------------------------------------------------------

class TestSecurityHeaders:
    @pytest.mark.asyncio
    async def test_security_headers_added(self):
        from app.middleware.security_headers import SecurityHeadersMiddleware

        mock_app = MagicMock()
        middleware = SecurityHeadersMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/test"

        mock_response = MagicMock()
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "strict-origin" in response.headers["Referrer-Policy"]
        assert "camera=()" in response.headers["Permissions-Policy"]
        assert "31536000" in response.headers["Strict-Transport-Security"]

    @pytest.mark.asyncio
    async def test_csp_added_for_api_paths(self):
        from app.middleware.security_headers import SecurityHeadersMiddleware

        mock_app = MagicMock()
        middleware = SecurityHeadersMiddleware(mock_app)

        mock_request = MagicMock()
        mock_request.url.path = "/api/companies"

        mock_response = MagicMock()
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        response = await middleware.dispatch(mock_request, mock_call_next)
        assert "default-src 'none'" in response.headers["Content-Security-Policy"]


# ---------------------------------------------------------------------------
# Input Validation Tests
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_sort_field_whitelist(self):
        from app.api.companies import ALLOWED_SORT_FIELDS
        assert "brand_name" in ALLOWED_SORT_FIELDS
        assert "composite_score" in ALLOWED_SORT_FIELDS
        assert "created_at" in ALLOWED_SORT_FIELDS
        # Dangerous field names should not be in whitelist
        assert "password" not in ALLOWED_SORT_FIELDS
        assert "'; DROP TABLE" not in ALLOWED_SORT_FIELDS

    def test_max_csv_size_defined(self):
        from app.api.companies import MAX_CSV_BYTES
        assert MAX_CSV_BYTES == 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Config Security Tests
# ---------------------------------------------------------------------------

class TestConfigSecurity:
    def test_require_auth_defaults_false(self):
        """Auth should default to off for development safety."""
        # In test env, it's set to false by conftest
        from app.config import settings
        assert settings.require_auth is False

    def test_is_production_flag(self):
        from app.config import settings
        # In test, APP_ENV=test
        assert settings.is_production is False

    def test_dashboard_api_key_configurable(self):
        from app.config import settings
        # In test, set by conftest
        assert settings.dashboard_api_key == "test-dashboard-key"
