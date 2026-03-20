"""Tests for the scoring engine."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.engine_a.scoring import (
    calculate_brand_value,
    calculate_handle_pain,
    calculate_urgency,
    calculate_reachability,
    classify_priority_bucket,
    score_company,
)
from app.models.company import PriorityBucket


class TestCalculateBrandValue:
    @pytest.mark.asyncio
    async def test_large_public_tech_company(self):
        company = {
            "employee_range": "10000+",
            "is_public": True,
            "consumer_facing_score": 0.9,
            "industry": "technology",
            "founding_year": 1998,
        }
        score, signals = await calculate_brand_value(company)
        assert score > 0.7  # Should be high value
        assert signals["is_public"] > 0

    @pytest.mark.asyncio
    async def test_small_unknown_company(self):
        company = {
            "employee_range": "1-10",
            "is_public": False,
            "consumer_facing_score": 0.2,
            "industry": "consulting",
            "founding_year": 2023,
        }
        score, signals = await calculate_brand_value(company)
        assert score < 0.4  # Should be low value

    @pytest.mark.asyncio
    async def test_midsize_ecommerce_company(self):
        company = {
            "employee_range": "201-500",
            "is_public": False,
            "consumer_facing_score": 0.8,
            "industry": "e-commerce",
            "founding_year": 2015,
        }
        score, signals = await calculate_brand_value(company)
        assert 0.4 < score < 0.8  # Should be medium-high

    @pytest.mark.asyncio
    async def test_missing_fields_defaults_gracefully(self):
        company = {}
        score, signals = await calculate_brand_value(company)
        assert 0.0 <= score <= 1.0  # Should not crash

    @pytest.mark.asyncio
    async def test_industry_scoring_high_value(self):
        company = {"industry": "gaming", "employee_range": "51-200"}
        score, signals = await calculate_brand_value(company)
        assert signals["industry_relevance"] == 0.85

    @pytest.mark.asyncio
    async def test_industry_scoring_medium_value(self):
        company = {"industry": "finance", "employee_range": "51-200"}
        score, signals = await calculate_brand_value(company)
        assert signals["industry_relevance"] == 0.55


class TestCalculateHandlePain:
    @pytest.mark.asyncio
    async def test_no_handle_data(self):
        mock_result = MagicMock()
        mock_result.data = []

        with patch("app.engine_a.scoring.get_service_client") as mock_db:
            mock_db.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            score, signals = await calculate_handle_pain("test-id")
            assert score == 0.0

    @pytest.mark.asyncio
    async def test_all_platforms_mismatched(self):
        handles = [
            {"platform": "instagram", "mismatch_severity": 0.7, "account_dormant": False, "handle_available": False},
            {"platform": "tiktok", "mismatch_severity": 0.6, "account_dormant": False, "handle_available": False},
            {"platform": "youtube", "mismatch_severity": 0.8, "account_dormant": True, "handle_available": False},
            {"platform": "twitch", "mismatch_severity": 0.5, "account_dormant": False, "handle_available": True},
        ]
        mock_result = MagicMock()
        mock_result.data = handles

        with patch("app.engine_a.scoring.get_service_client") as mock_db:
            mock_db.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            score, signals = await calculate_handle_pain("test-id")

            assert score > 0.7  # High pain due to mismatches + dormant + inconsistency
            assert signals["dormant_bonus"] > 0
            assert signals["inconsistency_bonus"] > 0

    @pytest.mark.asyncio
    async def test_perfect_handles_no_pain(self):
        handles = [
            {"platform": "instagram", "mismatch_severity": 0.0, "account_dormant": False, "handle_available": False},
            {"platform": "youtube", "mismatch_severity": 0.0, "account_dormant": False, "handle_available": False},
        ]
        mock_result = MagicMock()
        mock_result.data = handles

        with patch("app.engine_a.scoring.get_service_client") as mock_db:
            mock_db.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            score, signals = await calculate_handle_pain("test-id")
            assert score == 0.0


class TestCalculateUrgency:
    @pytest.mark.asyncio
    async def test_available_handles_create_urgency(self):
        company = {}
        handle_signals = {
            "platforms": {
                "instagram": {"available": True, "dormant": False},
                "tiktok": {"available": True, "dormant": False},
            },
        }
        score, signals = await calculate_urgency(company, handle_signals)
        assert score > 0.2  # Available handles should drive urgency

    @pytest.mark.asyncio
    async def test_funding_and_ipo_signals(self):
        company = {
            "urgency_signals": {"recent_funding": True, "ipo_planned": True},
        }
        handle_signals = {"platforms": {}}
        score, signals = await calculate_urgency(company, handle_signals)
        assert score >= 0.4  # Funding + IPO should be urgent

    @pytest.mark.asyncio
    async def test_no_urgency_signals(self):
        company = {}
        handle_signals = {"platforms": {}}
        score, signals = await calculate_urgency(company, handle_signals)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_dormant_holders_moderate_urgency(self):
        company = {}
        handle_signals = {
            "platforms": {
                "instagram": {"available": False, "dormant": True},
            },
        }
        score, signals = await calculate_urgency(company, handle_signals)
        assert 0.1 <= score <= 0.3


class TestCalculateReachability:
    @pytest.mark.asyncio
    async def test_us_company_with_domain(self):
        company = {
            "domain": "example.com",
            "employee_range": "51-200",
            "country": "United States",
        }
        score, signals = await calculate_reachability(company)
        assert score > 0.5  # Good reachability

    @pytest.mark.asyncio
    async def test_large_company_hard_to_reach(self):
        company = {
            "domain": "megacorp.com",
            "employee_range": "10000+",
            "country": "United States",
        }
        score, signals = await calculate_reachability(company)
        assert signals["size_reachability"] < 0.1

    @pytest.mark.asyncio
    async def test_no_domain_reduces_reachability(self):
        company = {"employee_range": "11-50", "country": "Canada"}
        score, signals = await calculate_reachability(company)
        assert not signals["has_domain"]


class TestClassifyPriorityBucket:
    def test_critical(self):
        assert classify_priority_bucket(0.85) == PriorityBucket.CRITICAL

    def test_very_high(self):
        assert classify_priority_bucket(0.72) == PriorityBucket.VERY_HIGH

    def test_high(self):
        assert classify_priority_bucket(0.55) == PriorityBucket.HIGH

    def test_medium(self):
        assert classify_priority_bucket(0.40) == PriorityBucket.MEDIUM

    def test_low(self):
        assert classify_priority_bucket(0.20) == PriorityBucket.LOW

    def test_boundary_very_high(self):
        assert classify_priority_bucket(0.65) == PriorityBucket.VERY_HIGH

    def test_boundary_high(self):
        assert classify_priority_bucket(0.50) == PriorityBucket.HIGH


class TestScoreCompany:
    @pytest.mark.asyncio
    async def test_full_scoring_pipeline(self):
        company = {
            "id": "test-123",
            "brand_name": "TestBrand",
            "employee_range": "201-500",
            "is_public": False,
            "consumer_facing_score": 0.7,
            "industry": "technology",
            "founding_year": 2010,
            "domain": "testbrand.com",
            "country": "United States",
            "urgency_signals": {},
            "enrichment_data": {},
        }

        # Mock handle pain DB call
        handles = [
            {"platform": "instagram", "mismatch_severity": 0.6, "account_dormant": False, "handle_available": False},
            {"platform": "youtube", "mismatch_severity": 0.4, "account_dormant": True, "handle_available": False},
        ]
        mock_result = MagicMock()
        mock_result.data = handles

        with patch("app.engine_a.scoring.get_service_client") as mock_db:
            mock_db.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

            result = await score_company(company)

            assert result["company_id"] == "test-123"
            assert 0.0 <= result["brand_value_score"] <= 1.0
            assert 0.0 <= result["handle_pain_score"] <= 1.0
            assert 0.0 <= result["urgency_score"] <= 1.0
            assert 0.0 <= result["reachability_score"] <= 1.0
            assert 0.0 <= result["total_opportunity_score"] <= 1.0
            assert result["priority_bucket"] in [b.value for b in PriorityBucket]
            assert "component_signals" in result

    @pytest.mark.asyncio
    async def test_scoring_weights_sum_to_one(self):
        """Verify the scoring weights in config sum to 1.0."""
        from app.config import settings
        total_weight = (
            settings.weight_brand_value
            + settings.weight_handle_pain
            + settings.weight_urgency
            + settings.weight_reachability
        )
        assert abs(total_weight - 1.0) < 0.001
