"""Shared two-leg resume run used by probe1 and the receipt emitter."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "lib"))
sys.path.insert(0, str(HERE))

from resume_budget import (  # noqa: E402
    AXES,
    ResumeBudgetLedger,
    last_suspend_remaining,
    remainders_equal,
    resume_event_remaining,
)
from scenario import (  # noqa: E402
    CAPS,
    EXPECT_AFTER_BOTH,
    EXPECT_AFTER_LEG1,
    EXPECT_CONSUMED,
    LEG1,
    LEG2,
    RUN_ID,
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0170/probe1_resume_remainder.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0170/probe2_launder_control.py"
)


def two_leg(path: Path, run_id: str = RUN_ID) -> dict[str, Any]:
    ledger = ResumeBudgetLedger(path)
    fresh = ledger.create(run_id, CAPS)
    fresh_full = remainders_equal(fresh["remaining"], CAPS) and remainders_equal(
        fresh["consumed"], {a: 0 for a in AXES}
    )
    after1 = ledger.consume(run_id, LEG1)
    pre = ledger.suspend(run_id)
    ledger_before = ledger.snapshot(run_id)
    post = ledger.resume(run_id)
    ledger_after = ledger.snapshot(run_id)
    after2 = ledger.consume(run_id, LEG2)
    tally = ledger.tally_consumed(run_id)
    events = ledger.events(run_id)
    suspend_rem = last_suspend_remaining(events, run_id)
    resume_rem = resume_event_remaining(events, run_id)
    snapshot_sum = {
        axis: after2["consumed"][axis] + after2["remaining"][axis] for axis in AXES
    }
    tally_plus_remaining = {
        axis: tally[axis] + after2["remaining"][axis] for axis in AXES
    }
    return {
        "fresh": fresh,
        "fresh_full": fresh_full,
        "after_leg1": after1,
        "pre_suspend": pre,
        "ledger_before": ledger_before,
        "post_resume": post,
        "ledger_after": ledger_after,
        "after_leg2": after2,
        "tally": tally,
        "events": events,
        "suspend_event_remaining": suspend_rem,
        "resume_event_remaining": resume_rem,
        "snapshot_sum": snapshot_sum,
        "tally_plus_remaining": tally_plus_remaining,
        "expect_after_leg1": EXPECT_AFTER_LEG1,
        "expect_after_both": EXPECT_AFTER_BOTH,
        "expect_consumed": EXPECT_CONSUMED,
        "caps": CAPS,
    }


def evaluate_two_leg(rep: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "fresh_starts_at_cap": rep["fresh_full"],
        "leg1_remaining_matches_plan": remainders_equal(
            rep["after_leg1"]["remaining"], EXPECT_AFTER_LEG1
        ),
        "suspend_remaining_equals_leg1": remainders_equal(
            rep["pre_suspend"]["remaining"], EXPECT_AFTER_LEG1
        ),
        "resume_remaining_equals_pre_suspend": remainders_equal(
            rep["post_resume"]["remaining"], rep["pre_suspend"]["remaining"]
        ),
        "resume_did_not_reload_caps": not remainders_equal(
            rep["post_resume"]["remaining"], CAPS
        ),
        "signal_a_ledger_before_after_equal": remainders_equal(
            rep["ledger_before"]["remaining"], rep["ledger_after"]["remaining"]
        ),
        "signal_a_event_suspend_equals_resume": remainders_equal(
            rep["suspend_event_remaining"] or {},
            rep["resume_event_remaining"] or {},
        ),
        "leg2_remaining_matches_plan": remainders_equal(
            rep["after_leg2"]["remaining"], EXPECT_AFTER_BOTH
        ),
        "signal_b_tally_equals_snapshot_consumed": remainders_equal(
            rep["tally"], rep["after_leg2"]["consumed"]
        ),
        "signal_b_tally_equals_declared_consumed": remainders_equal(
            rep["tally"], EXPECT_CONSUMED
        ),
        "e2e_tally_plus_remaining_equals_cap": remainders_equal(
            rep["tally_plus_remaining"], CAPS
        ),
        "e2e_snapshot_consumed_plus_remaining_equals_cap": remainders_equal(
            rep["snapshot_sum"], CAPS
        ),
    }
    return {
        "pass": all(checks.values()),
        "checks": checks,
        "failed": [k for k, v in checks.items() if not v],
    }
