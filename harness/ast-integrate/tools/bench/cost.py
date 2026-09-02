"""Per-run cost accounting so improvement is reported per unit cost (TST-0304).

Every benchmark run records tokens in and out, wall-clock, tool calls and an estimated
spend derived from a published rate card.  Rows missing any cost field are rejected, never
defaulted; a recorded spend that disagrees with the rate card is a forgery and is
rejected; recorded tokens are reconciled against the vendor's usage report for the same
run and the delta is always reported (strict ingest refuses a non-zero delta).

Quality deltas are always published next to their cost deltas: a candidate that is 2 %
better for 6x the tokens is a different decision from one that is 2 % better for free.
The objective order ranks correctness first and resource efficiency last, but efficiency
is never invisible: the Pareto frontier is cost-aware (``COST_AWARE_FRONTIER``) and names
every dominated candidate together with what dominates it.  Remaining quota is a
scheduler admission input, evaluated per candidate before a run is admitted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

COST_AWARE_FRONTIER = True  # TST-0304-COST-AWARE-FRONTIER

REQUIRED_COST_FIELDS: tuple[str, ...] = (
    "tokens_in",
    "tokens_out",
    "wall_clock_ms",
    "tool_calls",
    "estimated_spend_usd",
)
INTEGER_COST_FIELDS: frozenset[str] = frozenset(
    {"tokens_in", "tokens_out", "wall_clock_ms", "tool_calls"}
)
OBJECTIVE_ORDER: tuple[str, ...] = ("correctness_quality", "resource_efficiency")
SPEND_TOLERANCE_USD = 1e-9
KIND_WORSE_AND_MORE_EXPENSIVE = "worse_and_more_expensive"
KIND_WORSE_QUALITY_EQUAL_COST = "worse_quality_equal_cost"
KIND_EQUAL_QUALITY_MORE_EXPENSIVE = "equal_quality_more_expensive"


class CostRecordError(ValueError):
    """Base class for rejected cost rows."""


class MissingCostError(CostRecordError):
    """A required cost field is absent, null, blank or not a non-negative number."""


class SpendMismatchError(CostRecordError):
    """The recorded spend does not follow from the tokens and the rate card."""


class VendorDiscrepancyReject(CostRecordError):
    """Strict ingest refused a row whose tokens disagree with the vendor report."""

    def __init__(self, discrepancy: "VendorDiscrepancy") -> None:
        self.discrepancy = discrepancy
        super().__init__(
            f"vendor discrepancy for {discrepancy.run_id}: "
            f"tokens_in delta={discrepancy.delta_tokens_in} "
            f"tokens_out delta={discrepancy.delta_tokens_out}"
        )


# --------------------------------------------------------------------------- rate card
@dataclass(frozen=True)
class RateCard:
    """Published prices used to estimate spend; per million tokens plus per tool call."""

    input_usd_per_mtok: float = 3.0
    output_usd_per_mtok: float = 15.0
    tool_call_usd: float = 0.0
    name: str = "default-rate-card"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_RATE_CARD = RateCard()


def estimate_spend_usd(
    tokens_in: int,
    tokens_out: int,
    tool_calls: int = 0,
    rate_card: RateCard = DEFAULT_RATE_CARD,
) -> float:
    """Spend implied by the rate card, rounded to micro-dollars."""
    for name, value in (
        ("tokens_in", tokens_in),
        ("tokens_out", tokens_out),
        ("tool_calls", tool_calls),
    ):
        if int(value) < 0:
            raise MissingCostError(f"{name} must be non-negative, got {value!r}")
    spend = (
        int(tokens_in) * rate_card.input_usd_per_mtok / 1_000_000
        + int(tokens_out) * rate_card.output_usd_per_mtok / 1_000_000
        + int(tool_calls) * rate_card.tool_call_usd
    )
    return round(spend, 6)


# --------------------------------------------------------------------------- records
def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _number(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise MissingCostError(f"{name} is a boolean, not a number")
    if isinstance(value, (int, float)):
        out = float(value)
    elif isinstance(value, str):
        try:
            out = float(value.strip())
        except ValueError as exc:
            raise MissingCostError(f"{name} is not numeric: {value!r}") from exc
    else:
        raise MissingCostError(f"{name} is not numeric: {type(value).__name__}")
    if out != out or out in (float("inf"), float("-inf")):
        raise MissingCostError(f"{name} is not finite: {value!r}")
    if out < 0:
        raise MissingCostError(f"{name} must be non-negative, got {value!r}")
    return out


def validate_cost_fields(row: Mapping[str, Any]) -> dict[str, float | int]:
    """Require every cost field; return the parsed numbers.  Missing cost is rejected."""
    if not isinstance(row, Mapping):
        raise MissingCostError("cost row is not a mapping")
    missing = [f for f in REQUIRED_COST_FIELDS if f not in row]
    if missing:
        raise MissingCostError(f"missing cost fields: {missing}")
    blank = [f for f in REQUIRED_COST_FIELDS if _is_blank(row[f])]
    if blank:
        raise MissingCostError(f"null or blank cost fields: {blank}")
    parsed: dict[str, float | int] = {}
    for name in REQUIRED_COST_FIELDS:
        value = _number(name, row[name])
        if name in INTEGER_COST_FIELDS:
            if value != int(value):
                raise MissingCostError(
                    f"{name} must be an integer count, got {row[name]!r}"
                )
            parsed[name] = int(value)
        else:
            parsed[name] = value
    return parsed


@dataclass(frozen=True)
class CostRecord:
    """One accepted benchmark run with complete cost accounting."""

    run_id: str
    candidate_id: str
    quality: float
    tokens_in: int
    tokens_out: int
    wall_clock_ms: int
    tool_calls: int
    estimated_spend_usd: float

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out

    def cost_vector(self) -> tuple[int, float, int, int]:
        """(tokens_total, spend, wall_clock_ms, tool_calls): lower is better on every axis."""
        return (
            self.tokens_total,
            self.estimated_spend_usd,
            self.wall_clock_ms,
            self.tool_calls,
        )

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["tokens_total"] = self.tokens_total
        return out


def parse_cost_record(
    row: Mapping[str, Any], rate_card: RateCard = DEFAULT_RATE_CARD
) -> CostRecord:
    """Validate a row and check its spend against the rate card."""
    cost = validate_cost_fields(row)
    for key in ("candidate_id", "quality"):
        if _is_blank(row.get(key)):
            raise CostRecordError(f"row is missing {key!r}")
    quality = _number("quality", row["quality"])
    run_id = str(row.get("run_id") or f"run-{row['candidate_id']}")
    expected = estimate_spend_usd(
        cost["tokens_in"], cost["tokens_out"], cost["tool_calls"], rate_card
    )
    recorded = float(cost["estimated_spend_usd"])
    if abs(recorded - expected) > SPEND_TOLERANCE_USD:
        raise SpendMismatchError(
            f"{run_id}: recorded spend {recorded} does not follow from the rate card "
            f"({rate_card.name} -> {expected})"
        )
    return CostRecord(
        run_id=run_id,
        candidate_id=str(row["candidate_id"]),
        quality=quality,
        tokens_in=int(cost["tokens_in"]),
        tokens_out=int(cost["tokens_out"]),
        wall_clock_ms=int(cost["wall_clock_ms"]),
        tool_calls=int(cost["tool_calls"]),
        estimated_spend_usd=recorded,
    )


def coverage_complete(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Share of rows carrying every cost field; the rejected ones are listed by reason."""
    accepted = 0
    rejections: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        try:
            validate_cost_fields(row)
            accepted += 1
        except MissingCostError as exc:
            rejections.append(
                {
                    "index": idx,
                    "label": row.get("label") if isinstance(row, Mapping) else None,
                    "reason": str(exc),
                }
            )
    total = len(rows)
    return {
        "total": total,
        "accepted": accepted,
        "rejected": len(rejections),
        "coverage": (accepted / total) if total else 0.0,
        "rejections": rejections,
        "required_cost_fields": list(REQUIRED_COST_FIELDS),
    }


