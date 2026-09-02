"""Fusion admission gate: outperform-or-complement, never bigger-not-better."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

ADMIT_OUTPERFORM = "ADMIT_OUTPERFORM"
ADMIT_COMPLEMENT = "ADMIT_COMPLEMENT"
REJECT_BIGGER_NOT_BETTER = "REJECT_BIGGER_NOT_BETTER"
REJECT_FORBIDDEN_METRIC = "REJECT_FORBIDDEN_METRIC"
FORBIDDEN_METRICS = frozenset({"stage_count", "stage-count", "n_stages"})


@dataclass(frozen=True)
class WorkflowRecord:
    workflow_id: str
    stages: tuple[str, ...]
    capabilities: frozenset[str]
    metric_name: str
    metric_value: float
    budget: float = 0.0


@dataclass(frozen=True)
class FusionCandidate:
    fusion_id: str
    sources: tuple[WorkflowRecord, ...]
    stages: tuple[str, ...]
    capabilities: frozenset[str]
    metric_name: str
    metric_value: float
    budget: float = 0.0
    prose_claim: str = ""


@dataclass
class Decision:
    admitted: bool
    reason: str
    fusion_id: str
    outperform: bool = False
    complement: bool = False
    fusion_stage_count: int = 0
    source_stage_counts: list[tuple[str, int]] = field(default_factory=list)
    named_new_capabilities: tuple[str, ...] = ()
    capability_vector_delta: tuple[str, ...] = ()
    stage_count_used_as_criterion: bool = False
    prose_consulted: bool = False

    def to_dict(self) -> dict:
        return {
            "admitted": self.admitted,
            "reason": self.reason,
            "fusion_id": self.fusion_id,
            "outperform": self.outperform,
            "complement": self.complement,
            "fusion_stage_count": self.fusion_stage_count,
            "source_stage_counts": [list(x) for x in self.source_stage_counts],
            "named_new_capabilities": list(self.named_new_capabilities),
            "capability_vector_delta": list(self.capability_vector_delta),
            "stage_count_used_as_criterion": self.stage_count_used_as_criterion,
            "prose_consulted": self.prose_consulted,
        }


def _union_caps(sources: Iterable[WorkflowRecord]) -> set[str]:
    union: set[str] = set()
    for src in sources:
        union |= set(src.capabilities)
    return union


def _capability_delta(candidate: FusionCandidate) -> tuple[str, ...]:
    union = _union_caps(candidate.sources)
    return tuple(sorted(set(candidate.capabilities) - union))


def evaluate(candidate: FusionCandidate) -> Decision:
    sources = tuple(candidate.sources)
    source_counts = [(s.workflow_id, len(s.stages)) for s in sources]
    delta = _capability_delta(candidate)
    fusion_n = len(candidate.stages)
    metric = str(candidate.metric_name or "")
    if metric.lower().replace("-", "_") in FORBIDDEN_METRICS:
        return Decision(
            admitted=False,
            reason=REJECT_FORBIDDEN_METRIC,
            fusion_id=candidate.fusion_id,
            fusion_stage_count=fusion_n,
            source_stage_counts=source_counts,
        )
    source_metrics = [float(s.metric_value) for s in sources] or [0.0]
    outperform = float(candidate.metric_value) > max(source_metrics)
    complement = bool(delta)
    if outperform:
        return Decision(
            admitted=True,
            reason=ADMIT_OUTPERFORM,
            fusion_id=candidate.fusion_id,
            outperform=True,
            fusion_stage_count=fusion_n,
            source_stage_counts=source_counts,
            named_new_capabilities=delta if complement else (),
            capability_vector_delta=delta if complement else (),
        )
    if complement:
        return Decision(
            admitted=True,
            reason=ADMIT_COMPLEMENT,
            fusion_id=candidate.fusion_id,
            complement=True,
            fusion_stage_count=fusion_n,
            source_stage_counts=source_counts,
            named_new_capabilities=delta,
            capability_vector_delta=delta,
        )
    return Decision(
        admitted=False,
        reason=REJECT_BIGGER_NOT_BETTER,
        fusion_id=candidate.fusion_id,
        fusion_stage_count=fusion_n,
        source_stage_counts=source_counts,
    )


def decision_fingerprint(decision: Decision) -> tuple:
    return (
        decision.admitted,
        decision.reason,
        decision.outperform,
        decision.complement,
        decision.fusion_stage_count,
        tuple(decision.source_stage_counts),
        decision.named_new_capabilities,
        decision.capability_vector_delta,
        decision.stage_count_used_as_criterion,
        decision.prose_consulted,
    )


class FusionLibrary:
    def __init__(self) -> None:
        self._admitted: dict[str, Decision] = {}

    def try_admit(self, candidate: FusionCandidate) -> Decision:
        decision = evaluate(candidate)
        if decision.admitted:
            self._admitted[candidate.fusion_id] = decision
        return decision

    def contains(self, fusion_id: str) -> bool:
        return fusion_id in self._admitted

    def admitted_ids(self) -> list[str]:
        return list(self._admitted.keys())
