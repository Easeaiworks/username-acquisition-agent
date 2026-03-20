"""Tests for the outreach engine — message generation, reply classification, sequence management."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.engine_b.message_generator import (
    _build_platform_summary,
    _add_compliance_footer,
    _fallback_message,
    generate_outreach_message,
)
from app.engine_b.reply_classifier import (
    _quick_classify,
    _rule_based_classify,
    classify_reply,
)
from app.engine_b.sequence_manager import (
    create_outreach_sequence,
)


class TestBuildPlatformSummary:
    def test_empty_details(self):
        result = _build_platform_summary([])
        assert "No specific" in result

    def test_single_platform(self):
        details = [{"platform": "instagram", "issue": "uses @acmehq", "handle_available": False, "dormant": False}]
        result = _build_platform_summary(details)
        assert "Instagram" in result
        assert "acmehq" in result

    def test_dormant_flag(self):
        details = [{"platform": "twitch", "issue": "handle taken", "handle_available": False, "dormant": True}]
        result = _build_platform_summary(details)
        assert "inactive" in result

    def test_available_flag(self):
        details = [{"platform": "tiktok", "issue": "no presence", "handle_available": True, "dormant": False}]
        result = _build_platform_summary(details)
        assert "AVAILABLE" in result


class TestComplianceFooter:
    def test_adds_unsubscribe_link(self):
        body = "Hello, this is a test email."
        result = _add_compliance_footer(body)
        assert "unsubscribe" in result.lower()
        assert body in result

    def test_preserves_original_body(self):
        body = "Original content here."
        result = _add_compliance_footer(body)
        assert result.startswith(body)


class TestFallbackMessage:
    def test_step1_template(self):
        result = _fallback_message("Acme Corp", "Jane Doe", 1)
        assert "Acme Corp" in result["subject"]
        assert "Jane" in result["body"]
        assert result["step"] == 1
        assert result["model"] == "fallback_template"

    def test_step2_template(self):
        result = _fallback_message("Acme Corp", "Jane Doe", 2)
        assert result["step"] == 2

    def test_step3_has_calendly_placeholder(self):
        result = _fallback_message("Acme Corp", "Jane Doe", 3)
        assert "calendly_link" in result["body"]

    def test_step4_breakup(self):
        result = _fallback_message("Acme Corp", "Jane Doe", 4)
        assert result["step"] == 4
        assert "unsubscribe" in result["body"].lower()

    def test_all_steps_have_compliance_footer(self):
        for step in range(1, 5):
            result = _fallback_message("Test Co", "John Smith", step)
            assert "unsubscribe" in result["body"].lower()


class TestQuickClassify:
    def test_ooo_detection(self):
        result = _quick_classify("I am out of the office until March 30th.")
        assert result is not None
        assert result["classification"] == "ooo"
        assert result["confidence"] >= 0.9

    def test_unsubscribe_detection(self):
        result = _quick_classify("Please unsubscribe me from this list.")
        assert result is not None
        assert result["classification"] == "unsubscribe"

    def test_short_negative(self):
        result = _quick_classify("Not interested")
        assert result is not None
        assert result["classification"] == "negative"

    def test_no_match_returns_none(self):
        result = _quick_classify("Thanks for reaching out! I'd love to learn more about this.")
        assert result is None

    def test_auto_reply_detection(self):
        result = _quick_classify("This is an automatic reply. I am currently away on vacation.")
        assert result is not None
        assert result["classification"] == "ooo"

    def test_remove_me(self):
        result = _quick_classify("Please remove me from your mailing list")
        assert result is not None
        assert result["classification"] == "unsubscribe"


class TestRuleBasedClassify:
    def test_positive_signals(self):
        result = _rule_based_classify("That sounds great! I'd love to schedule a call.")
        assert result["classification"] == "positive"

    def test_negative_signals(self):
        result = _rule_based_classify("Not interested, please stop emailing me.")
        assert result["classification"] == "negative"

    def test_objection_signals(self):
        result = _rule_based_classify("We don't have the budget for this right now, maybe next quarter.")
        assert result["classification"] == "objection"

    def test_neutral_no_signals(self):
        result = _rule_based_classify("Okay I saw your email.")
        assert result["classification"] == "neutral"


class TestGenerateOutreachMessage:
    @pytest.mark.asyncio
    async def test_fallback_when_no_api_key(self):
        with patch("app.engine_b.message_generator.settings") as mock_settings:
            mock_settings.anthropic_api_key = None
            mock_settings.physical_address = "123 Main St"

            result = await generate_outreach_message(
                company_name="Acme Corp",
                contact_name="Jane Doe",
                contact_title="CMO",
                platform_details=[],
                sequence_step=1,
            )

            assert result["model"] == "fallback_template"
            assert "Acme Corp" in result["subject"]
            assert "Jane" in result["body"]


class TestClassifyReply:
    @pytest.mark.asyncio
    async def test_empty_reply(self):
        result = await classify_reply("")
        assert result["classification"] == "neutral"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_ooo_reply(self):
        result = await classify_reply("I am out of the office until April 5th.")
        assert result["classification"] == "ooo"

    @pytest.mark.asyncio
    async def test_unsubscribe_reply(self):
        result = await classify_reply("Please unsubscribe me from all future emails.")
        assert result["classification"] == "unsubscribe"

    @pytest.mark.asyncio
    async def test_falls_back_to_rules_without_api_key(self):
        with patch("app.engine_b.reply_classifier.settings") as mock_settings:
            mock_settings.anthropic_api_key = None
            result = await classify_reply("Sounds interesting, tell me more!")
            assert result["classification"] == "positive"


class TestCreateOutreachSequence:
    @pytest.mark.asyncio
    async def test_blocks_without_email(self):
        company = {"id": "c1", "brand_name": "Test"}
        contact = {"id": "ct1", "email": None, "full_name": "John", "title": "CEO"}

        result = await create_outreach_sequence(company, contact)
        assert result is None

    @pytest.mark.asyncio
    async def test_creates_sequence_when_compliant(self):
        company = {"id": "c1", "brand_name": "Test Corp", "industry": "tech", "employee_range": "51-200"}
        contact = {"id": "ct1", "email": "john@test.com", "full_name": "John Smith", "title": "CMO"}

        mock_insert_result = MagicMock()
        mock_insert_result.data = [{"id": "out-1", "status": "draft", "company_id": "c1", "contact_id": "ct1"}]

        with patch(
            "app.engine_b.sequence_manager.can_send_outreach",
            new_callable=AsyncMock,
            return_value=(True, "approved"),
        ), patch(
            "app.engine_b.sequence_manager._get_platform_details",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.engine_b.sequence_manager.generate_outreach_message",
            new_callable=AsyncMock,
            return_value={"subject": "Test Subject", "body": "Test Body", "model": "fallback"},
        ), patch(
            "app.engine_b.sequence_manager.get_service_client",
        ) as mock_db:
            mock_db.return_value.table.return_value.insert.return_value.execute.return_value = mock_insert_result

            result = await create_outreach_sequence(company, contact, auto_send=False)

            assert result is not None
            assert result["id"] == "out-1"

    @pytest.mark.asyncio
    async def test_blocked_by_compliance(self):
        company = {"id": "c1", "brand_name": "Test"}
        contact = {"id": "ct1", "email": "blocked@test.com", "full_name": "John", "title": "CEO"}

        with patch(
            "app.engine_b.sequence_manager.can_send_outreach",
            new_callable=AsyncMock,
            return_value=(False, "suppressed"),
        ):
            result = await create_outreach_sequence(company, contact)
            assert result is None
