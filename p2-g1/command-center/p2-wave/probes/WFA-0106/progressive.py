#!/usr/bin/env python3
"""WFA-0106 progressive fusion: cheapest adequate source first, then escalate.

L0-L3 follows the smallest-check-ladder precedent. A typed measurable
adequacy predicate (factor found, or the trial bound covers sqrt(n))
decides whether the current rung is enough. Escalation is bounded so a
predicate that never holds cannot loop.

Work is charged to an append-only budget ledger when a rung actually
runs. Outcome is a paired per-case comparison against always running
the top rung. A cheaper ladder with worse labels is REJECT. A ladder
that escalates on every input is a more expensive top rung with extra
steps and is also REJECT.

WFA-0044 (IR spec) and WFA-0039 (stopping-rule extract) are not on this
worktree. Sources are IR-shaped hermetic rungs with source_anchor on
every node — disclosed, not hidden as a PASS caveat.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

Label = Literal["PRIME", "COMPOSITE"]

L0_COST = 1
L1_COST = 3
L2_COST = 8
L3_COST = 20
L0_BASE: tuple[int, ...] = (2, 3, 5, 7)
L0_PRODUCT = 210
L1_BOUND = 11  # 11^2 = 121
L2_BOUND = 23  # 23^2 = 529
MAX_ESCALATIONS = 3
MAX_INVOCATIONS = 4
MAX_MISMATCH_RATE = 0.0
MIN_REDUCTION = 0.15
MIN_CASES = 16
LOOP_SAFETY = 200
LOOP_INPUT_N = 541

L0_COMPOSITES: tuple[int, ...] = (
    9, 15, 21, 25, 27, 33, 35, 39, 45, 49, 51, 55,
)
L0_PRIMES: tuple[int, ...] = (2, 3, 5, 7)
L1_CASES: tuple[int, ...] = (11, 13, 17, 19, 121, 143)
L2_CASES: tuple[int, ...] = (149, 151, 169, 221, 289, 323)
L3_CASES: tuple[int, ...] = (541, 547, 841, 899)

RUNG_IDS: tuple[str, ...] = (
    "L0-cheap-gcd",
    "L1-trial-11",
    "L2-trial-23",
    "L3-trial-sqrt",
)
RUNG_COSTS: tuple[int, ...] = (L0_COST, L1_COST, L2_COST, L3_COST)


@dataclass(frozen=True)
class LedgerEntry:
    seq: int
    case_id: str
    source_id: str
    work_units: int
    reason: str
    rung: int
    invocation: int


class BudgetLedger:
    """Append-only budget ledger. Past charges cannot be edited."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []
        self._seen: set[tuple[str, str, int, int]] = set()
        self._frozen = False

    def charge(
        self,
        case_id: str,
        source_id: str,
        work_units: int,
        reason: str,
        rung: int,
        invocation: int = 0,
    ) -> LedgerEntry:
        if self._frozen:
            raise RuntimeError("ledger is frozen")
        if work_units <= 0:
            raise ValueError("work_units must be positive")
        key = (case_id, source_id, rung, invocation)
        if key in self._seen:
            raise RuntimeError(f"double-count refused: {key}")
        entry = LedgerEntry(
            seq=len(self._entries) + 1,
            case_id=case_id,
            source_id=source_id,
            work_units=work_units,
            reason=reason,
            rung=rung,
            invocation=invocation,
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
                "invocation": e.invocation,
            }
            for e in self._entries
        ]


def assert_ledger_invariants(ledger: BudgetLedger) -> None:
    rows = ledger.entries()
    prev = 0
    running = 0
    seen: set[tuple[str, str, int, int]] = set()
    for e in rows:
        if e.seq != prev + 1:
            raise AssertionError(f"ledger seq gap: {prev} -> {e.seq}")
        if e.work_units <= 0:
            raise AssertionError(f"non-positive charge seq={e.seq}")
        key = (e.case_id, e.source_id, e.rung, e.invocation)
        if key in seen:
            raise AssertionError(f"double-count in ledger: {key}")
        seen.add(key)
        running += e.work_units
        prev = e.seq
    if running != ledger.total():
        raise AssertionError("ledger total != sum of entries")


