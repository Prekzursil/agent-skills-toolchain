#!/usr/bin/env python3
"""Probe 2: negative control — skip quorum recompute, sub-quorum wrongly concludes.

Independent of probe 1 and of the author's narrative: re-derives the
conclude/refuse identity from (N, Q, failed) arithmetic, then shows that
``conclude_skipping_quorum_recompute`` accepts a state ``may_conclude``
rejects.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from council.resilience import (  # noqa: E402
    FaultKind,
    conclude_skipping_quorum_recompute,
    crashing_runner,
    healthy_runner,
    may_conclude,
    new_session,
    recompute_quorum,
    refuse_at_failed_count,
    run_round,
)


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0330-probe2 {msg}")
    return 1


def expected_decision(n: int, q: int, failed: int) -> str:
    return "conclude" if (n - failed) >= q else "refuse"


def main() -> int:
    n, q = 5, 4
    boundary = refuse_at_failed_count(n, q)
    if boundary != 2:
        return _fail(f"identity refuse-at {boundary} != 2")

    # Sub-quorum fixture: fail `boundary` seats (healthy = 3 < 4).
    session = new_session(n, required_quorum=q)
    scratch: dict = {}
    runners = {}
    for i, seat in enumerate(session.seats):
        if i < boundary:
            runners[seat.seat_id] = crashing_runner(
                scratch, seat.seat_id, draft=f"{seat.seat_id}-partial"
            )
        else:
            runners[seat.seat_id] = healthy_runner(text=f"{seat.seat_id}-ok")
    run_round(session, runners, timeout_s=0.05, round_id=0, scratch=scratch)
    if session.aborted:
        return _fail("council aborted; isolation failed")

    qstate = recompute_quorum(session)
    real = may_conclude(session)
    skipped = conclude_skipping_quorum_recompute(session)
    want = expected_decision(n, q, failed=boundary)

    if want != "refuse":
        return _fail("fixture is not sub-quorum")
    if real:
        return _fail("may_conclude allowed a sub-quorum council")
    if qstate.decision != "refuse":
        return _fail(f"recompute decision {qstate.decision}")
    if not skipped:
        return _fail("negative control did not wrongly conclude")
    if skipped == real:
        return _fail("skipping recompute did not flip the outcome")

    # Good-state silence: fail 1 seat (healthy=4>=4). Both paths conclude.
    good = new_session(n, required_quorum=q)
    gscratch: dict = {}
    grundners = {
        good.seats[0].seat_id: crashing_runner(
            gscratch, good.seats[0].seat_id, draft="s0-partial"
        )
    }
    for seat in good.seats[1:]:
        grundners[seat.seat_id] = healthy_runner(text=f"{seat.seat_id}-ok")
    run_round(good, grundners, timeout_s=0.05, round_id=0, scratch=gscratch)
    good_real = may_conclude(good)
    good_skip = conclude_skipping_quorum_recompute(good)
    if not good_real:
        return _fail("good-state (failed=1) should still conclude")
    if not good_skip:
        return _fail("skip-recompute should conclude on the original roster")

    shrinking = qstate.shrinking_denominator_would_conclude
    summary = {
        "both_states": {
            "bad_real_refuses": (not real) and qstate.decision == "refuse",
            "bad_skip_wrongly_concludes": skipped is True,
            "good_real_concludes": good_real is True,
            "good_skip_concludes": good_skip is True,
        },
        "pass": True,
        "probe": "probe2-quorum-negative",
        "shrinking_denominator_would_conclude": shrinking,
        "sub_quorum": {
            "failed": boundary,
            "healthy": qstate.healthy_count,
            "real_decision": qstate.decision,
            "required": q,
            "skip_recompute_decision": "conclude" if skipped else "refuse",
        },
        "unit_id": "IMP-0330",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"nc fired_on_bad={skipped and not real} silent_on_good={good_real} "
        f"kind={FaultKind.CRASH.value} shrinking_would_conclude={shrinking}"
    )
    print("SUCCESS:IMP-0330-probe2 skip-recompute wrongly concludes; real path refuses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