# --------------------------------------------------------------------------- vendor reconcile
@dataclass(frozen=True)
class VendorUsage:
    """What the vendor billed for a run, keyed by the same run_id."""

    run_id: str
    tokens_in: int
    tokens_out: int
    source: str = "vendor"


@dataclass(frozen=True)
class VendorDiscrepancy:
    """Recorded minus vendor tokens for one run; zero deltas are reported, not omitted."""

    run_id: str
    source: str
    recorded_tokens_in: int
    recorded_tokens_out: int
    vendor_tokens_in: int
    vendor_tokens_out: int
    delta_tokens_in: int
    delta_tokens_out: int
    match: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def reconcile_vendor(record: CostRecord, vendor: VendorUsage) -> VendorDiscrepancy:
    """Compare recorded tokens with the vendor report for the same run."""
    if vendor.run_id != record.run_id:
        raise CostRecordError(
            f"vendor usage is for {vendor.run_id!r}, record is {record.run_id!r}"
        )
    d_in = record.tokens_in - int(vendor.tokens_in)
    d_out = record.tokens_out - int(vendor.tokens_out)
    return VendorDiscrepancy(
        run_id=record.run_id,
        source=vendor.source,
        recorded_tokens_in=record.tokens_in,
        recorded_tokens_out=record.tokens_out,
        vendor_tokens_in=int(vendor.tokens_in),
        vendor_tokens_out=int(vendor.tokens_out),
        delta_tokens_in=d_in,
        delta_tokens_out=d_out,
        match=(d_in == 0 and d_out == 0),
    )