@dataclass(frozen=True)
class AdequacyFeatures:
    """Measurable rung features. Not a model self-score of output quality."""

    n: int
    rung: int
    gcd_with_base: int
    trial_bound: int
    factor_found: int | None
    sqrt_covered: bool
    certified: bool
    certification_rule: str
    self_assessment: bool = False


@dataclass(frozen=True)
class RungResult:
    case_id: str
    n: int
    source_id: str
    rung: int
    label: Label
    work_units: int
    features: AdequacyFeatures


@dataclass(frozen=True)
class AdequacyPredicate:
    """Typed adequacy predicate. holds() is a function of measurable features."""

    kind: str
    description: str
    holds: Callable[[AdequacyFeatures], bool]
    self_assessment: bool = False

    def spec(self) -> dict:
        return {
            "kind": self.kind,
            "type": "adequacy-predicate",
            "description": self.description,
            "inputs": [
                "AdequacyFeatures.certified",
                "AdequacyFeatures.factor_found",
                "AdequacyFeatures.sqrt_covered",
                "AdequacyFeatures.gcd_with_base",
            ],
            "self_assessment": False,
        }


def certified_predicate() -> AdequacyPredicate:
    return AdequacyPredicate(
        kind="certified-factor-or-sqrt-cover",
        description=(
            "Rung is adequate iff it certified a factor (gcd>1 or trial hit) "
            "or its trial bound covers sqrt(n). Certification is a function of "
            "n and the rung bound, not a model self-score."
        ),
        holds=lambda feat: bool(feat.certified),
        self_assessment=False,
    )


def never_adequate_predicate() -> AdequacyPredicate:
    return AdequacyPredicate(
        kind="never-adequate",
        description="Planted mutant: never holds, so a missing bound would loop.",
        holds=lambda _feat: False,
        self_assessment=False,
    )


def always_adequate_predicate() -> AdequacyPredicate:
    return AdequacyPredicate(
        kind="always-adequate",
        description="Planted mutant: never escalates, even on uncertified cases.",
        holds=lambda _feat: True,
        self_assessment=False,
    )


def _trial_factor(n: int, bound: int) -> tuple[int | None, bool]:
    """Return (factor_or_None, sqrt_covered) for trial up to bound."""
    if n < 2:
        return None, True
    if n % 2 == 0:
        return (None if n == 2 else 2), (bound >= math.isqrt(n) or n == 2)
    f = 3
    limit = min(bound, math.isqrt(n))
    while f <= limit:
        if n % f == 0:
            return f, bound >= math.isqrt(n)
        f += 2
    return None, bound >= math.isqrt(n)


def run_l0(n: int, case_id: str) -> RungResult:
    if n < 2:
        feat = AdequacyFeatures(
            n=n,
            rung=0,
            gcd_with_base=n,
            trial_bound=0,
            factor_found=None,
            sqrt_covered=True,
            certified=True,
            certification_rule="n<2-composite",
        )
        return RungResult(case_id, n, RUNG_IDS[0], 0, "COMPOSITE", L0_COST, feat)
    g = math.gcd(n, L0_PRODUCT)
    if n in L0_BASE:
        feat = AdequacyFeatures(
            n=n,
            rung=0,
            gcd_with_base=g,
            trial_bound=7,
            factor_found=None,
            sqrt_covered=True,
            certified=True,
            certification_rule="factor-base-prime",
        )
        return RungResult(case_id, n, RUNG_IDS[0], 0, "PRIME", L0_COST, feat)
    if g > 1:
        feat = AdequacyFeatures(
            n=n,
            rung=0,
            gcd_with_base=g,
            trial_bound=7,
            factor_found=g,
            sqrt_covered=False,
            certified=True,
            certification_rule="gcd-small-factor",
        )
        return RungResult(case_id, n, RUNG_IDS[0], 0, "COMPOSITE", L0_COST, feat)
    feat = AdequacyFeatures(
        n=n,
        rung=0,
        gcd_with_base=g,
        trial_bound=7,
        factor_found=None,
        sqrt_covered=False,
        certified=False,
        certification_rule="gcd==1-uncertified",
    )
    return RungResult(case_id, n, RUNG_IDS[0], 0, "PRIME", L0_COST, feat)


