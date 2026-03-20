"""Tests for the Engine A pipeline orchestration."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.engine_a.pipeline import run_tier1_scan, get_pipeline_stats


class TestRunTier1Scan:
    @pytest.mark.asyncio
    async def test_no_companies_to_scan(self):
        with patch(
            "app.engine_a.pipeline.get_companies_for_scanning",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await run_tier1_scan()

            assert result["status"] == "completed"
            assert result["companies_scanned"] == 0
            assert result["companies_available"] == 0

    @pytest.mark.asyncio
    async def test_scans_available_companies(self):
        companies = [
            {"id": "1", "brand_name": "Alpha"},
            {"id": "2", "brand_name": "Beta"},
        ]

        scan_results = [
            {"company_id": "1", "brand_slug": "alpha", "platforms": {}, "cross_platform_severity": 0.6},
            {"company_id": "2", "brand_slug": "beta", "platforms": {}, "cross_platform_severity": 0.3},
        ]

        with patch(
            "app.engine_a.pipeline.get_companies_for_scanning",
            new_callable=AsyncMock,
            return_value=companies,
        ), patch(
            "app.engine_a.pipeline.scan_batch",
            new_callable=AsyncMock,
            return_value=scan_results,
        ), patch(
            "app.engine_a.pipeline._record_pipeline_run",
            new_callable=AsyncMock,
        ):
            result = await run_tier1_scan()

            assert result["status"] == "completed"
            assert result["companies_scanned"] == 2
            assert result["companies_available"] == 2
            assert result["high_value_opportunities"] == 1  # Only alpha >= 0.5

    @pytest.mark.asyncio
    async def test_handles_scan_errors_in_batch(self):
        companies = [
            {"id": "1", "brand_name": "Alpha"},
            {"id": "2", "brand_name": "Beta"},
        ]

        scan_results = [
            {"company_id": "1", "brand_slug": "alpha", "platforms": {}, "cross_platform_severity": 0.7},
            {"company_id": "2", "error": "API timeout"},
        ]

        with patch(
            "app.engine_a.pipeline.get_companies_for_scanning",
            new_callable=AsyncMock,
            return_value=companies,
        ), patch(
            "app.engine_a.pipeline.scan_batch",
            new_callable=AsyncMock,
            return_value=scan_results,
        ), patch(
            "app.engine_a.pipeline._record_pipeline_run",
            new_callable=AsyncMock,
        ):
            result = await run_tier1_scan()

            assert result["companies_scanned"] == 1
            assert result["companies_errored"] == 1

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        with patch(
            "app.engine_a.pipeline.get_companies_for_scanning",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_fetch:
            await run_tier1_scan(limit=10)
            mock_fetch.assert_called_once_with(limit=10, stage="discovered")
