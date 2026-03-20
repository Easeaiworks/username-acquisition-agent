"""Tests for the handle scanner orchestrator."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.engine_a.handle_scanner import (
    scan_company_handles,
    _scan_single_platform,
    _summarize_holder,
    scan_batch,
)
from app.models.platform_handle import Platform, MismatchType


@pytest.fixture
def mock_available_result():
    """A platform check result where the handle is available."""
    return {
        "handle": "testbrand",
        "available": True,
        "user_data": None,
        "platform": "twitch",
    }


@pytest.fixture
def mock_taken_result():
    """A platform check result where the handle is taken by an active user."""
    return {
        "handle": "testbrand",
        "available": False,
        "user_data": {
            "display_name": "TestBrand Gaming",
            "description": "We stream games",
            "follower_count": 50000,
            "post_count": 500,
            "last_post_date": "2026-03-01T12:00:00+00:00",
            "account_dormant": False,
        },
        "platform": "twitch",
    }


@pytest.fixture
def mock_dormant_result():
    """A platform check result where the handle is held by a dormant account."""
    return {
        "handle": "testbrand",
        "available": False,
        "user_data": {
            "display_name": "Old User",
            "description": "inactive",
            "follower_count": 15,
            "post_count": 2,
            "last_post_date": "2023-01-15T00:00:00+00:00",
            "account_dormant": True,
        },
        "platform": "twitch",
    }


class TestSummarizeHolder:
    def test_basic_summary(self):
        holder = {
            "display_name": "Test User",
            "description": "A test user bio that is somewhat long",
            "follower_count": 1000,
            "post_count": 50,
            "last_post_date": "2026-01-01T00:00:00Z",
            "account_dormant": False,
            "is_verified": True,
        }
        summary = _summarize_holder(holder)
        assert summary["display_name"] == "Test User"
        assert summary["follower_count"] == 1000
        assert summary["is_verified"] is True
        assert summary["account_dormant"] is False

    def test_summary_truncates_description(self):
        holder = {
            "display_name": "Test",
            "description": "x" * 500,
            "follower_count": 0,
            "post_count": 0,
            "last_post_date": None,
            "account_dormant": False,
            "is_verified": False,
        }
        summary = _summarize_holder(holder)
        assert len(summary["description"]) <= 200

    def test_summary_missing_fields(self):
        holder = {"display_name": "Test"}
        summary = _summarize_holder(holder)
        assert summary["display_name"] == "Test"
        assert summary["follower_count"] is None
        assert summary["account_dormant"] is False


class TestScanSinglePlatform:
    @pytest.mark.asyncio
    async def test_available_handle(self, mock_available_result):
        with patch(
            "app.engine_a.handle_scanner.PLATFORM_CHECKERS",
            {Platform.TWITCH: AsyncMock(return_value=mock_available_result)},
        ):
            result = await _scan_single_platform("testbrand", Platform.TWITCH)

            assert result["handle_available"] is True
            assert result["platform"] == "twitch"
            assert result["ideal_handle"] == "testbrand"

    @pytest.mark.asyncio
    async def test_taken_active_handle(self, mock_taken_result):
        with patch(
            "app.engine_a.handle_scanner.PLATFORM_CHECKERS",
            {Platform.TWITCH: AsyncMock(return_value=mock_taken_result)},
        ):
            result = await _scan_single_platform("testbrand", Platform.TWITCH)

            assert result["handle_available"] is False
            assert result["holder_summary"] is not None
            assert result["holder_summary"]["follower_count"] == 50000

    @pytest.mark.asyncio
    async def test_dormant_handle_detected(self, mock_dormant_result):
        with patch(
            "app.engine_a.handle_scanner.PLATFORM_CHECKERS",
            {Platform.TWITCH: AsyncMock(return_value=mock_dormant_result)},
        ):
            result = await _scan_single_platform("testbrand", Platform.TWITCH)

            assert result["handle_available"] is False
            assert result["account_dormant"] is True
            assert result["holder_summary"]["account_dormant"] is True


class TestScanCompanyHandles:
    @pytest.mark.asyncio
    async def test_scan_returns_all_platforms(self):
        mock_result = {
            "handle": "testbrand",
            "available": True,
            "user_data": None,
            "platform": "mock",
        }

        with patch(
            "app.engine_a.handle_scanner.PLATFORM_CHECKERS",
            {
                Platform.YOUTUBE: AsyncMock(return_value=mock_result),
                Platform.TWITCH: AsyncMock(return_value=mock_result),
                Platform.INSTAGRAM: AsyncMock(return_value=mock_result),
                Platform.TIKTOK: AsyncMock(return_value=mock_result),
            },
        ), patch(
            "app.engine_a.handle_scanner._save_scan_results",
            new_callable=AsyncMock,
        ), patch(
            "app.engine_a.handle_scanner._update_company_stage",
            new_callable=AsyncMock,
        ):
            result = await scan_company_handles(
                company_id="test-id",
                brand_name="Test Brand",
            )

            assert result["company_id"] == "test-id"
            assert result["brand_slug"] == "testbrand"
            assert len(result["platforms"]) == 4
            assert "youtube" in result["platforms"]
            assert "twitch" in result["platforms"]
            assert "instagram" in result["platforms"]
            assert "tiktok" in result["platforms"]

    @pytest.mark.asyncio
    async def test_scan_handles_platform_errors_gracefully(self):
        mock_ok = {
            "handle": "testbrand",
            "available": True,
            "user_data": None,
            "platform": "mock",
        }

        with patch(
            "app.engine_a.handle_scanner.PLATFORM_CHECKERS",
            {
                Platform.YOUTUBE: AsyncMock(return_value=mock_ok),
                Platform.TWITCH: AsyncMock(side_effect=Exception("API down")),
                Platform.INSTAGRAM: AsyncMock(return_value=mock_ok),
                Platform.TIKTOK: AsyncMock(return_value=mock_ok),
            },
        ), patch(
            "app.engine_a.handle_scanner._save_scan_results",
            new_callable=AsyncMock,
        ), patch(
            "app.engine_a.handle_scanner._update_company_stage",
            new_callable=AsyncMock,
        ):
            result = await scan_company_handles(
                company_id="test-id",
                brand_name="Test Brand",
            )

            # Should still have all 4 platforms, but Twitch has error
            assert len(result["platforms"]) == 4
            assert "error" in result["platforms"]["twitch"]
            assert "error" not in result["platforms"]["youtube"]

    @pytest.mark.asyncio
    async def test_scan_specific_platforms_only(self):
        mock_result = {
            "handle": "testbrand",
            "available": True,
            "user_data": None,
            "platform": "mock",
        }

        with patch(
            "app.engine_a.handle_scanner.PLATFORM_CHECKERS",
            {
                Platform.YOUTUBE: AsyncMock(return_value=mock_result),
                Platform.TWITCH: AsyncMock(return_value=mock_result),
            },
        ), patch(
            "app.engine_a.handle_scanner._save_scan_results",
            new_callable=AsyncMock,
        ), patch(
            "app.engine_a.handle_scanner._update_company_stage",
            new_callable=AsyncMock,
        ):
            result = await scan_company_handles(
                company_id="test-id",
                brand_name="Test Brand",
                platforms=[Platform.YOUTUBE, Platform.TWITCH],
            )

            assert len(result["platforms"]) == 2
            assert "youtube" in result["platforms"]
            assert "twitch" in result["platforms"]


class TestScanBatch:
    @pytest.mark.asyncio
    async def test_batch_scan_multiple_companies(self):
        mock_result = {
            "handle": "test",
            "available": True,
            "user_data": None,
            "platform": "mock",
        }

        with patch(
            "app.engine_a.handle_scanner.PLATFORM_CHECKERS",
            {
                Platform.YOUTUBE: AsyncMock(return_value=mock_result),
                Platform.TWITCH: AsyncMock(return_value=mock_result),
                Platform.INSTAGRAM: AsyncMock(return_value=mock_result),
                Platform.TIKTOK: AsyncMock(return_value=mock_result),
            },
        ), patch(
            "app.engine_a.handle_scanner._save_scan_results",
            new_callable=AsyncMock,
        ), patch(
            "app.engine_a.handle_scanner._update_company_stage",
            new_callable=AsyncMock,
        ):
            companies = [
                {"id": "1", "brand_name": "Alpha Corp"},
                {"id": "2", "brand_name": "Beta Inc"},
                {"id": "3", "brand_name": "Gamma LLC"},
            ]

            results = await scan_batch(companies, concurrency=2)

            assert len(results) == 3
            assert all("company_id" in r for r in results)
