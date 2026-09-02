#!/usr/bin/env python3
"""Unit tests for TST-0290: three-way stuck-run classification and owner packet."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from council.owner_ask import check_packet  # noqa: E402
from council.simulate import FIXED_PID, FROZEN_NS, SEED_A, SEED_B, three_cast_bundle, trace_hash  # noqa: E402
from council.stopping.deadlock import (  # noqa: E402
    ACTION_CONTINUE,
    ACTION_ESCALATE,
    ACTION_OPERATIONAL,
    CAST_NAMES,
    KIND_DEADLOCK,
    KIND_PRODUCTIVE,
    KIND_STALLED,
    PROPOSITION_CUTOVER,
    classify_cast_run,
    load_cast,
    run_cast,
    run_three_way,
)


class ThreeWayTests(unittest.TestCase):
    def test_three_casts_take_three_distinct_actions(self) -> None:
        policy = run_three_way(seed=SEED_A)
        self.assertTrue(policy["ok"], policy.get("mismatches"))
        self.assertTrue(policy["distinct_actions"])
        self.assertFalse(policy["generic_escalation"])
        self.assertEqual(
            policy["actions"], [ACTION_CONTINUE, ACTION_ESCALATE, ACTION_OPERATIONAL]
        )
        self.assertEqual(policy["kinds"], [KIND_PRODUCTIVE, KIND_DEADLOCK, KIND_STALLED])

    def test_deadlock_names_the_proposition_and_a_seat(self) -> None:
        row = classify_cast_run(run_cast("deadlock"), seed=SEED_A)
        self.assertTrue(row["escalated"])
        self.assertEqual(row["proposition_id"], PROPOSITION_CUTOVER)
        self.assertTrue(row.get("seat_id"))

    def test_productive_dissent_is_not_escalated(self) -> None:
        row = classify_cast_run(run_cast("productive"), seed=SEED_A)
        self.assertFalse(row["escalated"])
        self.assertEqual(row["action"], ACTION_CONTINUE)

    def test_stall_is_operational_not_deadlock(self) -> None:
        stalled = classify_cast_run(run_cast("stalled"), seed=SEED_A)
        deadlock = classify_cast_run(run_cast("deadlock"), seed=SEED_A)
        self.assertFalse(stalled["escalated"])
        self.assertNotEqual(stalled["kind"], deadlock["kind"])
        self.assertEqual(stalled["action"], ACTION_OPERATIONAL)

    def test_every_cast_loads(self) -> None:
        for name in CAST_NAMES:
            self.assertTrue(load_cast(name)["seats"])


class TraceDeterminismTests(unittest.TestCase):
    def test_same_seed_same_hash_and_seed_moves_it(self) -> None:
        a = three_cast_bundle(seed=SEED_A, clock_ns=FROZEN_NS, pid=FIXED_PID)
        b = three_cast_bundle(seed=SEED_A, clock_ns=FROZEN_NS, pid=FIXED_PID)
        other = three_cast_bundle(seed=SEED_B, clock_ns=FROZEN_NS, pid=FIXED_PID)
        self.assertEqual(a["trace_hash"], b["trace_hash"])
        self.assertNotEqual(a["trace_hash"], other["trace_hash"])

    def test_clock_and_pid_do_not_leak_into_production_trace(self) -> None:
        a = three_cast_bundle(seed=SEED_A, clock_ns=FROZEN_NS, pid=FIXED_PID)
        wall = three_cast_bundle(seed=SEED_A, clock_ns=FROZEN_NS + 123456, pid=FIXED_PID)
        pid = three_cast_bundle(seed=SEED_A, clock_ns=FROZEN_NS, pid=FIXED_PID + 91)
        self.assertEqual(a["trace_hash"], wall["trace_hash"])
        self.assertEqual(a["trace_hash"], pid["trace_hash"])

    def test_trace_hash_is_independent_recomputation(self) -> None:
        a = three_cast_bundle(seed=SEED_A, clock_ns=FROZEN_NS, pid=FIXED_PID)
        for run in a["runs"]:
            self.assertEqual(trace_hash(run), run["trace_hash"])


class OwnerPacketTests(unittest.TestCase):
    def test_compound_question_is_refused(self) -> None:
        verdict = check_packet(
            {
                "question": "Should we replace the frozen seat, and should we also ratify the split?",
                "recommendation": "replace",
                "strongest_tradeoff": "loses context",
                "default": "replace after 5 rounds",
            }
        )
        self.assertFalse(verdict.get("ok", verdict.get("accepted", False)))


if __name__ == "__main__":
    result = unittest.main(verbosity=1, exit=False).result
    if result.wasSuccessful():
        print(f"SUCCESS:TST-0290-tests ran={result.testsRun}")
        raise SystemExit(0)
    print(f"FAILED:TST-0290-tests failures={len(result.failures)} errors={len(result.errors)}")
    raise SystemExit(1)
