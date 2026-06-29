"""Source-confidence grading tests (deterministic, no network)."""

from research_harness.grading import (
    Source,
    grade_source,
    overall_confidence,
    source_tier,
)

REF = 2026


def _src(url, provider, year=None, title="t"):
    return Source(title=title, url=url, provider=provider, published_year=year)


def test_domain_authority_sets_tier_a():
    assert source_tier(_src("https://www.ncbi.nlm.nih.gov/x", "exa.web_search_exa")) == "A"
    assert source_tier(_src("https://doi.org/10.1/x", "tavily.tavily_search")) == "A"


def test_provider_prior_can_lift_to_a():
    # community-looking domain but authoritative provider -> A
    assert source_tier(_src("https://example.org/p", "scholarly-access.paper_resolve")) == "A"


def test_secondary_and_community_tiers():
    assert source_tier(_src("https://github.com/o/r", "exa.web_search_exa")) == "B"
    assert source_tier(_src("https://random-blog.xyz/post", "exa.web_search_exa")) == "B"
    # bare community domain + community provider -> C
    assert source_tier(_src("https://forum.example.test/t", "unknown")) == "C"


def test_high_confidence_primary_corroborated_recent():
    g = grade_source(
        _src("https://doi.org/10.1/x", "scholarly-access.paper_resolve", 2026),
        corroboration_count=2,
        reference_year=REF,
    )
    assert g.tier == "A"
    assert g.confidence == "High"
    assert g.unverified is False
    assert g.provenance == "[A.corrob x2.2026]"


def test_low_confidence_community_single_old():
    g = grade_source(
        _src("https://forum.example.test/t", "unknown", 2024),
        corroboration_count=1,
        reference_year=REF,
    )
    assert g.tier == "C"
    assert g.confidence == "Low"
    assert g.unverified is True
    assert g.provenance == "[C.single.2024 - UNVERIFIED]"


def test_medium_confidence_secondary_recent_single():
    g = grade_source(
        _src("https://github.com/o/r", "exa.web_search_exa", 2026),
        corroboration_count=1,
        reference_year=REF,
    )
    assert g.tier == "B"
    assert g.confidence == "Medium"
    assert g.unverified is True


def test_undated_source_uses_nd_label():
    g = grade_source(
        _src("https://github.com/o/r", "exa.web_search_exa", None),
        corroboration_count=2,
        reference_year=REF,
    )
    assert "n.d." in g.provenance
    assert g.recent is False


def test_overall_confidence_from_distribution():
    high = grade_source(
        _src("https://doi.org/1", "scholarly-access.paper_resolve", 2026),
        corroboration_count=2,
        reference_year=REF,
    )
    low = grade_source(
        _src("https://forum.test/t", "unknown", 2020),
        corroboration_count=1,
        reference_year=REF,
    )
    assert overall_confidence([high, high, low]) == "High"
    assert overall_confidence([low, low, high]) == "Low"
    assert overall_confidence([high, low]) == "Medium"
    assert overall_confidence([]) == "Low"
