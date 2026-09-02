#!/usr/bin/env python3
"""IMP-0188 progressive fusion: cheap tier first, escalate only on need.

Composes a cheap fast source and an expensive thorough source into a two-rung
progressive workflow with a typed, measurable escalation predicate.

Work is charged to an append-only budget ledger when a source actually runs.
Correctness is a paired, per-case comparison against the expensive form on the
same case ids. Missing either declared bar is REJECT, not a caveat.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Literal, Sequence

LABEL = Literal["PRIME", "COMPOSITE"]
CHEAP_WORK_UNITS = 1
EXPENSIVE_WORK_UNITS = 10
FACTOR_BASE: tuple[int, ...] = (2, 3, 5, 7, 11, 13, 17, 19)
FACTOR_BASE_PRODUCT = math.prod(FACTOR_BASE)
MAX_ESCALATIONS = 1
MAX_MISMATCH_RATE = 0.0
MIN_WORK_REDUCTION = 0.15
MIN_CASES = 16

EASY_COMPOSITES: tuple[int, ...] = (
    9,
    15,
    21,
    25,
    27,
    33,
    35,
    39,
    45,
    49,
    51,
    55,
    57,
    63,
    65,
    69,
    77,
    85,
    91,
    95,
)
FACTOR_BASE_PRIMES: tuple[int, ...] = FACTOR_BASE
# Not in the cheap factor base: cheap cannot certify; must escalate.
LARGE_PRIMES: tuple[int, ...] = (23, 29, 31, 37, 41, 43)
HARD_COMPOSITES: tuple[int, ...] = (
    23 * 29,  # 667
    31 * 37,  # 1147
    41 * 43,  # 1763
    47 * 53,  # 2491
    59 * 61,  # 3599
    67 * 71,  # 4757
)


@dataclass(frozen=True)
class LedgerEntry:
    seq: int
    case_id: str
    source_id: str
    work_units: int
    reason: str
    rung: int


class BudgetLedger:
    """Immutable-after-write budget ledger. Past charges cannot be edited."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []
        self._seen: set[tuple[str, str, int]] = set()
        self._frozen = False

    def charge(
        self,
        case_id: str,
        source_id: str,
        work_units: int,
        reason: str,
        rung: int,
    ) -> LedgerEntry:
        if self._frozen:
            raise RuntimeError("ledger is frozen")
        if work_units <= 0:
            raise ValueError("work_units must be positive; zero/negative is not a charge")
        key = (case_id, source_id, rung)
        if key in self._seen:
            raise RuntimeError(f"double-count refused: {key}")
        entry = LedgerEntry(
            seq=len(self._entries) + 1,
            case_id=case_id,
            source_id=source_id,
            work_units=work_units,
            reason=reason,
            rung=rung,
        )
        self._entries.append(entry)
        self._seen.add(key)
        return entry

    def freeze(self) -> None:
        self._frozen = True

    def entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._entries)

    def total(self, source_id: str | None = None) -> int:
        if source_id is None:
            return sum(e.work_units for e in self._entries)
        return sum(e.work_units for e in self._entries if e.source_id == source_id)

    def as_dicts(self) -> list[dict]:
        return [
            {
                "seq": e.seq,
                "case_id": e.case_id,
                "source_id": e.source_id,
                "work_units": e.work_units,
                "reason": e.reason,
                "rung": e.rung,
            }
            for e in self._entries
        ]


def assert_ledger_invariants(ledger: BudgetLedger) -> None:
    rows = ledger.entries()
    prev_seq = 0
    running = 0
    seen: set[tuple[str, str, int]] = set()
    for e in rows:
        if e.seq != prev_seq + 1:
            raise AssertionError(f"ledger seq gap: {prev_seq} -> {e.seq}")
        if e.work_units <= 0:
            raise AssertionError(f"non-positive charge seq={e.seq}")
        key = (e.case_id, e.source_id, e.rung)
        if key in seen:
            raise AssertionError(f"double-count in ledger: {key}")
        seen.add(key)
        running += e.work_units
        prev_seq = e.seq
    if running != ledger.total():
        raise AssertionError("ledger total != sum of entries")


@dataclass(frozen=True)
class AdequacyFeatures:
    """Measurable cheap-rung features. Not a self-score of output quality."""

    n: int
    gcd_with_factor_base: int
    certified: bool
    certification_rule: str


