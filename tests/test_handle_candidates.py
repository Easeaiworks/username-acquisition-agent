"""Tests for the handle candidate generator."""

from app.engine_a.handle_candidates import (
    generate_candidates,
    classify_observed_handle,
)


class TestGenerateCandidates:
    def test_first_candidate_is_exact(self):
        candidates = generate_candidates("stripe")
        assert candidates[0]["handle"] == "stripe"
        assert candidates[0]["priority"] == 1

    def test_generates_suffix_variants(self):
        candidates = generate_candidates("stripe")
        handles = [c["handle"] for c in candidates]
        assert "stripehq" in handles
        assert "stripeofficial" in handles
        assert "stripeapp" in handles

    def test_generates_prefix_variants(self):
        candidates = generate_candidates("stripe")
        handles = [c["handle"] for c in candidates]
        assert "getstripe" in handles
        assert "usestripe" in handles

    def test_platform_specific_youtube(self):
        candidates = generate_candidates("stripe", platform="youtube")
        handles = [c["handle"] for c in candidates]
        assert "stripetv" in handles
        assert "stripechannel" in handles

    def test_respects_max_candidates(self):
        candidates = generate_candidates("stripe", max_candidates=5)
        assert len(candidates) <= 5

    def test_no_duplicates(self):
        candidates = generate_candidates("stripe")
        handles = [c["handle"] for c in candidates]
        assert len(handles) == len(set(handles))

    def test_empty_slug(self):
        assert generate_candidates("") == []


class TestClassifyObservedHandle:
    def test_exact_match(self):
        result = classify_observed_handle("stripe", "stripe")
        assert result["match_type"] == "exact"
        assert result["severity"] == 0.0

    def test_exact_match_with_at(self):
        result = classify_observed_handle("stripe", "@stripe")
        assert result["match_type"] == "exact"

    def test_suffix_modifier_hq(self):
        result = classify_observed_handle("stripe", "stripehq")
        assert result["match_type"] == "suffix_modified"
        assert result["modifier"] == "hq"
        assert result["severity"] > 0

    def test_suffix_modifier_official(self):
        result = classify_observed_handle("tesla", "teslaofficial")
        assert result["match_type"] == "suffix_modified"
        assert result["modifier"] == "official"

    def test_prefix_modifier(self):
        result = classify_observed_handle("stripe", "getstripe")
        assert result["match_type"] == "prefix_modified"
        assert result["modifier"] == "get"

    def test_unrelated_handle(self):
        result = classify_observed_handle("stripe", "paymentshub")
        assert result["match_type"] == "unrelated"
        assert result["severity"] >= 0.8

    def test_contains_brand(self):
        result = classify_observed_handle("stripe", "stripepayments")
        # "payments" is not in our known modifiers, but brand is contained
        assert result["severity"] > 0
