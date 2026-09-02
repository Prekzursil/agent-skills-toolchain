"""Council cost estimate, calibration, and owner-ceiling gate (IMP-0352)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

GATE_REFUSE_ALLOWED = False  # IMP-0352-GATE-REFUSE

REASON_CEILING_BREACH = "ceiling-breach"
REASON_GATE_ABSENT = "gate-absent"
REASON_OWNER_WAIVER = "owner-waiver"
REASON_UNDER_CEILING = "under-ceiling"


@dataclass
class Cost:
    tokens: int
    wall_clock_seconds: float
    external_calls: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "tokens": int(self.tokens),
            "wall_clock_seconds": float(self.wall_clock_seconds),
            "external_calls": int(self.external_calls),
        }


@dataclass
class CouncilPlan:
    council_id: str
    seats: tuple[str, ...]
    rounds: int
    tokens_per_seat_turn: int
    tool_calls_per_seat_turn: float
    think_seconds_per_seat_turn: float

    @classmethod
    def from_mapping(cls, spec: dict[str, Any]) -> "CouncilPlan":
        seats = tuple(str(s) for s in (spec.get("seats") or spec.get("participants") or []))
        if seats and isinstance(seats[0], dict):
            seats = tuple(str(s.get("id") or i) for i, s in enumerate(spec.get("participants") or []))
        return cls(
            council_id=str(spec.get("id") or spec.get("council_id") or "plan"),
            seats=seats or ("a", "b"),
            rounds=int(spec.get("rounds") or 1),
            tokens_per_seat_turn=int(spec.get("tokens_per_seat_turn") or 100),
            tool_calls_per_seat_turn=float(spec.get("tool_calls_per_seat_turn") or 0.0),
            think_seconds_per_seat_turn=float(spec.get("think_seconds_per_seat_turn") or 1.0),
        )


@dataclass
class OwnerCeiling:
    tokens: int
    wall_clock_seconds: float
    external_calls: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "tokens": int(self.tokens),
            "wall_clock_seconds": float(self.wall_clock_seconds),
            "external_calls": int(self.external_calls),
        }


@dataclass
class OwnerApproval:
    granted: bool
    approver_id: str
    ticket: str
    dimensions: tuple[str, ...] = ()


@dataclass
class DimCal:
    n: int
    ratios: list[float]
    exceed_count: int
    exceed_rate: float
    p90_overrun_ratio: float


@dataclass
class CalReport:
    n: int
    rows: list[dict[str, Any]]
    by_dimension: dict[str, DimCal]
    combined_p90_overrun_ratio: float
    combined_exceed_rate: float


@dataclass
class PreflightResult:
    allowed: bool
    launched: bool
    reason: str
    breaches: list[str] = field(default_factory=list)
    estimate: dict[str, Any] = field(default_factory=dict)


def estimate_cost(plan: CouncilPlan) -> Cost:
    n = max(1, len(plan.seats)) * max(1, int(plan.rounds))
    tokens = int(n * int(plan.tokens_per_seat_turn))
    wall = float(n) * float(plan.think_seconds_per_seat_turn)
    calls = int(round(float(n) * float(plan.tool_calls_per_seat_turn)))
    return Cost(tokens=tokens, wall_clock_seconds=wall, external_calls=calls)


def nearest_rank_percentile(values: Sequence[float], p: float = 0.90) -> float:
    xs = sorted(float(v) for v in values)
    if not xs:
        return 0.0
    rank = max(1, min(len(xs), math.ceil(p * len(xs))))
    return xs[rank - 1]


def calibrate(records: Iterable[dict[str, Any]]) -> CalReport:
    rows: list[dict[str, Any]] = []
    dims = ("tokens", "wall_clock_seconds", "external_calls")
    dim_ratios: dict[str, list[float]] = {d: [] for d in dims}
    combined: list[float] = []
    exceed_any = 0
    recs = list(records)
    for rec in recs:
        plan = rec["plan"]
        actual: Cost = rec["actual"]
        est = estimate_cost(plan)
        est_d = est.as_dict()
        act_d = actual.as_dict()
        overrun = {}
        exceeded = []
        for dim in dims:
            e = float(est_d[dim]) if est_d[dim] else 1.0
            a = float(act_d[dim])
            ratio = a / e
            overrun[dim] = ratio
            dim_ratios[dim].append(ratio)
            if a > float(est_d[dim]):
                exceeded.append(dim)
        if exceeded:
            exceed_any += 1
        combined.append(max(overrun.values()))
        rows.append(
            {
                "id": rec.get("id") or getattr(plan, "council_id", ""),
                "estimate": est_d,
                "actual": act_d,
                "overrun_ratio": overrun,
                "exceeded_dimensions": exceeded,
            }
        )
    by: dict[str, DimCal] = {}
    n = len(recs)
    for dim in dims:
        ratios = dim_ratios[dim]
        exceed_count = sum(1 for r in rows if dim in r["exceeded_dimensions"])
        by[dim] = DimCal(
            n=n,
            ratios=ratios,
            exceed_count=exceed_count,
            exceed_rate=(exceed_count / n) if n else 0.0,
            p90_overrun_ratio=nearest_rank_percentile(ratios, 0.90),
        )
    return CalReport(
        n=n,
        rows=rows,
        by_dimension=by,
        combined_p90_overrun_ratio=nearest_rank_percentile(combined, 0.90) if combined else 0.0,
        combined_exceed_rate=(exceed_any / n) if n else 0.0,
    )


def preflight(
    plan: CouncilPlan,
    ceiling: OwnerCeiling,
    approval: OwnerApproval | None = None,
    *,
    apply_gate: bool = True,
) -> PreflightResult:
    est = estimate_cost(plan)
    breaches: list[str] = []
    if est.tokens > int(ceiling.tokens):
        breaches.append("tokens")
    if est.wall_clock_seconds > float(ceiling.wall_clock_seconds):
        breaches.append("wall_clock_seconds")
    if est.external_calls > int(ceiling.external_calls):
        breaches.append("external_calls")
    if not breaches:
        return PreflightResult(
            allowed=True,
            launched=True,
            reason=REASON_UNDER_CEILING,
            breaches=[],
            estimate=est.as_dict(),
        )
    if not apply_gate:
        return PreflightResult(
            allowed=True,
            launched=True,
            reason=REASON_GATE_ABSENT,
            breaches=breaches,
            estimate=est.as_dict(),
        )
    if GATE_REFUSE_ALLOWED:
        return PreflightResult(
            allowed=True,
            launched=True,
            reason=REASON_GATE_ABSENT,
            breaches=breaches,
            estimate=est.as_dict(),
        )
    if (
        approval is not None
        and approval.granted
        and approval.approver_id.startswith("owner-")
        and set(approval.dimensions) >= {"tokens", "wall_clock_seconds", "external_calls"}
    ):
        return PreflightResult(
            allowed=True,
            launched=True,
            reason=REASON_OWNER_WAIVER,
            breaches=breaches,
            estimate=est.as_dict(),
        )
    return PreflightResult(
        allowed=False,
        launched=False,
        reason=REASON_CEILING_BREACH,
        breaches=breaches,
        estimate=est.as_dict(),
    )
