#!/usr/bin/env python3
"""Token-bucket, both-states 429 control, 529 cap, headroom gate."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arrival_scheduler import (  # noqa: E402
    FakeClock,
    FixtureProvider,
    SchedulerInputs,
    TokenBucket,
    dispatch_scheduled,
    headroom_refuses,
    run_529_concurrency_control,
    run_both_states,
    token_bucket_checks,
)


class TokenBucketTests(unittest.TestCase):
    def test_named_checks_pass(self) -> None:
        failed = [n for n, ok, _ in token_bucket_checks() if not ok]
        self.assertEqual(failed, [])

    def test_never_negative_or_above_capacity(self) -> None:
        clock = FakeClock()
        b = TokenBucket(5.0, 0.0, clock, initial=0.0)
        for _ in range(50):
            b.try_consume(1.0)
            self.assertGreaterEqual(b.tokens, 0.0)
        full = TokenBucket(5.0, 1000.0, FakeClock(), initial=5.0)
        full.clock.sleep(100.0)
        self.assertLessEqual(full.tokens, 5.0 + 1e-9)

    def test_oversize_is_atomic(self) -> None:
        b = TokenBucket(8.0, 8.0, FakeClock(), initial=2.0)
        self.assertFalse(b.try_consume(3.0))
        self.assertEqual(b.tokens, 2.0)


class BothStatesTests(unittest.TestCase):
    def test_burst_storm_scheduled_clean(self) -> None:
        cmp = run_both_states()
        self.assertTrue(cmp.ok())
        self.assertGreater(cmp.burst.n_429, 0)
        self.assertEqual(cmp.scheduled.n_429, 0)
        self.assertEqual(cmp.burst.n_units, cmp.scheduled.n_units)
        self.assertFalse(cmp.vacuous)
        self.assertEqual(cmp.load_escalations, 0)


class RetryAndCapTests(unittest.TestCase):
    def test_529_does_not_reduce_concurrency(self) -> None:
        rec = run_529_concurrency_control()
        self.assertTrue(rec["concurrency_unchanged"])
        self.assertTrue(rec["all_succeeded"])
        self.assertGreater(rec["n_529_observed"], 0)
        self.assertEqual(rec["concurrency_cap_before"], rec["concurrency_cap_after"])

    def test_headroom_gate_no_vendor_call(self) -> None:
        rec = headroom_refuses()
        self.assertEqual(rec["n_vendor_calls"], 0)
        self.assertTrue(rec["all_503"])

    def test_retry_after_delta_seconds(self) -> None:
        clock = FakeClock()

        class Once429:
            def __init__(self) -> None:
                self.n = 0
                self.arrivals: list[float] = []

            def call(self, unit_id: str):
                from arrival_scheduler import ProviderResponse

                self.arrivals.append(clock.now())
                self.n += 1
                if self.n == 1:
                    return ProviderResponse(429, "5", unit_id, clock.now())
                return ProviderResponse(200, None, unit_id, clock.now())

        provider = Once429()
        inputs = SchedulerInputs(
            arrival_rate_per_sec=1000.0,
            burst_capacity=1000.0,
            concurrency_cap=8,
            default_backoff_sec=0.25,
        )
        dispatch_scheduled(["u0"], provider, inputs, clock)
        self.assertEqual(provider.arrivals[1] - provider.arrivals[0], 5.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