@dataclass(frozen=True)
class SourceResult:
    case_id: str
    n: int
    source_id: str
    label: LABEL
    work_units: int
    features: AdequacyFeatures | None
    ops: int


@dataclass(frozen=True)
class EscalationPredicate:
    """Typed escalation predicate. kind is the declared type; decide() is measurable."""

    kind: str
    description: str
    decide: Callable[[AdequacyFeatures], bool]

    def spec(self) -> dict:
        return {
            "kind": self.kind,
            "type": "escalation-predicate",
            "description": self.description,
            "inputs": ["AdequacyFeatures.certified", "AdequacyFeatures.gcd_with_factor_base"],
            "self_assessment": False,
        }


def cheap_features(n: int) -> AdequacyFeatures:
    if n < 2:
        return AdequacyFeatures(
            n=n,
            gcd_with_factor_base=n,
            certified=True,
            certification_rule="n<2-composite",
        )
    g = math.gcd(n, FACTOR_BASE_PRODUCT)
    if n in FACTOR_BASE:
        return AdequacyFeatures(
            n=n,
            gcd_with_factor_base=g,
            certified=True,
            certification_rule="factor-base-prime",
        )
    if g > 1:
        return AdequacyFeatures(
            n=n,
            gcd_with_factor_base=g,
            certified=True,
            certification_rule="small-factor-found",
        )
    return AdequacyFeatures(
        n=n,
        gcd_with_factor_base=g,
        certified=False,
        certification_rule="gcd==1-uncertified",
    )


def cheap_label(features: AdequacyFeatures) -> LABEL:
    if features.n < 2:
        return "COMPOSITE"
    if features.n in FACTOR_BASE:
        return "PRIME"
    if features.gcd_with_factor_base > 1:
        return "COMPOSITE"
    # Uncertified guess: treat as prime. Correct only if the number is actually prime.
    return "PRIME"


def run_cheap(n: int, case_id: str) -> SourceResult:
    feat = cheap_features(n)
    return SourceResult(
        case_id=case_id,
        n=n,
        source_id="cheap-small-factor-gcd",
        label=cheap_label(feat),
        work_units=CHEAP_WORK_UNITS,
        features=feat,
        ops=1,
    )


def trial_primality(n: int) -> tuple[LABEL, int]:
    if n < 2:
        return "COMPOSITE", 0
    ops = 0
    if n % 2 == 0:
        ops += 1
        return ("COMPOSITE" if n != 2 else "PRIME"), ops
    f = 3
    while f * f <= n:
        ops += 1
        if n % f == 0:
            return "COMPOSITE", ops
        f += 2
    return "PRIME", ops


def run_expensive(n: int, case_id: str) -> SourceResult:
    label, ops = trial_primality(n)
    return SourceResult(
        case_id=case_id,
        n=n,
        source_id="expensive-trial-to-sqrt",
        label=label,
        work_units=EXPENSIVE_WORK_UNITS,
        features=None,
        ops=ops,
    )


def uncertified_predicate() -> EscalationPredicate:
    return EscalationPredicate(
        kind="uncertified-small-factor-search",
        description=(
            "Escalate iff the cheap gcd against the factor-base product cannot certify "
            "(gcd==1 and n not in the factor base). Certification is a function of n and "
            "the factor base, not a model self-score."
        ),
        decide=lambda feat: not feat.certified,
    )


def never_escalate_predicate() -> EscalationPredicate:
    return EscalationPredicate(
        kind="never-escalate",
        description="Planted mutant: never escalates, even on uncertified hard cases.",
        decide=lambda feat: False,
    )


@dataclass
class ProgressiveRun:
    case_id: str
    n: int
    label: LABEL
    escalated: bool
    escalations: int
    cheap: SourceResult
    expensive: SourceResult | None
    predicate_fired: bool


@dataclass(frozen=True)
class FusedWorkflow:
    strategy: str
    cheap_id: str
    expensive_id: str
    predicate: EscalationPredicate
    max_escalations: int

    def spec(self) -> dict:
        return {
            "kind": "fused-workflow",
            "strategy": self.strategy,
            "sources": {
                "cheap": {
                    "id": self.cheap_id,
                    "work_units_when_invoked": CHEAP_WORK_UNITS,
                    "method": "gcd(n, factor_base_product)",
                    "factor_base": list(FACTOR_BASE),
                },
                "expensive": {
                    "id": self.expensive_id,
                    "work_units_when_invoked": EXPENSIVE_WORK_UNITS,
                    "method": "trial-division-to-sqrt",
                },
            },
            "escalation_predicate": self.predicate.spec(),
            "max_escalations": self.max_escalations,
            "rungs": ["cheap", "expensive"],
        }


