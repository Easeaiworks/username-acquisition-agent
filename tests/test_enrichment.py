"""Tests for the contact enrichment engine."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.engine_b.enrichment import (
    _merge_contacts,
    _rank_contacts,
    enrich_company_contacts,
)


class TestMergeContacts:
    def test_dedup_by_email(self):
        contacts = [
            {"email": "jane@acme.com", "full_name": "Jane Doe", "email_confidence": 0.9, "title": "CMO"},
            {"email": "jane@acme.com", "full_name": "Jane D.", "email_confidence": 0.7, "title": None},
        ]
        merged = _merge_contacts(contacts)
        assert len(merged) == 1
        assert merged[0]["email_confidence"] == 0.9  # Keeps higher confidence
        assert merged[0]["title"] == "CMO"

    def test_dedup_by_name(self):
        contacts = [
            {"email": None, "full_name": "John Smith", "title": "VP Marketing"},
            {"email": "john@acme.com", "full_name": "John Smith", "email_confidence": 0.8},
        ]
        merged = _merge_contacts(contacts)
        assert len(merged) == 1
        assert merged[0]["email"] == "john@acme.com"  # Email filled in

    def test_keeps_unique_contacts(self):
        contacts = [
            {"email": "jane@acme.com", "full_name": "Jane Doe"},
            {"email": "john@acme.com", "full_name": "John Smith"},
            {"email": "bob@acme.com", "full_name": "Bob Jones"},
        ]
        merged = _merge_contacts(contacts)
        assert len(merged) == 3

    def test_skips_empty_contacts(self):
        contacts = [
            {"email": None, "full_name": None},
            {"email": "", "full_name": ""},
            {"email": "real@acme.com", "full_name": "Real Person"},
        ]
        merged = _merge_contacts(contacts)
        assert len(merged) == 1

    def test_merges_supplementary_fields(self):
        contacts = [
            {"email": "jane@acme.com", "full_name": "Jane", "title": "CMO", "linkedin_url": None, "phone": None, "department": None, "seniority_level": None},
            {"email": "jane@acme.com", "full_name": "Jane", "title": None, "linkedin_url": "linkedin.com/jane", "phone": "555-1234", "department": "marketing", "seniority_level": "c_suite", "email_confidence": 0.5},
        ]
        merged = _merge_contacts(contacts)
        assert len(merged) == 1
        assert merged[0]["linkedin_url"] == "linkedin.com/jane"
        assert merged[0]["phone"] == "555-1234"


class TestRankContacts:
    def test_csuite_brand_ranks_highest(self):
        contacts = [
            {"seniority_level": "individual", "department": "other", "email_confidence": 0.5},
            {"seniority_level": "c_suite", "department": "brand", "email_confidence": 0.9},
            {"seniority_level": "manager", "department": "marketing", "email_confidence": 0.7},
        ]
        ranked = _rank_contacts(contacts)
        assert ranked[0]["seniority_level"] == "c_suite"

    def test_email_confidence_boosts_priority(self):
        contacts = [
            {"seniority_level": "director", "department": "marketing", "email_confidence": 0.2},
            {"seniority_level": "director", "department": "marketing", "email_confidence": 0.95},
        ]
        ranked = _rank_contacts(contacts)
        # Higher confidence should rank first
        assert ranked[0]["email_confidence"] == 0.95

    def test_all_contacts_get_priority_score(self):
        contacts = [
            {"seniority_level": "vp", "department": "social", "email_confidence": 0.8},
            {"seniority_level": "manager", "department": "digital", "email_confidence": 0.6},
        ]
        ranked = _rank_contacts(contacts)
        assert all("outreach_priority" in c for c in ranked)
        assert all(c["outreach_priority"] > 0 for c in ranked)


class TestEnrichCompanyContacts:
    @pytest.mark.asyncio
    async def test_enrichment_combines_sources(self):
        company = {
            "id": "test-123",
            "brand_name": "Acme Corp",
            "domain": "acme.com",
        }

        rr_contacts = [
            {
                "first_name": "Jane", "last_name": "Doe", "full_name": "Jane Doe",
                "title": "CMO", "email": "jane@acme.com", "email_confidence": 0.9,
                "email_source": "rocketreach", "seniority_level": "c_suite",
                "department": "marketing", "linkedin_url": None, "phone": None,
                "rocketreach_id": "123", "enrichment_data": {},
            },
        ]

        hunter_contacts = [
            {
                "first_name": "Bob", "last_name": "Smith", "full_name": "Bob Smith",
                "title": "Social Media Manager", "email": "bob@acme.com",
                "email_confidence": 0.7, "email_source": "hunter",
                "seniority_level": "manager", "department": "social",
            },
        ]

        mock_db_result = MagicMock()
        mock_db_result.data = [{"total_opportunity_score": 0.75, "priority_bucket": "very_high"}]

        with patch(
            "app.engine_b.enrichment.rr_search",
            new_callable=AsyncMock,
            return_value=rr_contacts,
        ), patch(
            "app.engine_b.enrichment.hunter_domain_search",
            new_callable=AsyncMock,
            return_value=hunter_contacts,
        ), patch(
            "app.engine_b.enrichment.verify_email",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.engine_b.enrichment.get_service_client",
        ) as mock_db:
            # Mock the DB calls
            mock_table = MagicMock()
            mock_db.return_value.table.return_value = mock_table
            mock_table.upsert.return_value.execute.return_value = MagicMock()
            mock_table.select.return_value.eq.return_value.execute.return_value = mock_db_result
            mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()

            result = await enrich_company_contacts(company, verify_emails=False)

            assert result["company_id"] == "test-123"
            assert result["rocketreach_found"] == 1
            assert result["hunter_found"] >= 1
            assert result["contacts_saved"] > 0

    @pytest.mark.asyncio
    async def test_enrichment_handles_no_domain(self):
        company = {
            "id": "test-456",
            "brand_name": "No Domain Inc",
            "domain": None,
        }

        with patch(
            "app.engine_b.enrichment.rr_search",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.engine_b.enrichment.hunter_domain_search",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.engine_b.enrichment.get_service_client",
        ) as mock_db:
            mock_table = MagicMock()
            mock_db.return_value.table.return_value = mock_table
            mock_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"total_opportunity_score": 0.3, "priority_bucket": "low"}])
            mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()

            result = await enrich_company_contacts(company, verify_emails=False)

            assert result["contacts_saved"] == 0


class TestRocketReachIntegration:
    """Test RocketReach helper functions."""

    def test_classify_seniority(self):
        from app.integrations.rocketreach import _classify_seniority
        assert _classify_seniority("Chief Marketing Officer") == "c_suite"
        assert _classify_seniority("VP of Brand") == "vp"
        assert _classify_seniority("Director of Social Media") == "director"
        assert _classify_seniority("Social Media Manager") == "manager"
        assert _classify_seniority("Marketing Associate") == "individual"

    def test_classify_department(self):
        from app.integrations.rocketreach import _classify_department
        assert _classify_department("Social Media Manager") == "social"
        assert _classify_department("Brand Director") == "brand"
        assert _classify_department("Digital Marketing Lead") == "digital"
        assert _classify_department("VP Marketing") == "marketing"
        assert _classify_department("CEO") == "executive"

    def test_parse_profile(self):
        from app.integrations.rocketreach import _parse_profile
        profile = {
            "id": 12345,
            "first_name": "Jane",
            "last_name": "Doe",
            "name": "Jane Doe",
            "current_title": "CMO",
            "emails": [
                {"email": "jane@acme.com", "type": "professional", "confidence": 95},
            ],
            "linkedin_url": "https://linkedin.com/in/janedoe",
            "phones": ["+1-555-1234"],
            "city": "San Francisco",
            "region": "California",
            "country_code": "US",
            "current_employer": "Acme Corp",
        }
        result = _parse_profile(profile)
        assert result["full_name"] == "Jane Doe"
        assert result["email"] == "jane@acme.com"
        assert result["email_confidence"] == 0.95
        assert result["seniority_level"] == "c_suite"
        assert result["department"] == "marketing"


class TestHunterIntegration:
    """Test Hunter.io helper functions."""

    def test_parse_email_result(self):
        from app.integrations.hunter import _parse_email_result
        entry = {
            "value": "jane@acme.com",
            "confidence": 92,
            "type": "personal",
            "first_name": "Jane",
            "last_name": "Doe",
            "position": "Marketing Director",
            "department": "marketing",
            "seniority": "senior",
            "linkedin": "https://linkedin.com/in/janedoe",
            "sources": [{"uri": "https://acme.com/team"}],
        }
        result = _parse_email_result(entry, "acme.com")
        assert result["email"] == "jane@acme.com"
        assert result["email_confidence"] == 0.92
        assert result["full_name"] == "Jane Doe"
        assert result["title"] == "Marketing Director"
        assert result["sources_count"] == 1

    def test_parse_empty_entry(self):
        from app.integrations.hunter import _parse_email_result
        assert _parse_email_result({}, "acme.com") is None
        assert _parse_email_result(None, "acme.com") is None
