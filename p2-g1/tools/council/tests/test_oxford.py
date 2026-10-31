#!/usr/bin/env python3
"""IMP-0333 unit tests for the Oxford debate engine (standalone, no pytest).

Runs the real engine end-to-end and prints SUCCESS:IMP-0333 tests on green;
any failed check exits non-zero (fail closed).  Covers: sides seated, turn
kinds, loop invariant, rebuttal depth bound, timing audit both-states, the
side-swap / evidence-swap flip-rate experiments and the detector non-vacuity
negative control.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.council.protocol.oxford import (  # noqa: E402
    HIGH_FLIP_FLOOR,
    LOW_FLIP_CEILING,
    DebateConfig,
    EvidenceBoundSpeaker,
    LocalTurnLoop,
    OxfordProtocol,
    SideBoundSpeaker,
    balanced_taste_motion,
    compare_side_vs_evidence,
    decisive_arithmetic_motion,
    evidence_swap_experiment,
    side_swap_experiment,
)

FAILURES: list[str] = []

ASSIGN = {"alice": "proposition", "bob": "opposition"}
CFG = DebateConfig(turn_budget_ms=1000, max_rebuttal_depth=2)


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  ok {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL {name} {detail}")


def main() -> int:
    motion = decisive_arithmetic_motion()

    # 1. Debate run: both sides seated, opening/rebuttal/closing present, loop invariant.
    rec = OxfordProtocol(CFG).run(motion, {
        "alice": EvidenceBoundSpeaker("alice"),
        "bob": EvidenceBoundSpeaker("bob"),
    }, ASSIGN)
    check(
        "sides-seated",
        rec.sides() == {"proposition", "opposition"},
        str(rec.sides()),
    )
    check(
        "turn-kinds",
        {"opening", "rebuttal", "closing"} <= rec.turn_kinds(),
        str(rec.turn_kinds()),
    )
    check(
        "loop-invariant",
        rec.turns_executed == rec.turns_recorded == 8,
        f"executed={rec.turns_executed} recorded={rec.turns_recorded}",
    )

    # 2. Rebuttal depth bound: over-depth refused with the recorded reason.
    proto = OxfordProtocol(CFG)
    extra = proto.submit_rebuttal(rec, {"alice": EvidenceBoundSpeaker("alice")}, "alice", depth=3)
    check(
        "depth-bound-refused",
        extra.refused and extra.refuse_reason == "rebuttal_depth_exceeded",
        f"refused={extra.refused} reason={extra.refuse_reason}",
    )

    # 3. Timing audit both-states: overruns flagged, in-budget silent.
    slow = {
        "alice": EvidenceBoundSpeaker("alice", elapsed_ms=5000),
        "bob": EvidenceBoundSpeaker("bob", elapsed_ms=5000),
    }
    fast = {
        "alice": EvidenceBoundSpeaker("alice", elapsed_ms=10),
        "bob": EvidenceBoundSpeaker("bob", elapsed_ms=10),
    }
    tight = DebateConfig(turn_budget_ms=100, max_rebuttal_depth=1)
    over = OxfordProtocol(tight, LocalTurnLoop()).run(motion, slow, ASSIGN)
    ok_run = OxfordProtocol(tight, LocalTurnLoop()).run(motion, fast, ASSIGN)
    check(
        "timing-overrun-flagged",
        over.timing is not None
        and over.timing.overrun_count == len(over.turns)
        and all(t.timed_out for t in over.turns),
        f"overruns={over.timing.overrun_count if over.timing else None} n={len(over.turns)}",
    )
    check(
        "timing-in-budget-silent",
        ok_run.timing is not None
        and ok_run.timing.overrun_count == 0
        and not any(t.timed_out for t in ok_run.turns),
        f"overruns={ok_run.timing.overrun_count if ok_run.timing else None}",
    )

    # 4. Side-swap: evidence-bound stays low on the decisive motion.
    low = side_swap_experiment(motion, {
        "alice": EvidenceBoundSpeaker("alice"),
        "bob": EvidenceBoundSpeaker("bob"),
    }, ASSIGN, CFG)
    check(
        "side-swap-evidence-bound-low",
        low["evidence_decisive"] and float(low["flip_rate"]) <= LOW_FLIP_CEILING,
        str(low),
    )

    # 5. Detector non-vacuity (negative control): side-bound must flip HIGH everywhere.
    high_dec = side_swap_experiment(motion, {
        "alice": SideBoundSpeaker("alice"),
        "bob": SideBoundSpeaker("bob"),
    }, ASSIGN, CFG)
    high_bal = side_swap_experiment(balanced_taste_motion(), {
        "alice": SideBoundSpeaker("alice"),
        "bob": SideBoundSpeaker("bob"),
    }, ASSIGN, CFG)
    check(
        "side-swap-side-bound-high-decisive",
        float(high_dec["flip_rate"]) >= HIGH_FLIP_FLOOR,
        str(high_dec),
    )
    check(
        "side-swap-side-bound-high-balanced",
        float(high_bal["flip_rate"]) >= HIGH_FLIP_FLOOR,
        str(high_bal),
    )

    # 6. Evidence swap on the decisive motion: evidence-bound flips, side-bound holds.
    ev_flips = evidence_swap_experiment(motion, {
        "alice": EvidenceBoundSpeaker("alice"),
        "bob": EvidenceBoundSpeaker("bob"),
    }, ASSIGN, CFG)
    ev_side_bound = evidence_swap_experiment(motion, {
        "alice": SideBoundSpeaker("alice"),
        "bob": SideBoundSpeaker("bob"),
    }, ASSIGN, CFG)
    check(
        "evidence-swap-evidence-bound-flips",
        float(ev_flips["flip_rate"]) == 1.0,
        str(ev_flips),
    )
    check(
        "evidence-swap-side-bound-holds",
        float(ev_side_bound["flip_rate"]) == 0.0,
        str(ev_side_bound),
    )

    # 7. Compare blocks: the published side-vs-evidence verdicts.
    cmp_dec = compare_side_vs_evidence(motion, {
        "alice": EvidenceBoundSpeaker("alice"),
        "bob": EvidenceBoundSpeaker("bob"),
    }, ASSIGN, CFG)
    cmp_bal = compare_side_vs_evidence(balanced_taste_motion(), {
        "alice": SideBoundSpeaker("alice"),
        "bob": SideBoundSpeaker("bob"),
    }, ASSIGN, CFG)
    check(
        "compare-decisive-evidence-wins",
        cmp_dec["evidence_decisive"]
        and not cmp_dec["side_exceeds_evidence"]
        and cmp_dec["side_assignment_flip_rate"] == 0.0
        and cmp_dec["evidence_flip_rate"] == 1.0,
        str(cmp_dec),
    )
    check(
        "compare-balanced-rhetoric-wins",
        cmp_bal["side_exceeds_evidence"]
        and cmp_bal["side_assignment_flip_rate"] == 1.0,
        str(cmp_bal),
    )

    if FAILURES:
        print(f"FAILED:IMP-0333 tests {len(FAILURES)} failed: {sorted(FAILURES)}")
        return 1
    print("SUCCESS:IMP-0333 tests 12/12 checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