def ingest_row(
    row: Mapping[str, Any],
    vendor: VendorUsage | None = None,
    *,
    strict_vendor: bool = False,
    rate_card: RateCard = DEFAULT_RATE_CARD,
) -> tuple[CostRecord, VendorDiscrepancy | None]:
    """Parse, then reconcile; strict ingest raises on any vendor delta."""
    record = parse_cost_record(row, rate_card)
    if vendor is None:
        if strict_vendor:
            raise VendorDiscrepancyReject(
                VendorDiscrepancy(
                    record.run_id,
                    "absent",
                    record.tokens_in,
                    record.tokens_out,
                    0,
                    0,
                    record.tokens_in,
                    record.tokens_out,
                    False,
                )
            )
        return record, None
    discrepancy = reconcile_vendor(record, vendor)
    if strict_vendor and not discrepancy.match:
        raise VendorDiscrepancyReject(discrepancy)
    return record, discrepancy


# --------------------------------------------------------------------------- deltas
def _ratio(candidate: float, baseline: float) -> float:
    if baseline == 0:
        return float("inf") if candidate > 0 else 1.0
    return candidate / baseline


def quality_cost_delta(baseline: CostRecord, candidate: CostRecord) -> dict[str, Any]:
    """Quality delta published next to every cost delta, with a decision note."""
    q_delta = candidate.quality - baseline.quality
    q_rel = _ratio(q_delta, baseline.quality) if baseline.quality else q_delta
    tokens_ratio = _ratio(candidate.tokens_total, baseline.tokens_total)
    spend_ratio = _ratio(candidate.estimated_spend_usd, baseline.estimated_spend_usd)
    note = (
        f"quality {q_rel * 100:+.4f}% at {tokens_ratio:.2f}x tokens / {spend_ratio:.2f}x spend"
        if q_rel < 0
        else f"quality {q_rel * 100:.4f}% at {tokens_ratio:.2f}x tokens / {spend_ratio:.2f}x spend"
    )
    return {
        "baseline_id": baseline.candidate_id,
        "candidate_id": candidate.candidate_id,
        "quality_baseline": baseline.quality,
        "quality_candidate": candidate.quality,
        "quality_delta": q_delta,
        "quality_relative": q_rel,
        "tokens_baseline": baseline.tokens_total,
        "tokens_candidate": candidate.tokens_total,
        "tokens_ratio": tokens_ratio,
        "spend_baseline_usd": baseline.estimated_spend_usd,
        "spend_candidate_usd": candidate.estimated_spend_usd,
        "spend_ratio": spend_ratio,
        "wall_clock_ms_baseline": baseline.wall_clock_ms,
        "wall_clock_ms_candidate": candidate.wall_clock_ms,
        "tool_calls_baseline": baseline.tool_calls,
        "tool_calls_candidate": candidate.tool_calls,
        "decision_note": note,
    }


# --------------------------------------------------------------------------- quota
@dataclass(frozen=True)
class Quota:
    """Remaining budget the scheduler may still spend; ``None`` means unlimited on that axis."""

    tokens: int | None = None
    spend_usd: float | None = None
    wall_clock_ms: int | None = None
    tool_calls: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def admit_quota(record: CostRecord, quota: Quota) -> dict[str, Any]:
    """Admit a candidate only if it fits inside every remaining-quota axis."""
    demand = {
        "tokens": record.tokens_total,
        "spend_usd": record.estimated_spend_usd,
        "wall_clock_ms": record.wall_clock_ms,
        "tool_calls": record.tool_calls,
    }
    limits = quota.as_dict()
    breaches = [
        axis
        for axis, need in demand.items()
        if limits[axis] is not None and need > limits[axis]
    ]
    return {
        "candidate_id": record.candidate_id,
        "run_id": record.run_id,
        "admitted": not breaches,
        "breaches": breaches,
        "demand": demand,
        "remaining": limits,
        "headroom": {
            axis: (None if limits[axis] is None else limits[axis] - need)
            for axis, need in demand.items()
        },
    }