def compose_progressive(
    predicate: EscalationPredicate | None = None,
    max_escalations: int = MAX_ESCALATIONS,
) -> FusedWorkflow:
    return FusedWorkflow(
        strategy="progressive",
        cheap_id="cheap-small-factor-gcd",
        expensive_id="expensive-trial-to-sqrt",
        predicate=predicate or uncertified_predicate(),
        max_escalations=max_escalations,
    )


def run_progressive(
    n: int,
    workflow: FusedWorkflow,
    ledger: BudgetLedger,
    case_id: str | None = None,
) -> ProgressiveRun:
    cid = case_id or f"n={n}"
    cheap = run_cheap(n, cid)
    ledger.charge(
        cid, cheap.source_id, cheap.work_units, "cheap-rung", rung=0
    )
    if cheap.features is None:
        raise RuntimeError("cheap rung must emit adequacy features")
    fire = workflow.predicate.decide(cheap.features)
    if not fire:
        return ProgressiveRun(
            case_id=cid,
            n=n,
            label=cheap.label,
            escalated=False,
            escalations=0,
            cheap=cheap,
            expensive=None,
            predicate_fired=False,
        )
    if workflow.max_escalations < 1:
        raise RuntimeError("escalation bound forbids the expensive rung")
    expensive = run_expensive(n, cid)
    ledger.charge(
        cid, expensive.source_id, expensive.work_units, "escalated-expensive-rung", rung=1
    )
    return ProgressiveRun(
        case_id=cid,
        n=n,
        label=expensive.label,
        escalated=True,
        escalations=1,
        cheap=cheap,
        expensive=expensive,
        predicate_fired=True,
    )


def benchmark_cases() -> tuple[dict, ...]:
    rows: list[dict] = []
    for n in EASY_COMPOSITES:
        rows.append({"n": n, "band": "easy-composite", "case_id": f"n={n}"})
    for n in FACTOR_BASE_PRIMES:
        rows.append({"n": n, "band": "factor-base-prime", "case_id": f"n={n}"})
    for n in LARGE_PRIMES:
        rows.append({"n": n, "band": "large-prime", "case_id": f"n={n}"})
    for n in HARD_COMPOSITES:
        rows.append({"n": n, "band": "hard-composite", "case_id": f"n={n}"})
    ids = [r["case_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate case ids")
    return tuple(rows)


@dataclass
class AcceptanceReport:
    verdict: str
    reason: str
    n_cases: int
    mismatches: int
    mismatch_rate: float
    max_mismatch_rate: float
    progressive_work: int
    expensive_work: int
    reduction_ratio: float
    min_reduction_ratio: float
    per_case: list[dict] = field(default_factory=list)
    progressive_ledger: list[dict] = field(default_factory=list)
    expensive_ledger: list[dict] = field(default_factory=list)
    escalations: int = 0
    workflow: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "n_cases": self.n_cases,
            "paired": True,
            "group_means": False,
            "correctness": {
                "mismatches_vs_expensive": self.mismatches,
                "mismatch_rate": self.mismatch_rate,
                "max_mismatch_rate": self.max_mismatch_rate,
                "per_case_deltas": self.per_case,
            },
            "work": {
                "progressive_ledger_total": self.progressive_work,
                "expensive_only_ledger_total": self.expensive_work,
                "reduction_ratio": self.reduction_ratio,
                "min_work_reduction_ratio": self.min_reduction_ratio,
                "source": "budget_ledger_sum",
                "estimated": False,
                "escalations": self.escalations,
            },
            "workflow": self.workflow,
            "progressive_ledger": self.progressive_ledger,
            "expensive_ledger": self.expensive_ledger,
        }