def run_trial_rung(
    n: int, case_id: str, rung: int, bound: int, cost: int
) -> RungResult:
    factor, covered = _trial_factor(n, bound)
    if n < 2:
        rule, label, certified = "n<2-composite", "COMPOSITE", True
        factor, covered = None, True
    elif factor is not None:
        rule, label, certified = f"trial-factor-{factor}", "COMPOSITE", True
    elif covered:
        rule, label, certified = f"trial-bound-{bound}-covers-sqrt", "PRIME", True
    else:
        rule, label, certified = f"trial-bound-{bound}-uncertified", "PRIME", False
    feat = AdequacyFeatures(
        n=n,
        rung=rung,
        gcd_with_base=math.gcd(n, L0_PRODUCT) if n >= 0 else n,
        trial_bound=bound,
        factor_found=factor,
        sqrt_covered=covered,
        certified=certified,
        certification_rule=rule,
    )
    return RungResult(case_id, n, RUNG_IDS[rung], rung, label, cost, feat)


def run_l1(n: int, case_id: str) -> RungResult:
    return run_trial_rung(n, case_id, 1, L1_BOUND, L1_COST)


def run_l2(n: int, case_id: str) -> RungResult:
    return run_trial_rung(n, case_id, 2, L2_BOUND, L2_COST)


def run_l3(n: int, case_id: str) -> RungResult:
    return run_trial_rung(n, case_id, 3, max(2, math.isqrt(n)), L3_COST)


RUNNERS: tuple[Callable[[int, str], RungResult], ...] = (
    run_l0,
    run_l1,
    run_l2,
    run_l3,
)


def fingerprint(feat: AdequacyFeatures) -> str:
    return (
        f"rung={feat.rung}|certified={feat.certified}|"
        f"rule={feat.certification_rule}"
    )


@dataclass
class RungTrace:
    rung: int
    rung_id: str
    cost: int
    adequate: bool
    why: str
    label: Label
    certification_rule: str
    fingerprint: str
    factor_found: int | None
    sqrt_covered: bool

    def as_dict(self) -> dict:
        return {
            "rung": self.rung,
            "rung_id": self.rung_id,
            "cost": self.cost,
            "adequate": self.adequate,
            "why": self.why,
            "label": self.label,
            "certification_rule": self.certification_rule,
            "fingerprint": self.fingerprint,
            "factor_found": self.factor_found,
            "sqrt_covered": self.sqrt_covered,
        }


@dataclass
class ProgressiveRun:
    case_id: str
    n: int
    label: Label
    traces: list[RungTrace]
    stopped_at: str
    stop_reason: str
    escalations: int
    invocations: int
    work: int
    strikes: dict[str, int]


@dataclass(frozen=True)
class FusedWorkflow:
    strategy: str
    predicate: AdequacyPredicate
    max_escalations: int
    max_invocations: int
    advance: bool

    def spec(self) -> dict:
        return {
            "kind": "fused-workflow",
            "strategy": self.strategy,
            "sources": [
                {
                    "id": RUNG_IDS[i],
                    "rung": i,
                    "work_units_when_invoked": RUNG_COSTS[i],
                    "source_anchor": f"wfa-0106:{RUNG_IDS[i]}",
                }
                for i in range(4)
            ],
            "adequacy_predicate": self.predicate.spec(),
            "max_escalations": self.max_escalations,
            "max_invocations": self.max_invocations,
            "rungs": list(RUNG_IDS),
        }


