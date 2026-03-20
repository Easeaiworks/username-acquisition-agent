"""
Tests for the daily reporting module — collector, formatter, and API.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_report():
    """A complete daily report payload for testing formatters."""
    return {
        "report_date": "2025-01-15",
        "generated_at": "2025-01-15T06:30:00",
        "pipeline": {
            "date": "2025-01-15",
            "total_companies": 450,
            "stage_breakdown": {
                "new": 50,
                "scanned": 100,
                "scored": 80,
                "enriched": 60,
                "qualified": 40,
                "approval_queue": 30,
                "outreach_active": 50,
                "meeting_booked": 20,
                "rejected": 10,
                "parked": 10,
            },
            "new_companies_today": 25,
            "stage_movements_today": 65,
        },
        "scoring": {
            "priority_distribution": {
                "critical": 15,
                "very_high": 35,
                "high": 80,
                "medium": 120,
                "low": 200,
            },
            "scored_today": 40,
            "avg_score_today": 0.5823,
            "high_value_today": 12,
        },
        "outreach": {
            "sent_today": 18,
            "replies_today": 4,
            "reply_rate_today": 22.2,
            "reply_classifications": {
                "positive": 2,
                "neutral": 1,
                "negative": 0,
                "objection": 1,
                "ooo": 0,
                "unsubscribe": 0,
            },
            "meetings_booked_today": 1,
            "bounces_today": 0,
            "active_sequences_total": 85,
        },
        "top_opportunities": [
            {
                "id": "c1",
                "brand_name": "TechCorp",
                "domain": "techcorp.com",
                "industry": "technology",
                "composite_score": 0.892,
                "priority_bucket": "critical",
                "pipeline_stage": "qualified",
            },
            {
                "id": "c2",
                "brand_name": "MediaBrand",
                "domain": "mediabrand.com",
                "industry": "media",
                "composite_score": 0.756,
                "priority_bucket": "very_high",
                "pipeline_stage": "enriched",
            },
        ],
        "attention_required": {
            "pending_approvals": 5,
            "stale_sequences": 3,
            "unreviewed_objections": 2,
            "hot_leads_no_meeting": 1,
        },
        "health": {
            "total_attention_items": 11,
            "pipeline_active": True,
            "outreach_active": True,
        },
    }


# ---------------------------------------------------------------------------
# Formatter Tests
# ---------------------------------------------------------------------------

class TestTextFormatter:
    def test_format_text_summary_contains_key_sections(self, sample_report):
        from app.reporting.formatter import format_text_summary
        text = format_text_summary(sample_report)

        assert "Daily Report" in text
        assert "2025-01-15" in text
        assert "PIPELINE" in text
        assert "SCORING" in text
        assert "OUTREACH" in text
        assert "ATTENTION REQUIRED" in text
        assert "TOP OPPORTUNITIES" in text

    def test_format_text_summary_includes_pipeline_stats(self, sample_report):
        from app.reporting.formatter import format_text_summary
        text = format_text_summary(sample_report)

        assert "450" in text  # total companies
        assert "25" in text   # new today
        assert "65" in text   # stage movements

    def test_format_text_summary_includes_outreach_stats(self, sample_report):
        from app.reporting.formatter import format_text_summary
        text = format_text_summary(sample_report)

        assert "Sent today: 18" in text
        assert "22.2%" in text  # reply rate
        assert "Meetings booked: 1" in text

    def test_format_text_summary_includes_attention_items(self, sample_report):
        from app.reporting.formatter import format_text_summary
        text = format_text_summary(sample_report)

        assert "5 companies pending approval" in text
        assert "3 stale sequences" in text
        assert "2 objections needing review" in text
        assert "1 positive replies without meeting" in text

    def test_format_text_summary_includes_top_opps(self, sample_report):
        from app.reporting.formatter import format_text_summary
        text = format_text_summary(sample_report)

        assert "TechCorp" in text
        assert "0.892" in text
        assert "MediaBrand" in text

    def test_format_text_summary_no_attention_when_empty(self, sample_report):
        from app.reporting.formatter import format_text_summary
        sample_report["attention_required"] = {
            "pending_approvals": 0,
            "stale_sequences": 0,
            "unreviewed_objections": 0,
            "hot_leads_no_meeting": 0,
        }
        text = format_text_summary(sample_report)
        assert "ATTENTION REQUIRED" not in text

    def test_format_text_summary_no_top_opps_when_empty(self, sample_report):
        from app.reporting.formatter import format_text_summary
        sample_report["top_opportunities"] = []
        text = format_text_summary(sample_report)
        assert "TOP OPPORTUNITIES" not in text


class TestHtmlFormatter:
    def test_format_html_email_is_valid_html(self, sample_report):
        from app.reporting.formatter import format_html_email
        html = format_html_email(sample_report)

        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html
        assert "Daily Pipeline Report" in html

    def test_format_html_email_includes_kpis(self, sample_report):
        from app.reporting.formatter import format_html_email
        html = format_html_email(sample_report)

        assert "450" in html    # total pipeline
        assert "18" in html     # emails sent
        assert "1" in html      # meetings (may match other numbers too)

    def test_format_html_email_includes_attention(self, sample_report):
        from app.reporting.formatter import format_html_email
        html = format_html_email(sample_report)

        assert "Attention Required" in html
        assert "pending approval" in html

    def test_format_html_email_includes_top_opps_table(self, sample_report):
        from app.reporting.formatter import format_html_email
        html = format_html_email(sample_report)

        assert "TechCorp" in html
        assert "0.892" in html
        assert "critical" in html

    def test_format_html_email_no_attention_section_when_clean(self, sample_report):
        from app.reporting.formatter import format_html_email
        sample_report["attention_required"] = {
            "pending_approvals": 0,
            "stale_sequences": 0,
            "unreviewed_objections": 0,
            "hot_leads_no_meeting": 0,
        }
        html = format_html_email(sample_report)
        assert "Attention Required" not in html


# ---------------------------------------------------------------------------
# Collector Tests
# ---------------------------------------------------------------------------

class TestCollector:
    @patch("app.reporting.collector.get_service_client")
    @pytest.mark.asyncio
    async def test_collect_pipeline_metrics_returns_structure(self, mock_db):
        from app.reporting.collector import collect_pipeline_metrics

        # Mock the Supabase chain
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_gte = MagicMock()
        mock_lt = MagicMock()
        mock_execute = MagicMock()

        mock_execute.return_value = MagicMock(count=10, data=[])
        mock_lt.return_value = MagicMock(execute=mock_execute)
        mock_gte.return_value = MagicMock(lt=mock_lt, execute=mock_execute)
        mock_eq.return_value = MagicMock(execute=mock_execute)
        mock_select.return_value = MagicMock(
            eq=mock_eq,
            gte=mock_gte,
            execute=mock_execute,
        )
        mock_table.return_value = MagicMock(select=mock_select)
        mock_db.return_value = MagicMock(table=mock_table)

        result = await collect_pipeline_metrics()

        assert "date" in result
        assert "total_companies" in result
        assert "stage_breakdown" in result
        assert "new_companies_today" in result
        assert "stage_movements_today" in result

    @patch("app.reporting.collector.get_service_client")
    @pytest.mark.asyncio
    async def test_collect_scoring_metrics_returns_structure(self, mock_db):
        from app.reporting.collector import collect_scoring_metrics

        mock_table = MagicMock()
        mock_execute = MagicMock(return_value=MagicMock(count=5, data=[
            {"composite_score": 0.7},
            {"composite_score": 0.8},
        ]))

        # Build the chain properly
        mock_chain = MagicMock()
        mock_chain.execute = mock_execute
        mock_chain.lt = MagicMock(return_value=MagicMock(execute=mock_execute))
        mock_chain.gte = MagicMock(return_value=mock_chain)
        mock_chain.eq = MagicMock(return_value=MagicMock(execute=mock_execute))

        mock_select = MagicMock(return_value=mock_chain)
        mock_table.return_value = MagicMock(select=mock_select)
        mock_db.return_value = MagicMock(table=mock_table)

        result = await collect_scoring_metrics()

        assert "priority_distribution" in result
        assert "scored_today" in result
        assert "avg_score_today" in result
        assert "high_value_today" in result

    @patch("app.reporting.collector.get_service_client")
    @pytest.mark.asyncio
    async def test_collect_attention_items_returns_structure(self, mock_db):
        from app.reporting.collector import collect_attention_items

        mock_execute = MagicMock(return_value=MagicMock(count=3, data=[]))
        mock_chain = MagicMock()
        mock_chain.execute = mock_execute
        mock_chain.eq = MagicMock(return_value=mock_chain)
        mock_chain.lt = MagicMock(return_value=MagicMock(execute=mock_execute))

        mock_select = MagicMock(return_value=mock_chain)
        mock_table = MagicMock(return_value=MagicMock(select=mock_select))
        mock_db.return_value = MagicMock(table=mock_table)

        result = await collect_attention_items()

        assert "pending_approvals" in result
        assert "stale_sequences" in result
        assert "unreviewed_objections" in result
        assert "hot_leads_no_meeting" in result


# ---------------------------------------------------------------------------
# Persist Tests
# ---------------------------------------------------------------------------

class TestPersist:
    @patch("app.reporting.formatter.get_service_client")
    @pytest.mark.asyncio
    async def test_persist_report_upserts_to_db(self, mock_db, sample_report):
        from app.reporting.formatter import persist_report

        mock_execute = MagicMock(return_value=MagicMock(data=[{"id": "r1"}]))
        mock_upsert = MagicMock(return_value=MagicMock(execute=mock_execute))
        mock_table = MagicMock(return_value=MagicMock(upsert=mock_upsert))
        mock_db.return_value = MagicMock(table=mock_table)

        result = await persist_report(sample_report)

        assert result["id"] == "r1"
        mock_table.assert_called_with("daily_reports")
        mock_upsert.assert_called_once()

        # Verify the record has expected keys
        call_args = mock_upsert.call_args[0][0]
        assert call_args["report_date"] == "2025-01-15"
        assert call_args["pipeline_total"] == 450
        assert call_args["emails_sent"] == 18
        assert call_args["meetings_booked"] == 1


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------

class TestReportsAPI:
    @patch("app.api.reports.collect_full_daily_report")
    @patch("app.api.reports.format_text_summary")
    @pytest.mark.asyncio
    async def test_get_today_report(self, mock_format, mock_collect, sample_report):
        mock_collect.return_value = sample_report
        mock_format.return_value = "summary text"

        from app.api.reports import get_today_report
        result = await get_today_report()

        assert result["report"] == sample_report
        assert result["text_summary"] == "summary text"

    @patch("app.api.reports.get_service_client")
    @pytest.mark.asyncio
    async def test_get_latest_report_returns_data(self, mock_db):
        mock_execute = MagicMock(return_value=MagicMock(data=[{"report_date": "2025-01-15", "id": "r1"}]))
        mock_chain = MagicMock()
        mock_chain.limit = MagicMock(return_value=MagicMock(execute=mock_execute))
        mock_chain.order = MagicMock(return_value=mock_chain)

        mock_select = MagicMock(return_value=mock_chain)
        mock_table = MagicMock(return_value=MagicMock(select=mock_select))
        mock_db.return_value = MagicMock(table=mock_table)

        from app.api.reports import get_latest_report
        result = await get_latest_report()

        assert result["report_date"] == "2025-01-15"

    @patch("app.api.reports.get_service_client")
    @pytest.mark.asyncio
    async def test_get_latest_report_empty(self, mock_db):
        mock_execute = MagicMock(return_value=MagicMock(data=[]))
        mock_chain = MagicMock()
        mock_chain.limit = MagicMock(return_value=MagicMock(execute=mock_execute))
        mock_chain.order = MagicMock(return_value=mock_chain)

        mock_select = MagicMock(return_value=mock_chain)
        mock_table = MagicMock(return_value=MagicMock(select=mock_select))
        mock_db.return_value = MagicMock(table=mock_table)

        from app.api.reports import get_latest_report
        result = await get_latest_report()

        assert "message" in result

    @patch("app.api.reports.get_service_client")
    @pytest.mark.asyncio
    async def test_get_report_history(self, mock_db):
        mock_execute = MagicMock(return_value=MagicMock(data=[
            {"report_date": "2025-01-14", "emails_sent": 15},
            {"report_date": "2025-01-15", "emails_sent": 18},
        ]))
        mock_chain = MagicMock()
        mock_chain.order = MagicMock(return_value=MagicMock(execute=mock_execute))
        mock_chain.gte = MagicMock(return_value=mock_chain)

        mock_select = MagicMock(return_value=mock_chain)
        mock_table = MagicMock(return_value=MagicMock(select=mock_select))
        mock_db.return_value = MagicMock(table=mock_table)

        from app.api.reports import get_report_history
        result = await get_report_history(days=30)

        assert result["period_days"] == 30
        assert result["count"] == 2
        assert len(result["reports"]) == 2

    @patch("app.api.reports.get_service_client")
    @pytest.mark.asyncio
    async def test_get_trends_insufficient_data(self, mock_db):
        mock_execute = MagicMock(return_value=MagicMock(data=[{"report_date": "2025-01-15"}]))
        mock_chain = MagicMock()
        mock_chain.order = MagicMock(return_value=MagicMock(execute=mock_execute))
        mock_chain.gte = MagicMock(return_value=mock_chain)

        mock_select = MagicMock(return_value=mock_chain)
        mock_table = MagicMock(return_value=MagicMock(select=mock_select))
        mock_db.return_value = MagicMock(table=mock_table)

        from app.api.reports import get_trends
        result = await get_trends(days=14)

        assert "Not enough data" in result["message"]

    @patch("app.api.reports.get_service_client")
    @pytest.mark.asyncio
    async def test_get_trends_calculates_changes(self, mock_db):
        mock_execute = MagicMock(return_value=MagicMock(data=[
            {"report_date": "2025-01-01", "emails_sent": 10, "replies_received": 2, "meetings_booked": 0, "avg_score": 0.5},
            {"report_date": "2025-01-02", "emails_sent": 10, "replies_received": 2, "meetings_booked": 0, "avg_score": 0.5},
            {"report_date": "2025-01-08", "emails_sent": 15, "replies_received": 4, "meetings_booked": 1, "avg_score": 0.6},
            {"report_date": "2025-01-09", "emails_sent": 15, "replies_received": 4, "meetings_booked": 1, "avg_score": 0.6},
        ]))
        mock_chain = MagicMock()
        mock_chain.order = MagicMock(return_value=MagicMock(execute=mock_execute))
        mock_chain.gte = MagicMock(return_value=mock_chain)

        mock_select = MagicMock(return_value=mock_chain)
        mock_table = MagicMock(return_value=MagicMock(select=mock_select))
        mock_db.return_value = MagicMock(table=mock_table)

        from app.api.reports import get_trends
        result = await get_trends(days=14)

        assert "trends" in result
        assert result["data_points"] == 4
        assert "totals" in result
        assert result["totals"]["total_emails"] == 50

    @patch("app.api.reports.get_service_client")
    @pytest.mark.asyncio
    async def test_get_report_by_date(self, mock_db):
        mock_execute = MagicMock(return_value=MagicMock(data=[{"report_date": "2025-01-15", "id": "r1"}]))
        mock_chain = MagicMock()
        mock_chain.eq = MagicMock(return_value=MagicMock(execute=mock_execute))

        mock_select = MagicMock(return_value=mock_chain)
        mock_table = MagicMock(return_value=MagicMock(select=mock_select))
        mock_db.return_value = MagicMock(table=mock_table)

        from app.api.reports import get_report_by_date
        result = await get_report_by_date("2025-01-15")

        assert result["report_date"] == "2025-01-15"
