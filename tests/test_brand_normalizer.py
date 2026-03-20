"""Tests for the brand normalization engine."""

from app.engine_a.brand_normalizer import (
    normalize_brand_name,
    generate_handle_slug,
    extract_domain_from_name,
    build_canonical_record,
)


class TestNormalizeBrandName:
    def test_strips_inc(self):
        assert normalize_brand_name("Stripe, Inc.") == "Stripe"

    def test_strips_corporation(self):
        assert normalize_brand_name("Microsoft Corporation") == "Microsoft"

    def test_strips_llc(self):
        assert normalize_brand_name("Acme LLC") == "Acme"

    def test_strips_the_prefix(self):
        assert normalize_brand_name("The Home Depot") == "Home Depot"

    def test_known_mapping_meta(self):
        assert normalize_brand_name("Meta Platforms, Inc.") == "Meta"

    def test_known_mapping_alphabet(self):
        assert normalize_brand_name("Alphabet Inc.") == "Google"

    def test_known_mapping_disney(self):
        assert normalize_brand_name("The Walt Disney Company") == "Disney"

    def test_strips_technologies(self):
        assert normalize_brand_name("Uber Technologies") == "Uber"

    def test_strips_holdings(self):
        assert normalize_brand_name("CrowdStrike Holdings") == "CrowdStrike"

    def test_strips_ltd(self):
        assert normalize_brand_name("ARM Ltd.") == "ARM"

    def test_handles_empty_string(self):
        assert normalize_brand_name("") == ""

    def test_preserves_simple_name(self):
        assert normalize_brand_name("Nike") == "Nike"

    def test_strips_multiple_suffixes(self):
        result = normalize_brand_name("Acme Software Solutions Inc.")
        # Should strip "Inc." at minimum
        assert "Inc" not in result

    def test_strips_trailing_comma(self):
        assert normalize_brand_name("Stripe,") == "Stripe"


class TestGenerateHandleSlug:
    def test_basic_slug(self):
        assert generate_handle_slug("Stripe") == "stripe"

    def test_removes_hyphens(self):
        assert generate_handle_slug("Coca-Cola") == "cocacola"

    def test_removes_spaces(self):
        assert generate_handle_slug("Under Armour") == "underarmour"

    def test_removes_ampersand(self):
        assert generate_handle_slug("H&M") == "hm"

    def test_preserves_numbers(self):
        assert generate_handle_slug("7-Eleven") == "7eleven"

    def test_handles_empty(self):
        assert generate_handle_slug("") == ""


class TestExtractDomain:
    def test_simple_domain(self):
        assert extract_domain_from_name("Stripe") == "stripe.com"

    def test_hyphenated_domain(self):
        assert extract_domain_from_name("Coca-Cola") == "coca-cola.com"

    def test_multi_word_domain(self):
        assert extract_domain_from_name("Home Depot") == "home-depot.com"


class TestBuildCanonicalRecord:
    def test_full_record(self):
        record = build_canonical_record(
            raw_name="Stripe, Inc.",
            legal_name="Stripe, Inc.",
            domain="stripe.com",
        )
        assert record["brand_name"] == "Stripe"
        assert record["handle_slug"] == "stripe"
        assert record["domain"] == "stripe.com"
        assert record["legal_name"] == "Stripe, Inc."
        assert "Stripe, Inc." in record["aliases"]

    def test_guesses_domain_if_missing(self):
        record = build_canonical_record(raw_name="Nike")
        assert record["domain"] == "nike.com"

    def test_includes_aliases(self):
        record = build_canonical_record(
            raw_name="Meta Platforms, Inc.",
            known_aliases=["Facebook", "Meta Quest"],
        )
        assert "Facebook" in record["aliases"]
        assert "Meta Quest" in record["aliases"]
