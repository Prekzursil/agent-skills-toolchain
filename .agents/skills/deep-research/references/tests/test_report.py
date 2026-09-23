"""Cited-report assembly tests."""

import pytest

from research_harness.grading import Source, grade_source
from research_harness.report import (
    REPORT_STATUSES,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_PARTIAL_BUDGET,
    STATUS_PARTIAL_LOOP,
    STATUS_PARTIAL_SOURCES,
    STATUS_PARTIAL_TIMEOUT,
    Claim,
    Methodology,
    Report,
    Theme,
    build_citations,
    render,
    status_family,
    summarize_statuses,
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
        providers_routed=(
            "firecrawl.firecrawl_search",
            "scholarly-access.paper_resolve",
        ),
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


# --- Terminal-state taxonomy (Lens 12 find 2) -------------------------------


def test_status_taxonomy_is_closed_and_defaults_to_complete():
    assert REPORT_STATUSES == {
        "complete",
        "partial:budget",
        "partial:sources",
        "partial:timeout",
        "partial:loop",
        "failed",
    }
    report = _sample_report()
    assert report.status == STATUS_COMPLETE
    assert report.open_subquestions == ()


def test_unknown_status_is_rejected():
    with pytest.raises(ValueError, match="unknown report status"):
        Report(
            topic="T",
            generated="2026-06-28",
            summary="s",
            themes=(),
            citations=(),
            methodology=Methodology(),
            status="partial",
        )


def test_complete_report_cannot_carry_open_subquestions():
    with pytest.raises(ValueError, match="open sub-questions"):
        Report(
            topic="T",
            generated="2026-06-28",
            summary="s",
            themes=(),
            citations=(),
            methodology=Methodology(),
            status=STATUS_COMPLETE,
            open_subquestions=("Who leads X?",),
        )


def _partial_report(status, open_subquestions=("Who leads X?",)):
    base = _sample_report()
    return Report(
        topic=base.topic,
        generated=base.generated,
        summary=base.summary,
        themes=base.themes,
        citations=base.citations,
        methodology=base.methodology,
        takeaways=base.takeaways,
        status=status,
        open_subquestions=open_subquestions,
    )


def test_partial_report_still_renders_everything_plus_unanswered_section():
    md = render(_partial_report(STATUS_PARTIAL_BUDGET))
    # The renderer ALWAYS emits the full report ...
    assert "## Executive Summary" in md
    assert "Primary corroborated claim [1]" in md
    assert "## Sources" in md
    # ... plus the terminal state and the open sub-questions.
    assert "Status: partial:budget" in md
    assert "## Unanswered sub-questions" in md
    assert "- Who leads X?" in md
    assert "Terminal state: partial:budget." in md


def test_complete_report_has_no_unanswered_section():
    md = render(_sample_report())
    assert "Status: complete" in md
    assert "## Unanswered sub-questions" not in md
    assert "Terminal state: complete." in md


def test_partial_without_recorded_open_subquestions_says_so():
    md = render(_partial_report(STATUS_PARTIAL_TIMEOUT, open_subquestions=()))
    assert "## Unanswered sub-questions" in md
    assert "none recorded" in md


def test_failed_report_is_still_rendered_with_its_gaps():
    md = render(_partial_report(STATUS_FAILED, ("What is X?", "Who leads X?")))
    assert "Status: failed" in md
    assert "- What is X?" in md
    assert "- Who leads X?" in md


def test_status_family_splits_partial_from_failed():
    assert status_family(STATUS_COMPLETE) == "complete"
    for status in (
        STATUS_PARTIAL_BUDGET,
        STATUS_PARTIAL_SOURCES,
        STATUS_PARTIAL_TIMEOUT,
        STATUS_PARTIAL_LOOP,
    ):
        assert status_family(status) == "partial"
    assert status_family(STATUS_FAILED) == "failed"
    with pytest.raises(ValueError):
        status_family("crashed")


def test_summarize_statuses_counts_partial_apart_from_failed():
    summary = summarize_statuses(
        [
            "complete",
            "partial:budget",
            "partial:budget",
            "partial:loop",
            "failed",
            "complete",
        ]
    )
    assert summary.total == 6
    assert summary.complete == 2
    assert summary.partial == 3
    assert summary.failed == 1
    assert summary.partial_by_kind == {"partial:budget": 2, "partial:loop": 1}
    # Success rate counts partial separately: 2 complete + 3 partial of 6.
    assert summary.complete_rate == pytest.approx(2 / 6)
    assert summary.delivered_rate == pytest.approx(5 / 6)
    assert "partial=3" in summary.line
    assert "failed=1" in summary.line


def test_summarize_statuses_handles_empty_input():
    summary = summarize_statuses([])
    assert summary.total == 0
    assert summary.complete_rate == 0.0
    assert summary.delivered_rate == 0.0


# --- Disputed callouts (Lens 12 find 9) --------------------------------------


def test_render_emits_disputed_callouts_as_their_own_section():
    base = _sample_report()
    callout = (
        "**Disputed:** Energy density reached 500 Wh/kg - sources disagree: "
        "500 wh/kg [1] `[A.corrob x2.2026]`; 400 wh/kg [2] `[C.single.2020 - UNVERIFIED]` "
        "(preferred: [1], by tier then recency)."
    )
    report = Report(
        topic=base.topic,
        generated=base.generated,
        summary=base.summary,
        themes=base.themes,
        citations=base.citations,
        methodology=base.methodology,
        disputes=(callout,),
    )
    md = render(report)
    assert "## Disputed claims" in md
    assert f"> {callout}" in md
    # A dispute is honest disagreement, not a failed run: the status stays complete.
    assert report.status == STATUS_COMPLETE
    assert "## Unanswered sub-questions" not in md
    # The section sits after the findings and before the sources.
    assert (
        md.index("## 1. Findings")
        < md.index("## Disputed claims")
        < md.index("## Sources")
    )


def test_report_without_disputes_has_no_disputed_section():
    md = render(_sample_report())
    assert "## Disputed claims" not in md
    assert "Disputed:" not in md
