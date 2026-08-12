"""FACT claim decomposition and RACE-style verifier contracts."""

import pytest

from research_harness.claims import (
    Claim,
    EvidenceSpan,
    RaceAssessment,
    audit_claims,
    validate_evidence_span,
)


def test_fact_audit_counts_supported_statement_citation_pairs():
    claims = (
        Claim("Atomic fact one", (1,), claim_id="c1", support="supported"),
        Claim("Atomic fact two", (2,), claim_id="c2", support="partial"),
    )
    audit = audit_claims(claims, valid_citation_indexes={1, 2}, final=False)
    assert audit.checked_pairs == 2
    assert audit.supported_pairs == 1
    assert audit.citation_accuracy == 0.5
    assert audit.effective_citations == 1


def test_fact_audit_rejects_compound_marker_and_unsourced_fact():
    claims = (
        Claim(
            "A happened and B happened",
            (),
            claim_id="c1",
            atomic=False,
            support="unsupported",
        ),
    )
    audit = audit_claims(claims, valid_citation_indexes=set(), final=True)
    assert any("not atomic" in issue for issue in audit.issues)
    assert any("unsourced" in issue for issue in audit.issues)


def test_final_audit_rejects_unsourced_opinion_that_would_render_as_a_claim():
    claim = Claim(
        "The reviewer prefers option A",
        (),
        claim_id="opinion-1",
        kind="opinion",
        support="supported",
    )
    audit = audit_claims((claim,), valid_citation_indexes=set(), final=True)
    assert any("unsourced opinion" in issue for issue in audit.issues)


def test_forecast_requires_probability_and_resolution_criterion():
    claim = Claim(
        "Event X will occur",
        (1,),
        claim_id="f1",
        kind="forecast",
        support="supported",
    )
    audit = audit_claims((claim,), valid_citation_indexes={1}, final=True)
    assert any("probability" in issue for issue in audit.issues)
    assert any("resolution criterion" in issue for issue in audit.issues)


@pytest.mark.parametrize(
    ("span", "message"),
    [
        (
            EvidenceSpan("e", 1, "https://x", "x", "char_location", 5, 5, 0),
            "end must be greater",
        ),
        (
            EvidenceSpan("e", 1, "https://x", "x", "page_location", 0, 2, 0),
            "page locations are 1-based",
        ),
        (
            EvidenceSpan(
                "e", 1, "https://x", "x", "web_search_result_location", 0, 1, 0
            ),
            "does not use numeric bounds",
        ),
    ],
)
def test_citation_location_semantics_are_validated(span, message):
    with pytest.raises(ValueError, match=message):
        validate_evidence_span(span)


def test_search_result_location_uses_its_own_index_not_document_index():
    span = EvidenceSpan(
        evidence_id="e",
        citation_index=1,
        source_url="https://example.com",
        cited_text="one search result content block",
        location_type="search_result_location",
        start=0,
        end=1,
        document_index=None,
        search_result_index=0,
    )
    validate_evidence_span(span)


def test_race_assessment_is_only_full_race_with_reference_and_adaptive_criteria():
    style = RaceAssessment(
        comprehensiveness=0.8,
        insight=0.7,
        instruction_following=0.9,
        readability=0.8,
        task_specific=0.75,
        fresh_context=True,
    )
    assert style.label == "RACE-style"

    full = RaceAssessment(
        comprehensiveness=0.8,
        insight=0.7,
        instruction_following=0.9,
        readability=0.8,
        task_specific=0.75,
        fresh_context=True,
        reference_used=True,
        adaptive_criteria=("criterion-1",),
    )
    assert full.label == "RACE"


def test_race_assessment_requires_fresh_context():
    with pytest.raises(ValueError, match="fresh context"):
        RaceAssessment(
            comprehensiveness=0.8,
            insight=0.7,
            instruction_following=0.9,
            readability=0.8,
            task_specific=0.75,
            fresh_context=False,
        )
