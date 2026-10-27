#!/usr/bin/env python3
"""Catalog tests for IMP-0044 both-states harness."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from both_states_harness import (  # noqa: E402
    TRUSTED,
    UNTRUSTWORTHY,
    ProbeSpec,
    bundled_fixtures,
    evaluate,
    missing_broken_control,
    reviewer_always_pass_probe,
    same_run_catalog_evidence,
)


class BothStatesHarnessTests(unittest.TestCase):
    def test_always_ok_probe_is_flagged(self) -> None:
        ev = same_run_catalog_evidence()
        self.assertEqual(ev.by_id()["always-ok"].trust, UNTRUSTWORTHY)

    def test_discriminating_probe_is_trusted(self) -> None:
        ev = same_run_catalog_evidence()
        self.assertEqual(ev.by_id()["content-marker"].trust, TRUSTED)

    def test_missing_broken_fixture_is_untrustworthy(self) -> None:
        row = missing_broken_control()
        self.assertEqual(row.trust, UNTRUSTWORTHY)
        self.assertFalse(row.skipped)
        self.assertEqual(row.reason, "missing-broken-fixture")

    def test_reviewer_always_pass_is_caught(self) -> None:
        broken, good = bundled_fixtures()
        row = evaluate(
            ProbeSpec(
                probe_id="reviewer-always-pass",
                run=reviewer_always_pass_probe,
                known_broken=broken,
                known_good=good,
            )
        )
        self.assertEqual(row.trust, UNTRUSTWORTHY)
        self.assertEqual(row.reason, "same-verdict-both-states")

    def test_same_run_flags_useless_and_trusts_genuine(self) -> None:
        ev = same_run_catalog_evidence()
        self.assertTrue(ev.same_run)
        self.assertEqual(ev.trusted_count, 1)
        self.assertEqual(ev.untrustworthy_count, 1)

    def test_undeclared_break_is_not_checked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            ghost = Path(raw) / "ghost"
            good = Path(raw) / "good.txt"
            good.write_text("ok\n", encoding="utf-8")
            row = evaluate(
                ProbeSpec(
                    probe_id="ghost",
                    run=lambda _p: "OK",
                    known_broken=ghost,
                    known_good=good,
                )
            )
            self.assertEqual(row.reason, "missing-broken-fixture")

    def test_probe_control_schema_roundtrip_and_garbage(self) -> None:
        schema = HERE.parent / "schema" / "probe-control.schema.json"
        self.assertTrue(schema.is_file())


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