def evaluate(
    workflow: FusedWorkflow,
    cases: Sequence[dict] | None = None,
) -> AcceptanceReport:
    cases = tuple(cases) if cases is not None else benchmark_cases()
    if len(cases) < MIN_CASES:
        return AcceptanceReport(
            verdict="INSUFFICIENT-EVIDENCE",
            reason=f"n_cases={len(cases)} below MIN_CASES={MIN_CASES}",
            n_cases=len(cases),
            mismatches=0,
            mismatch_rate=0.0,
            max_mismatch_rate=MAX_MISMATCH_RATE,
            progressive_work=0,
            expensive_work=0,
            reduction_ratio=0.0,
            min_reduction_ratio=MIN_WORK_REDUCTION,
            workflow=workflow.spec(),
        )
    prog_ledger = BudgetLedger()
    exp_ledger = BudgetLedger()
    per_case: list[dict] = []
    mismatches = 0
    escalations = 0
    for row in cases:
        n = int(row["n"])
        cid = str(row["case_id"])
        prog = run_progressive(n, workflow, prog_ledger, cid)
        exp = run_expensive(n, cid)
        exp_ledger.charge(
            cid, exp.source_id, exp.work_units, "expensive-only-matched", rung=0
        )
        match = prog.label == exp.label
        if not match:
            mismatches += 1
        if prog.escalated:
            escalations += 1
        per_case.append(
            {
                "case_id": cid,
                "n": n,
                "band": row.get("band"),
                "progressive_label": prog.label,
                "expensive_label": exp.label,
                "match": match,
                "escalated": prog.escalated,
                "predicate_fired": prog.predicate_fired,
                "cheap_work": prog.cheap.work_units,
                "expensive_rung_work": prog.expensive.work_units if prog.expensive else 0,
            }
        )
    prog_ledger.freeze()
    exp_ledger.freeze()
    assert_ledger_invariants(prog_ledger)
    assert_ledger_invariants(exp_ledger)
    n_cases = len(cases)
    mismatch_rate = mismatches / n_cases
    p_work = prog_ledger.total()
    e_work = exp_ledger.total()
    if e_work <= 0:
        reduction = 0.0
    else:
        reduction = (e_work - p_work) / e_work
    # Recompute totals from entries so a stuffed summary cannot pass.
    p_sum = sum(e.work_units for e in prog_ledger.entries())
    e_sum = sum(e.work_units for e in exp_ledger.entries())
    if p_sum != p_work or e_sum != e_work:
        return AcceptanceReport(
            verdict="REJECT",
            reason="ledger-summary-mismatch",
            n_cases=n_cases,
            mismatches=mismatches,
            mismatch_rate=mismatch_rate,
            max_mismatch_rate=MAX_MISMATCH_RATE,
            progressive_work=p_work,
            expensive_work=e_work,
            reduction_ratio=reduction,
            min_reduction_ratio=MIN_WORK_REDUCTION,
            per_case=per_case,
            progressive_ledger=prog_ledger.as_dicts(),
            expensive_ledger=exp_ledger.as_dicts(),
            escalations=escalations,
            workflow=workflow.spec(),
        )
    if mismatch_rate > MAX_MISMATCH_RATE:
        verdict, reason = "REJECT", "correctness-delta-exceeds-tolerance"
    elif reduction < MIN_WORK_REDUCTION:
        verdict, reason = "REJECT", "work-reduction-below-declared-minimum"
    else:
        verdict, reason = "PASS", "correctness-within-tolerance-and-measured-work-reduction"
    return AcceptanceReport(
        verdict=verdict,
        reason=reason,
        n_cases=n_cases,
        mismatches=mismatches,
        mismatch_rate=mismatch_rate,
        max_mismatch_rate=MAX_MISMATCH_RATE,
        progressive_work=p_work,
        expensive_work=e_work,
        reduction_ratio=reduction,
        min_reduction_ratio=MIN_WORK_REDUCTION,
        per_case=per_case,
        progressive_ledger=prog_ledger.as_dicts(),
        expensive_ledger=exp_ledger.as_dicts(),
        escalations=escalations,
        workflow=workflow.spec(),
    )


def planted_mismatch_is_rejected() -> bool:
    """Detector control: never-escalate on hard cases must be REJECT, not a caveat."""
    wf = compose_progressive()
    bad = evaluate(compose_progressive(never_escalate_predicate()), benchmark_cases())
    if bad.verdict != "REJECT":
        return False
    if bad.mismatches < 1:
        return False
    if "correctness" not in bad.reason:
        return False
    good = evaluate(wf)
    return good.verdict == "PASS"


def hard_case_ids() -> tuple[str, ...]:
    return tuple(f"n={n}" for n in HARD_COMPOSITES)
