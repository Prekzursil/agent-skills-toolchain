#!/usr/bin/env python3
"""Unit tests for TST-0303: TTL expiry, observed-class detection, hermetic never expires."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.classify import classify_calls  # noqa: E402
from bench.expire import cite_as_current, dashboard, gate_accepts  # noqa: E402
from bench.observe import NetworkObserver  # noqa: E402
from bench.oracles import case_by_id, execute_case, oracle_advisory, oracle_hermetic  # noqa: E402
from bench.ttl import load_ttl_table, ttl_for  # noqa: E402

NOW = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)


class TtlTableTests(unittest.TestCase):
    def test_hermetic_never_expires(self) -> None:
        self.assertIsNone(ttl_for("hermetic"))

    def test_advisory_has_finite_ttl(self) -> None:
        ttl = ttl_for("advisory-db")
        self.assertIsNotNone(ttl)
        self.assertGreater(ttl, 0)

    def test_unknown_class_is_live_not_eternal(self) -> None:
        self.assertIsNotNone(ttl_for("something-new"))

    def test_table_has_every_live_class(self) -> None:
        table = load_ttl_table()
        for key in ("hermetic", "advisory-db", "marketplace-index", "model-endpoint"):
            self.assertIn(key, table)


class ObserverTests(unittest.TestCase):
    def test_observer_records_nvd_and_restores_urlopen(self) -> None:
        import urllib.request

        before = urllib.request.urlopen
        with NetworkObserver() as obs:
            oracle_advisory("t")
            self.assertEqual(len(obs.calls), 1)
            self.assertEqual(obs.calls[0]["host"], "services.nvd.nist.gov")
        self.assertIs(urllib.request.urlopen, before)

    def test_hermetic_oracle_makes_no_calls(self) -> None:
        with NetworkObserver() as obs:
            oracle_hermetic("t")
        self.assertEqual(obs.calls, [])
        self.assertEqual(classify_calls(obs.calls), "hermetic")

    def test_loopback_is_not_live(self) -> None:
        calls = [{"url": "http://127.0.0.1:8080/x", "host": "127.0.0.1"}]
        self.assertEqual(classify_calls(calls), "hermetic")


class ObservedClassTests(unittest.TestCase):
    def test_lie_is_classified_by_traffic(self) -> None:
        rec = execute_case(case_by_id("lie-hermetic-hits-nvd"), captured_at=NOW, result_id="lie")
        self.assertEqual(rec.declared_class, "hermetic")
        self.assertEqual(rec.observed_class, "advisory-db")
        self.assertTrue(rec.mismatch)

    def test_true_hermetic_matches(self) -> None:
        rec = execute_case(case_by_id("hermetic-digest"), captured_at=NOW, result_id="h")
        self.assertEqual(rec.observed_class, "hermetic")
        self.assertFalse(rec.mismatch)


class GateTests(unittest.TestCase):
    def test_expired_advisory_is_not_checked(self) -> None:
        ttl = ttl_for("advisory-db")
        old = execute_case(case_by_id("advisory-nvd"), captured_at=NOW - timedelta(seconds=ttl + 1), result_id="old")
        old.verdict = "PASS"
        g = gate_accepts(old, NOW)
        self.assertFalse(g["accepted"])
        self.assertEqual(g["as"], "NOT-CHECKED")
        self.assertEqual(cite_as_current(old, NOW).status, "EXPIRED-NOT-CHECKED")

    def test_fresh_advisory_passes(self) -> None:
        fresh = execute_case(case_by_id("advisory-nvd"), captured_at=NOW, result_id="fresh")
        self.assertTrue(gate_accepts(fresh, NOW)["accepted"])

    def test_ancient_hermetic_still_current(self) -> None:
        rec = execute_case(case_by_id("hermetic-digest"), captured_at=NOW - timedelta(days=3650), result_id="h")
        g = gate_accepts(rec, NOW)
        self.assertTrue(g["accepted"])
        self.assertEqual(g["as"], "PASS")
        self.assertEqual(cite_as_current(rec, NOW).status, "CURRENT")

    def test_dashboard_counts_expired(self) -> None:
        ttl = ttl_for("advisory-db")
        old = execute_case(case_by_id("advisory-nvd"), captured_at=NOW - timedelta(seconds=ttl + 1), result_id="old")
        fresh = execute_case(case_by_id("advisory-nvd"), captured_at=NOW, result_id="fresh")
        dash = dashboard([old, fresh], NOW)
        self.assertEqual(dash["expired_count"], 1)
        self.assertEqual(len(dash["greens"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
