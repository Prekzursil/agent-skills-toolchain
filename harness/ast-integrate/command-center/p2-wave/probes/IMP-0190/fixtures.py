"""Shared both-states fixtures for IMP-0190 probes and the receipt emitter.

All numbers are chosen so stage counts and metric values are distinct, so a
gate that secretly used len(stages) as accuracy would fail these cases.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]  # file → IMP-0190 → probes → p2-wave → command-center → repo
_CC = _REPO / "command-center"
if str(_CC) not in sys.path:
    sys.path.insert(0, str(_CC))

from fusion.admission_gate import FusionCandidate, WorkflowRecord  # noqa: E402

METRIC = "matched_case_accuracy"

SOURCE_A = WorkflowRecord(
    workflow_id="wf.parse-rank",
    stages=("ingest", "parse", "rank"),
    capabilities=frozenset({"parse", "rank"}),
    metric_name=METRIC,
    metric_value=0.80,
    budget=100.0,
)

SOURCE_B = WorkflowRecord(
    workflow_id="wf.parse-fetch",
    stages=("ingest", "parse", "fetch", "normalize"),
    capabilities=frozenset({"parse", "fetch"}),
    metric_name=METRIC,
    metric_value=0.78,
    budget=100.0,
)

SOURCES = (SOURCE_A, SOURCE_B)

# Union of source capabilities. No novel bit.
UNION_CAPS = frozenset({"parse", "rank", "fetch"})
NEW_CAP = "cross_source_license_solver"

# Concatenation plus padding stages: strictly larger than either source.
PADDED_STAGES = (
    "ingest",
    "parse",
    "rank",
    "fetch",
    "normalize",
    "pad_a",
    "pad_b",
    "pad_c",
)


def bigger_not_better() -> FusionCandidate:
    """More stages than either source, metric below the best source, no new cap."""
    return FusionCandidate(
        fusion_id="fusion.bigger-not-better",
        sources=SOURCES,
        stages=PADDED_STAGES,
        capabilities=UNION_CAPS,
        metric_name=METRIC,
        metric_value=0.79,  # 0.78 < 0.79 < 0.80: not better than every source
        budget=100.0,
        prose_claim="merged workflow is better because it contains more stages",
    )


def better_on_metric() -> FusionCandidate:
    """Same padded size, strictly better accuracy than every source. No new cap."""
    return FusionCandidate(
        fusion_id="fusion.outperform-accuracy",
        sources=SOURCES,
        stages=PADDED_STAGES,
        capabilities=UNION_CAPS,
        metric_name=METRIC,
        metric_value=0.91,
        budget=100.0,
        prose_claim="",
    )


def complementary() -> FusionCandidate:
    """Not better on the metric; capability vector carries a named new bit."""
    return FusionCandidate(
        fusion_id="fusion.complement-license-solver",
        sources=SOURCES,
        stages=PADDED_STAGES,
        capabilities=UNION_CAPS | {NEW_CAP},
        metric_name=METRIC,
        metric_value=0.79,
        budget=100.0,
        prose_claim="",
    )


def prose_only_complement() -> FusionCandidate:
    """Prose claims novelty; capability vector is exactly the source union."""
    return FusionCandidate(
        fusion_id="fusion.prose-only-complement",
        sources=SOURCES,
        stages=PADDED_STAGES,
        capabilities=UNION_CAPS,
        metric_name=METRIC,
        metric_value=0.79,
        budget=100.0,
        prose_claim="adds a unique license-solver capability none of the sources has",
    )


def stage_count_as_metric() -> FusionCandidate:
    """Vanity metric: declare stage_count as the superiority number."""
    return FusionCandidate(
        fusion_id="fusion.stage-count-metric",
        sources=SOURCES,
        stages=PADDED_STAGES,
        capabilities=UNION_CAPS,
        metric_name="stage_count",
        metric_value=float(len(PADDED_STAGES)),
        budget=100.0,
        prose_claim="wins because 8 > 4 stages",
    )


def prose_swap(candidate: FusionCandidate, claim: str) -> FusionCandidate:
    return replace(candidate, prose_claim=claim)


def independent_capability_delta(candidate: FusionCandidate) -> tuple[str, ...]:
    """Probe-local set difference. Must not call admission_gate.capability_delta."""
    union: set[str] = set()
    for src in candidate.sources:
        union |= set(src.capabilities)
    return tuple(sorted(set(candidate.capabilities) - union))
