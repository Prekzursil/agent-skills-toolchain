"""FACT claim/evidence contracts and a bounded RACE-style scorecard.

The model performs linguistic decomposition and entailment review; this module
validates the returned structure.  A native Anthropic citation proves that a
span came from a supplied source, but it does *not* prove that the span entails
the report claim.  ``support`` therefore remains an explicit verifier verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CLAIM_KINDS = frozenset({"fact", "inference", "forecast", "opinion"})
# ``contradicted`` (Lens 12 find 9): the cited sources assert *different* values
# for the claim. Checked (it went through the verifier) but not supported, and
# not an audit issue on its own - the report carries a "Disputed" callout
# (``conflicts.Dispute.callout``) showing both values instead of picking one.
CONTRADICTED = "contradicted"
SUPPORT_VERDICTS = frozenset(
    {"supported", "partial", "unsupported", "unchecked", CONTRADICTED}
)

LOCATION_TYPES = frozenset(
    {
        "char_location",
        "page_location",
        "content_block_location",
        "search_result_location",
        "web_search_result_location",
        "fallback_span",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceSpan:
    """Statement-to-source evidence, native citation metadata when available."""

    evidence_id: str
    citation_index: int
    source_url: str
    cited_text: str
    location_type: str
    start: int | None = None
    end: int | None = None
    document_index: int | None = None
    search_result_index: int | None = None


def validate_evidence_span(span: EvidenceSpan) -> None:
    if span.location_type not in LOCATION_TYPES:
        raise ValueError(f"unknown citation location type: {span.location_type}")
    if span.citation_index < 1:
        raise ValueError("citation_index must be 1-based and positive")
    if not span.source_url:
        raise ValueError("source_url is required")
    if not span.cited_text:
        raise ValueError("cited_text is required")

    if span.location_type == "web_search_result_location":
        if span.start is not None or span.end is not None:
            raise ValueError("web_search_result_location does not use numeric bounds")
        return

    if span.location_type == "page_location":
        if span.start is None or span.end is None or span.start < 1:
            raise ValueError("page locations are 1-based")
        if span.end <= span.start:
            raise ValueError("citation end must be greater than start")
    elif span.location_type in {
        "char_location",
        "content_block_location",
        "search_result_location",
        "fallback_span",
    }:
        if span.start is None or span.end is None or span.start < 0:
            raise ValueError("citation bounds are 0-based and non-negative")
        if span.end <= span.start:
            raise ValueError("citation end must be greater than start")

    if span.location_type in {
        "char_location",
        "page_location",
        "content_block_location",
    }:
        if span.document_index is None or span.document_index < 0:
            raise ValueError("document_index must be 0-based")
    if span.location_type == "search_result_location":
        if span.search_result_index is None or span.search_result_index < 0:
            raise ValueError("search_result_index must be 0-based")


@dataclass(frozen=True, slots=True)
class Claim:
    """One atomic report claim and its FACT support verdict."""

    text: str
    citation_indexes: tuple[int, ...]
    claim_id: str = ""
    kind: str = "fact"
    support: str = "supported"
    atomic: bool = True
    evidence: tuple[EvidenceSpan, ...] = field(default_factory=tuple)
    follow_up_query: str | None = None
    probability: float | None = None
    resolution_criterion: str | None = None


@dataclass(frozen=True, slots=True)
class ClaimAudit:
    issues: tuple[str, ...]
    checked_pairs: int
    supported_pairs: int
    effective_citations: int
    citation_accuracy: float | None
    follow_up_queries: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def _claim_label(claim: Claim, position: int) -> str:
    return claim.claim_id or f"claim-{position}"


def audit_claims(
    claims: tuple[Claim, ...],
    *,
    valid_citation_indexes: set[int],
    final: bool = True,
) -> ClaimAudit:
    """Validate atomic claims and compute FACT-style citation metrics."""
    issues: list[str] = []
    checked_pairs = 0
    supported_pairs = 0
    effective: set[tuple[str, int]] = set()
    follow_ups: list[str] = []

    for position, claim in enumerate(claims, start=1):
        label = _claim_label(claim, position)
        if not claim.text.strip():
            issues.append(f"{label}: empty claim")
        if not claim.atomic:
            issues.append(f"{label}: claim is not atomic")
        if claim.kind not in CLAIM_KINDS:
            issues.append(f"{label}: unknown claim kind {claim.kind!r}")
        if claim.support not in SUPPORT_VERDICTS:
            issues.append(f"{label}: unknown support verdict {claim.support!r}")

        if not claim.citation_indexes and (final or claim.kind != "opinion"):
            issues.append(f"{label}: unsourced {claim.kind} claim")
        for citation_index in claim.citation_indexes:
            if citation_index not in valid_citation_indexes:
                issues.append(f"{label}: unknown citation index {citation_index}")

        if final and claim.support in {"unsupported", "unchecked"}:
            issues.append(f"{label}: support is {claim.support}")

        if claim.kind == "forecast":
            if claim.probability is None:
                issues.append(f"{label}: forecast probability is required")
            elif not 0.0 <= claim.probability <= 1.0:
                issues.append(f"{label}: forecast probability must be within [0, 1]")
            if not claim.resolution_criterion:
                issues.append(f"{label}: forecast resolution criterion is required")

        for span in claim.evidence:
            try:
                validate_evidence_span(span)
            except ValueError as exc:
                issues.append(f"{label}: {exc}")
            if span.citation_index not in claim.citation_indexes:
                issues.append(
                    f"{label}: evidence {span.evidence_id} points outside claim citations"
                )

        # FACT-style statement/citation pairs.  Partial and unsupported pairs
        # are checked but not counted as accurate/effective.
        if claim.support != "unchecked":
            checked_pairs += len(claim.citation_indexes)
        if claim.support == "supported":
            supported_pairs += len(claim.citation_indexes)
            normalized = " ".join(claim.text.lower().split())
            for citation_index in claim.citation_indexes:
                effective.add((normalized, citation_index))
        if claim.support != "supported" and claim.follow_up_query:
            follow_ups.append(claim.follow_up_query)

    accuracy = supported_pairs / checked_pairs if checked_pairs else None
    return ClaimAudit(
        issues=tuple(issues),
        checked_pairs=checked_pairs,
        supported_pairs=supported_pairs,
        effective_citations=len(effective),
        citation_accuracy=accuracy,
        follow_up_queries=tuple(dict.fromkeys(follow_ups)),
    )


@dataclass(frozen=True, slots=True)
class RaceAssessment:
    """Fresh-context report rubric; full RACE only with reference + criteria."""

    comprehensiveness: float
    insight: float
    instruction_following: float
    readability: float
    task_specific: float
    fresh_context: bool
    reference_used: bool = False
    adaptive_criteria: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.fresh_context:
            raise ValueError("RACE-style assessment requires a fresh context")
        scores = (
            self.comprehensiveness,
            self.insight,
            self.instruction_following,
            self.readability,
            self.task_specific,
        )
        if any(not 0.0 <= score <= 1.0 for score in scores):
            raise ValueError("RACE-style scores must be within [0, 1]")

    @property
    def label(self) -> str:
        if self.reference_used and self.adaptive_criteria:
            return "RACE"
        return "RACE-style"

    @property
    def overall(self) -> float:
        scores = (
            self.comprehensiveness,
            self.insight,
            self.instruction_following,
            self.readability,
            self.task_specific,
        )
        return sum(scores) / len(scores)
