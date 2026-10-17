import pytest
from Core.ai_engine import (
    normalize_verdict,
    clamp_confidence,
    extract_domain,
    is_credible_source_url,
    extract_key_claims,
    has_high_risk_terms,
    has_causal_claim
)


class TestVerdictNormalization:
    def test_canonical_verdicts(self):
        assert normalize_verdict("SUPPORTED") == "SUPPORTED"
        assert normalize_verdict("REFUTED") == "REFUTED"
        assert normalize_verdict("MISLEADING") == "MISLEADING"
        assert normalize_verdict("LOW CREDIBILITY") == "LOW CREDIBILITY"
        assert normalize_verdict("INSUFFICIENT EVIDENCE") == "INSUFFICIENT EVIDENCE"

    def test_alias_mapping(self):
        assert normalize_verdict("REAL") == "SUPPORTED"
        assert normalize_verdict("TRUE") == "SUPPORTED"
        assert normalize_verdict("FAKE") == "REFUTED"
        assert normalize_verdict("FALSE") == "REFUTED"
        assert normalize_verdict("DEBUNKED") == "REFUTED"
        assert normalize_verdict("UNKNOWN") == "INSUFFICIENT EVIDENCE"
        assert normalize_verdict("SUSPICIOUS") == "LOW CREDIBILITY"

    def test_unexpected_verdict_defaults_to_insufficient(self):
        assert normalize_verdict("BANANA") == "INSUFFICIENT EVIDENCE"
        assert normalize_verdict(None) == "INSUFFICIENT EVIDENCE"


class TestConfidenceClamping:
    def test_in_range_values(self):
        assert clamp_confidence(75) == 75
        assert clamp_confidence("82") == 82

    def test_out_of_bounds(self):
        assert clamp_confidence(150) == 100
        assert clamp_confidence(-10) == 0

    def test_invalid_type_uses_default(self):
        assert clamp_confidence("not-a-number", default=50) == 50


class TestDomainAndSourceChecking:
    def test_extract_domain(self):
        assert extract_domain("https://www.reuters.com/world/news") == "www.reuters.com"
        assert extract_domain("http://bbc.co.uk/news") == "bbc.co.uk"
        assert extract_domain("") == ""

    def test_credible_source_url(self):
        assert is_credible_source_url("https://www.reuters.com/article/123") is True
        assert is_credible_source_url("https://bbc.com/sport") is True
        assert is_credible_source_url("https://random-blog-1234.net/post") is False


class TestClaimSignals:
    def test_causal_claim_detection(self):
        assert has_causal_claim("Player dropped because of poor performance") is True
        assert has_causal_claim("Stock market fell due to interest rate hikes") is True
        assert has_causal_claim("The President visited France today") is False

    def test_high_risk_claim_detection(self):
        assert has_high_risk_terms("Prime Minister assassinated in sudden attack") is True
        assert has_high_risk_terms("New miracle cure eliminates virus instantly") is True
        assert has_high_risk_terms("Local football team wins championship") is False

    def test_extract_key_claims(self):
        text = "Virat Kohli scored 100 runs in the World Cup match in 2023."
        claims = extract_key_claims(text)
        assert "2023" in claims["years"]
        assert len(claims["names"]) > 0