# --------------------------------------------------------------------------- frontier
def dominates(a: CostRecord, b: CostRecord) -> bool:
    """``a`` dominates ``b``: at least as good on quality and every cost axis, strictly better once."""
    if a.quality < b.quality:
        return False
    ca, cb = a.cost_vector(), b.cost_vector()
    if any(x > y for x, y in zip(ca, cb)):
        return False
    return a.quality > b.quality or any(x < y for x, y in zip(ca, cb))


def _dominance_kind(loser: CostRecord, winners: Sequence[CostRecord]) -> str:
    worse_quality = any(w.quality > loser.quality for w in winners)
    more_expensive = any(
        any(x < y for x, y in zip(w.cost_vector(), loser.cost_vector()))
        for w in winners
    )
    if worse_quality and more_expensive:
        return KIND_WORSE_AND_MORE_EXPENSIVE
    if worse_quality:
        return KIND_WORSE_QUALITY_EQUAL_COST
    return KIND_EQUAL_QUALITY_MORE_EXPENSIVE


def _check_unique(records: Sequence[CostRecord]) -> None:
    ids = [r.candidate_id for r in records]
    if len(set(ids)) != len(ids):
        raise CostRecordError(f"duplicate candidate ids in frontier input: {ids}")


def identify_dominated(records: Iterable[CostRecord]) -> list[dict[str, Any]]:
    """Name every dominated candidate and its dominators (cost-aware only)."""
    recs = list(records)
    _check_unique(recs)
    if not COST_AWARE_FRONTIER:
        # Cost-blind mode has no cost axis to lose on, so nothing is ever dominated.
        return []
    rows: list[dict[str, Any]] = []
    for loser in recs:
        winners = [w for w in recs if w is not loser and dominates(w, loser)]
        if not winners:
            continue
        rows.append(
            {
                "candidate_id": loser.candidate_id,
                "quality": loser.quality,
                "tokens_total": loser.tokens_total,
                "estimated_spend_usd": loser.estimated_spend_usd,
                "dominated_by": sorted(w.candidate_id for w in winners),
                "kind": _dominance_kind(loser, winners),
            }
        )
    return rows


def pareto_frontier(records: Iterable[CostRecord]) -> list[CostRecord]:
    """Candidates no other candidate dominates, best quality first then cheapest."""
    recs = list(records)
    _check_unique(recs)
    if not COST_AWARE_FRONTIER:
        return list(recs)
    dominated = {row["candidate_id"] for row in identify_dominated(recs)}
    front = [r for r in recs if r.candidate_id not in dominated]
    return sorted(front, key=lambda r: (-r.quality, r.cost_vector(), r.candidate_id))


def objective_rank(records: Iterable[CostRecord]) -> list[dict[str, Any]]:
    """Rank by the objective order: correctness first, resource efficiency last but visible."""
    recs = list(records)
    _check_unique(recs)
    ordered = sorted(recs, key=lambda r: (-r.quality, r.cost_vector(), r.candidate_id))
    return [
        {
            "rank": i,
            "candidate_id": r.candidate_id,
            "quality": r.quality,
            "tokens_total": r.tokens_total,
            "estimated_spend_usd": r.estimated_spend_usd,
            "objective_order": list(OBJECTIVE_ORDER),
            "efficiency_is_last": OBJECTIVE_ORDER[-1] == "resource_efficiency",
        }
        for i, r in enumerate(ordered, 1)
    ]


__all__ = [
    "COST_AWARE_FRONTIER",
    "CostRecord",
    "CostRecordError",
    "DEFAULT_RATE_CARD",
    "INTEGER_COST_FIELDS",
    "KIND_EQUAL_QUALITY_MORE_EXPENSIVE",
    "KIND_WORSE_AND_MORE_EXPENSIVE",
    "KIND_WORSE_QUALITY_EQUAL_COST",
    "MissingCostError",
    "OBJECTIVE_ORDER",
    "Quota",
    "REQUIRED_COST_FIELDS",
    "RateCard",
    "SPEND_TOLERANCE_USD",
    "SpendMismatchError",
    "VendorDiscrepancy",
    "VendorDiscrepancyReject",
    "VendorUsage",
    "admit_quota",
    "coverage_complete",
    "dominates",
    "estimate_spend_usd",
    "identify_dominated",
    "ingest_row",
    "objective_rank",
    "pareto_frontier",
    "parse_cost_record",
    "quality_cost_delta",
    "reconcile_vendor",
    "validate_cost_fields",
]