def compose_progressive(
    predicate: AdequacyPredicate | None = None,
    max_escalations: int = MAX_ESCALATIONS,
    max_invocations: int = MAX_INVOCATIONS,
    advance: bool = True,
) -> FusedWorkflow:
    return FusedWorkflow(
        strategy="progressive",
        predicate=predicate or certified_predicate(),
        max_escalations=max_escalations,
        max_invocations=max_invocations,
        advance=advance,
    )


def run_progressive(
    n: int,
    workflow: FusedWorkflow,
    ledger: BudgetLedger,
    case_id: str | None = None,
) -> ProgressiveRun:
    cid = case_id or f"n={n}"
    rung = 0
    invocations = 0
    escalations = 0
    traces: list[RungTrace] = []
    strikes: dict[str, int] = {}
    last: RungResult | None = None
    while True:
        if invocations >= workflow.max_invocations:
            return ProgressiveRun(
                case_id=cid,
                n=n,
                label=last.label if last else "COMPOSITE",
                traces=traces,
                stopped_at=last.source_id if last else RUNG_IDS[0],
                stop_reason="escalation-bound",
                escalations=escalations,
                invocations=invocations,
                work=sum(t.cost for t in traces),
                strikes=strikes,
            )
        last = RUNNERS[rung](n, cid)
        ledger.charge(
            cid,
            last.source_id,
            last.work_units,
            f"rung-{last.rung}",
            rung=last.rung,
            invocation=invocations,
        )
        invocations += 1
        feat = last.features
        fp = fingerprint(feat)
        adequate = workflow.predicate.holds(feat)
        why = (
            f"stopped:{feat.certification_rule}"
            if adequate
            else f"escalated:{feat.certification_rule}"
        )
        traces.append(
            RungTrace(
                rung=last.rung,
                rung_id=last.source_id,
                cost=last.work_units,
                adequate=adequate,
                why=why,
                label=last.label,
                certification_rule=feat.certification_rule,
                fingerprint=fp,
                factor_found=feat.factor_found,
                sqrt_covered=feat.sqrt_covered,
            )
        )
        if adequate:
            return ProgressiveRun(
                case_id=cid,
                n=n,
                label=last.label,
                traces=traces,
                stopped_at=last.source_id,
                stop_reason="adequate",
                escalations=escalations,
                invocations=invocations,
                work=sum(t.cost for t in traces),
                strikes=strikes,
            )
        strikes[fp] = strikes.get(fp, 0) + 1
        # AGENTS.md 4b: two strikes on the same fingerprint then pivot.
        # A working ladder pivots on the first miss. A stuck scheduler
        # (advance=False) retries the same rung until the invocation bound.
        if not workflow.advance:
            continue
        if escalations >= workflow.max_escalations or rung >= 3:
            return ProgressiveRun(
                case_id=cid,
                n=n,
                label=last.label,
                traces=traces,
                stopped_at=last.source_id,
                stop_reason="escalation-bound",
                escalations=escalations,
                invocations=invocations,
                work=sum(t.cost for t in traces),
                strikes=strikes,
            )
        rung += 1
        escalations += 1


def run_top_rung(n: int, case_id: str) -> RungResult:
    return run_l3(n, case_id)


def corpus() -> tuple[dict, ...]:
    rows: list[dict] = []
    for n in L0_COMPOSITES:
        rows.append({"n": n, "band": "L0-composite", "case_id": f"n={n}"})
    for n in L0_PRIMES:
        rows.append({"n": n, "band": "L0-prime", "case_id": f"n={n}"})
    for n in L1_CASES:
        rows.append({"n": n, "band": "L1", "case_id": f"n={n}"})
    for n in L2_CASES:
        rows.append({"n": n, "band": "L2", "case_id": f"n={n}"})
    for n in L3_CASES:
        rows.append({"n": n, "band": "L3", "case_id": f"n={n}"})
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
    progressive_work: int
    expensive_work: int
    reduction_ratio: float
    escalations: int
    always_escalates: bool
    per_case: list[dict] = field(default_factory=list)
    traces: list[dict] = field(default_factory=list)
    progressive_ledger: list[dict] = field(default_factory=list)
    expensive_ledger: list[dict] = field(default_factory=list)
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
                "max_mismatch_rate": MAX_MISMATCH_RATE,
                "per_case_deltas": self.per_case,
            },
            "work": {
                "progressive_ledger_total": self.progressive_work,
                "expensive_only_ledger_total": self.expensive_work,
                "reduction_ratio": self.reduction_ratio,
                "min_work_reduction_ratio": MIN_REDUCTION,
                "source": "budget_ledger_sum",
                "estimated": False,
                "escalations": self.escalations,
                "always_escalates": self.always_escalates,
            },
            "workflow": self.workflow,
            "traces": self.traces,
            "progressive_ledger": self.progressive_ledger,
            "expensive_ledger": self.expensive_ledger,
        }


