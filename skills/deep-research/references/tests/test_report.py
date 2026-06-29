"""Cited-report assembly tests."""

from research_harness.grading import Source, grade_source
from research_harness.report import (
    Claim,
    Methodology,
    Report,
    Theme,
    build_citations,
    render,
)

REF = 2026


def _graded(url, provider, year, corrob):
    src = Source(title=f"T-{url[-3:]}", url=url, provider=provider, published_year=year)
    return src, grade_source(src, corroboration_count=corrob, reference_year=REF)


def _sample_report():
    graded = [
        _graded("https://doi.org/10.1/aaa", "scholarly-access.paper_resolve", 2026, 2),
        _graded("https://forum.example.test/bbb", "unknown", 2020, 1),
    ]
    citations = build_citations(graded)
    themes = (
        Theme(
            title="Findings",
            claims=(
                Claim(text="Primary corroborated claim", citation_indexes=(1,)),
                Claim(text="Shaky single-source claim", citation_indexes=(2,)),
            ),
        ),
    )
    methodology = Methodology(
        subquestions=("What is X?", "Who leads X?"),
        providers_routed=("firecrawl.firecrawl_search", "scholarly-access.paper_resolve"),
        cache_hits=3,
        cache_misses=5,
        providers_down=("tavily",),
        stale_allowed=False,
    )
    return Report(
        topic="Test Topic",
        generated="2026-06-28",
        summary="A short summary.",
        themes=themes,
        citations=citations,
        methodology=methodology,
        takeaways=("Do the thing",),
    )


def test_build_citations_numbers_sequentially():
    report = _sample_report()
    assert [c.index for c in report.citations] == [1, 2]


def test_render_has_inline_numbered_citations():
    md = render(_sample_report())
    assert "Primary corroborated claim [1]" in md
    assert "Shaky single-source claim [2]" in md


def test_render_includes_provenance_tags():
    md = render(_sample_report())
    assert "[A.corrob x2.2026]" in md
    assert "UNVERIFIED" in md


def test_render_references_section_is_tiered_and_numbered():
    md = render(_sample_report())
    assert "## Sources" in md
    assert "1. [T-aaa](https://doi.org/10.1/aaa) - tier A" in md
    assert "2. [T-bbb](https://forum.example.test/bbb) - tier C" in md


def test_render_methodology_reports_cache_and_downs():
    md = render(_sample_report())
    assert "Cache: 3 hits, 5 misses." in md
    assert "Providers down at preflight: tavily." in md
    assert "What is X?" in md


def test_render_header_confidence_derived_from_grades():
    md = render(_sample_report())
    header = md.splitlines()[1]
    # one High + one Low -> Medium overall
    assert "Confidence: Medium" in header
    assert "Sources: 2" in header


def test_render_handles_empty_citations():
    empty = Report(
        topic="Empty",
        generated="2026-06-28",
        summary="none",
        themes=(),
        citations=(),
        methodology=Methodology(),
    )
    md = render(empty)
    assert "Confidence: Low" in md
    assert "Providers down at preflight: none." in md
