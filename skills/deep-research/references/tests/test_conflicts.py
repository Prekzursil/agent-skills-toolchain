"""Contradiction detection tests (Lens 12 find 9): `contradicted` verdict + Disputed callout."""

from research_harness.claims import SUPPORT_VERDICTS, Claim, EvidenceSpan, audit_claims
from research_harness.conflicts import (
    CONTRADICTED,
    Dispute,
    DisputedValue,
    detect_conflict,
    extract_values,
    resolve_claims,
)
from research_harness.grading import Source, grade_source

REF = 2026


def _span(idx, text):
    return EvidenceSpan(
        evidence_id=f"e{idx}",
        citation_index=idx,
        source_url=f"https://s{idx}.example/",
        cited_text=text,
        location_type="fallback_span",
        start=0,
        end=len(text),
    )


def _grade(url, provider, year, corrob=1):
    return grade_source(
        Source("t", url, provider, year), corroboration_count=corrob, reference_year=REF
    )


GRADES = {
    1: _grade("https://doi.org/10.1/a", "scholarly-access", 2026, 2),  # A, recent
    2: _grade("https://forum.example/b", "unknown", 2020),  # C, stale
    3: _grade("https://en.wikipedia.org/c", "exa", 2026),  # B, recent
}


def test_contradicted_is_a_valid_support_verdict():
    assert CONTRADICTED == "contradicted"
    assert CONTRADICTED in SUPPORT_VERDICTS


def test_extract_values_normalizes_numbers_units_percents_dates_and_years():
    assert extract_values("reached 500 Wh/kg in 2026") == ("500 wh/kg", "2026")
    assert extract_values("1,200 employees, up 12.50%") == ("1200 employees", "12.5 %")
    assert extract_values("$500 million raised") == ("500 $ million",)
    assert extract_values("grew to 3 in the year") == ("3",)  # stopword is not a unit
    assert extract_values("on January 15, 2026 and again 2026-03-01") == (
        "2026-01-15",
        "2026-03-01",
    )
    assert extract_values("15 Jan 2026") == ("2026-01-15",)
    assert extract_values("no numbers here") == ()


def test_extract_values_keeps_first_seen_order_and_dedups():
    assert extract_values("500 Wh/kg then 500 Wh/kg then 400 Wh/kg") == (
        "500 wh/kg",
        "400 wh/kg",
    )


def test_agreeing_spans_are_not_a_conflict():
    claim = Claim(
        "Energy density reached 500 Wh/kg",
        (1, 3),
        evidence=(
            _span(1, "the cell hit 500 Wh/kg"),
            _span(3, "500 Wh/kg was reported"),
        ),
    )
    assert detect_conflict(claim, GRADES) is None


def test_distinct_values_produce_a_dispute_preferring_tier_then_recency():
    claim = Claim(
        "Energy density reached 500 Wh/kg",
        (1, 2),
        evidence=(
            _span(1, "the cell hit 500 Wh/kg"),
            _span(2, "only 400 Wh/kg was achieved"),
        ),
    )
    dispute = detect_conflict(claim, GRADES)
    assert isinstance(dispute, Dispute)
    assert dispute.claim_text == claim.text
    assert dispute.values == (
        DisputedValue("500 wh/kg", 1, "A", "[A.corrob x2.2026]"),
        DisputedValue("400 wh/kg", 2, "C", "[C.single.2020 - UNVERIFIED]"),
    )
    assert dispute.preferred_index == 1
    callout = dispute.callout
    assert callout.startswith("**Disputed:** Energy density reached 500 Wh/kg")
    assert "500 wh/kg [1] `[A.corrob x2.2026]`" in callout
    assert "400 wh/kg [2] `[C.single.2020 - UNVERIFIED]`" in callout
    assert "preferred: [1]" in callout


def test_recency_breaks_a_tier_tie():
    grades = {
        1: _grade("https://doi.org/10.1/a", "scholarly-access", 2019),  # A, stale
        2: _grade("https://doi.org/10.1/b", "scholarly-access", 2026),  # A, recent
    }
    claim = Claim("X is N", (1, 2), evidence=(_span(1, "N is 10"), _span(2, "N is 12")))
    assert detect_conflict(claim, grades).preferred_index == 2


def test_spans_without_values_or_a_single_span_never_conflict():
    claim = Claim(
        "X", (1, 2), evidence=(_span(1, "no numbers"), _span(2, "none either"))
    )
    assert detect_conflict(claim, GRADES) is None
    lone = Claim("X", (1,), evidence=(_span(1, "500 Wh/kg"),))
    assert detect_conflict(lone, GRADES) is None


def test_resolve_claims_marks_contradicted_and_collects_disputes():
    disputed = Claim(
        "Energy density reached 500 Wh/kg",
        (1, 2),
        claim_id="c1",
        evidence=(_span(1, "500 Wh/kg"), _span(2, "400 Wh/kg")),
    )
    fine = Claim(
        "Founded in 2019", (3,), claim_id="c2", evidence=(_span(3, "founded 2019"),)
    )
    claims, disputes = resolve_claims((disputed, fine), GRADES)
    assert claims[0].support == CONTRADICTED
    assert claims[0].claim_id == "c1" and claims[0].evidence == disputed.evidence
    assert claims[1].support == "supported"
    assert len(disputes) == 1 and disputes[0].claim_text == disputed.text


def test_audit_treats_contradicted_as_checked_but_not_supported_and_not_an_issue():
    claims = (
        Claim("A", (1, 2), claim_id="c1", support=CONTRADICTED),
        Claim("B", (3,), claim_id="c2", support="supported"),
    )
    audit = audit_claims(claims, valid_citation_indexes={1, 2, 3}, final=True)
    assert audit.ok, audit.issues
    assert audit.checked_pairs == 3
    assert audit.supported_pairs == 1