def evaluate(
    workflow: FusedWorkflow,
    cases: Sequence[dict] | None = None,
) -> AcceptanceReport:
    cases = tuple(cases) if cases is not None else corpus()
    if len(cases) < MIN_CASES:
        return AcceptanceReport(
            verdict="INSUFFICIENT-EVIDENCE",
            reason=f"n_cases={len(cases)} below MIN_CASES={MIN_CASES}",
            n_cases=len(cases),
            mismatches=0,
            mismatch_rate=0.0,
            progressive_work=0,
            expensive_work=0,
            reduction_ratio=0.0,
            escalations=0,
            always_escalates=False,
            workflow=workflow.spec(),
        )
    prog_ledger = BudgetLedger()
    exp_ledger = BudgetLedger()
    per_case: list[dict] = []
    traces: list[dict] = []
    mismatches = 0
    escalations = 0
    full_ladder = 0
    for row in cases:
        n = int(row["n"])
        cid = str(row["case_id"])
        prog = run_progressive(n, workflow, prog_ledger, cid)
        exp = run_top_rung(n, cid)
        exp_ledger.charge(
            cid,
            exp.source_id,
            exp.work_units,
            "always-top-rung",
            rung=3,
            invocation=0,
        )
        match = prog.label == exp.label
        if not match:
            mismatches += 1
        if prog.escalations:
            escalations += prog.escalations
        if len(prog.traces) >= 4:
            full_ladder += 1
        per_case.append(
            {
                "case_id": cid,
                "n": n,
                "band": row.get("band"),
                "progressive_label": prog.label,
                "expensive_label": exp.label,
                "match": match,
                "escalations": prog.escalations,
                "invocations": prog.invocations,
                "stopped_at": prog.stopped_at,
                "stop_reason": prog.stop_reason,
                "progressive_work": prog.work,
                "expensive_rung_work": exp.work_units,
            }
        )
        traces.append(
            {
                "case_id": cid,
                "n": n,
                "stopped_at": prog.stopped_at,
                "stop_reason": prog.stop_reason,
                "escalations": prog.escalations,
                "rungs_run": [t.as_dict() for t in prog.traces],
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
    reduction = 0.0 if e_work <= 0 else (e_work - p_work) / e_work
    p_sum = sum(e.work_units for e in prog_ledger.entries())
    e_sum = sum(e.work_units for e in exp_ledger.entries())
    always_escalates = full_ladder == n_cases
    if p_sum != p_work or e_sum != e_work:
        verdict, reason = "REJECT", "ledger-summary-mismatch"
    elif mismatch_rate > MAX_MISMATCH_RATE:
        verdict, reason = "REJECT", "correctness-delta-exceeds-tolerance"
    elif always_escalates:
        verdict, reason = (
            "REJECT",
            "always-escalates-is-expensive-top-rung-plus-steps",
        )
    elif reduction < MIN_REDUCTION:
        verdict, reason = "REJECT", "work-reduction-below-declared-minimum"
    else:
        verdict, reason = (
            "PASS",
            "equal-outcome-and-measured-work-reduction-vs-always-top-rung",
        )
    return AcceptanceReport(
        verdict=verdict,
        reason=reason,
        n_cases=n_cases,
        mismatches=mismatches,
        mismatch_rate=mismatch_rate,
        progressive_work=p_work,
        expensive_work=e_work,
        reduction_ratio=reduction,
        escalations=escalations,
        always_escalates=always_escalates,
        per_case=per_case,
        traces=traces,
        progressive_ledger=prog_ledger.as_dicts(),
        expensive_ledger=exp_ledger.as_dicts(),
        workflow=workflow.spec(),
    )


def bound_stops_loop(n: int = LOOP_INPUT_N) -> dict:
    """Both-states: stuck never-adequate runner with and without a tight bound."""
    wf_bound = compose_progressive(
        never_adequate_predicate(),
        max_escalations=MAX_ESCALATIONS,
        max_invocations=MAX_INVOCATIONS,
        advance=False,
    )
    bounded = run_progressive(n, wf_bound, BudgetLedger(), f"loop-n={n}")
    wf_open = compose_progressive(
        never_adequate_predicate(),
        max_escalations=10**6,
        max_invocations=LOOP_SAFETY,
        advance=False,
    )
    opened = run_progressive(n, wf_open, BudgetLedger(), f"loop-open-n={n}")
    return {
        "n": n,
        "bounded_invocations": bounded.invocations,
        "bounded_stop_reason": bounded.stop_reason,
        "bounded_strikes": bounded.strikes,
        "unbounded_invocations": opened.invocations,
        "unbounded_stop_reason": opened.stop_reason,
        "would_loop": opened.invocations == LOOP_SAFETY,
        "bound_enforced": (
            bounded.stop_reason == "escalation-bound"
            and bounded.invocations == MAX_INVOCATIONS
            and opened.invocations == LOOP_SAFETY
        ),
    }


def planted_controls() -> dict:
    good = evaluate(compose_progressive())
    never_esc = evaluate(compose_progressive(always_adequate_predicate()))
    always_esc = evaluate(
        compose_progressive(
            never_adequate_predicate(),
            max_escalations=MAX_ESCALATIONS,
            max_invocations=MAX_INVOCATIONS,
            advance=True,
        )
    )
    return {
        "good_verdict": good.verdict,
        "never_escalate_verdict": never_esc.verdict,
        "never_escalate_mismatches": never_esc.mismatches,
        "never_escalate_reason": never_esc.reason,
        "always_escalate_verdict": always_esc.verdict,
        "always_escalate_reason": always_esc.reason,
        "always_escalate_work": always_esc.progressive_work,
        "always_top_work": always_esc.expensive_work,
        "always_escalate_more_expensive": (
            always_esc.progressive_work > always_esc.expensive_work
        ),
        "never_escalate_rejected_for_correctness": (
            never_esc.verdict == "REJECT"
            and "correctness" in never_esc.reason
            and never_esc.mismatches >= 1
        ),
        "good_pass": good.verdict == "PASS",
    }


def fused_ir() -> dict:
    nodes = []
    for i, rid in enumerate(RUNG_IDS):
        nodes.append(
            {
                "id": rid,
                "kind": "source-rung",
                "rung": i,
                "cost": RUNG_COSTS[i],
                "source_anchor": f"wfa-0106:{rid}",
                "runtime_entrypoint": None,
            }
        )
        if i < 3:
            nodes.append(
                {
                    "id": f"gate-adequacy-{rid}",
                    "kind": "adequacy-gate",
                    "rung": i,
                    "predicate": "certified-factor-or-sqrt-cover",
                    "on_fail": "escalate",
                    "source_anchor": f"wfa-0106:gate-{rid}",
                    "runtime_entrypoint": None,
                }
            )
    return {
        "kind": "WorkflowIR",
        "id": "wf.progressive.wfa-0106",
        "strategy": "progressive",
        "source_anchor": "wfa-0106:fused",
        "runtime_entrypoint": None,
        "max_escalations": MAX_ESCALATIONS,
        "max_invocations": MAX_INVOCATIONS,
        "nodes": nodes,
        "lossy_field_ledger": [],
    }
