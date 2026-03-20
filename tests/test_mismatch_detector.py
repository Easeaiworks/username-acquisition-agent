"""Tests for the mismatch detector."""

from datetime import datetime, timezone, timedelta
from app.engine_a.mismatch_detector import detect_mismatch, _check_dormancy


class TestDetectMismatch:
    def test_exact_match_no_opportunity(self):
        result = detect_mismatch(
            brand_slug="stripe",
            observed_handle="stripe",
            platform="instagram",
        )
        assert result["mismatch_type"] == "none"
        assert result["mismatch_severity"] == 0.0

    def test_modifier_detected(self):
        result = detect_mismatch(
            brand_slug="stripe",
            observed_handle="stripehq",
            platform="instagram",
        )
        assert result["mismatch_type"] == "modifier"
        assert result["mismatch_severity"] > 0

    def test_not_present_with_available_handle(self):
        result = detect_mismatch(
            brand_slug="stripe",
            observed_handle=None,
            platform="tiktok",
            account_exists=False,
            ideal_handle_available=True,
        )
        assert result["mismatch_type"] == "not_present"
        assert result["acquisition_difficulty"] == "easy"

    def test_dormant_holder_boosts_severity(self):
        two_years_ago = (datetime.now(timezone.utc) - timedelta(days=800)).isoformat()

        result = detect_mismatch(
            brand_slug="stripe",
            observed_handle="stripehq",
            platform="instagram",
            ideal_handle_available=False,
            ideal_handle_holder_info={
                "last_post_date": two_years_ago,
                "follower_count": 50,
                "post_count": 3,
            },
        )
        assert result["account_dormant"] is True
        assert result["mismatch_type"] == "inactive_holder"
        assert result["dormancy_months"] >= 24
        assert result["acquisition_difficulty"] == "easy"

    def test_active_holder_hard_acquisition(self):
        recent = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        result = detect_mismatch(
            brand_slug="stripe",
            observed_handle="stripehq",
            platform="instagram",
            ideal_handle_available=False,
            ideal_handle_holder_info={
                "last_post_date": recent,
                "follower_count": 50000,
                "post_count": 500,
            },
        )
        assert result["account_dormant"] is False
        assert result["acquisition_difficulty"] == "hard"


class TestCheckDormancy:
    def test_dormant_old_post(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        result = _check_dormancy(last_post_date=old_date)
        assert result["is_dormant"] is True
        assert result["months_dormant"] >= 12

    def test_active_recent_post(self):
        recent = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        result = _check_dormancy(last_post_date=recent)
        assert result["is_dormant"] is False

    def test_dormant_low_activity(self):
        result = _check_dormancy(follower_count=10, post_count=2)
        assert result["is_dormant"] is True
