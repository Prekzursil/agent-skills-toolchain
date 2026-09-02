"""Resume planner: intact terminal claims skip, truncated claims re-dispatch (TST-0162).

Reconstructed 2026-09-02 (the capture had no copy of this file); the assertions mirror the
unit's two named probes: both-states on an intact vs truncated ledger, and the skip-corrupt
mutant that must turn the control red. Runs under both pytest and ``python -m unittest``.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import claim_resume as CR  # noqa: E402


class ClaimResumeBothStates(unittest.TestCase):
    def test_intact_ledger_skips_everything_and_leaves_receipts_alone(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td)
            CR.first_run(ledger)
            out = CR.resume(ledger)
        self.assertEqual(out["plan"]["skip"], list(CR.UNITS))
        self.assertEqual(out["plan"]["redispatch"], [])
        self.assertFalse(out["receipt_dir_changed"])

    def test_truncated_claim_is_redispatched_and_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td)
            CR.first_run(ledger)
            CR.truncate_claim(ledger, CR.TRUNCATE_UNIT)
            self.assertFalse(CR.read_claim(CR.claim_path(ledger, CR.TRUNCATE_UNIT))["parses"])
            out = CR.resume(ledger)
            repaired = CR.read_claim(CR.claim_path(ledger, CR.TRUNCATE_UNIT))
        self.assertEqual(out["plan"]["redispatch"], [CR.TRUNCATE_UNIT])
        self.assertTrue(out["receipt_dir_changed"])
        self.assertTrue(repaired["terminal"])

    def test_missing_claim_counts_as_redispatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td)
            CR.first_run(ledger)
            CR.claim_path(ledger, "U-0003").unlink()
            plan = CR.plan_resume(ledger)
        self.assertIn("U-0003", plan["redispatch"])
        self.assertNotIn("U-0003", plan["skip"])

    def test_skip_corrupt_mutant_silently_skips(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ledger = Path(td)
            CR.first_run(ledger)
            CR.truncate_claim(ledger, CR.TRUNCATE_UNIT)
            out = CR.resume(ledger, skip_corrupt=True)
            still_corrupt = not CR.read_claim(CR.claim_path(ledger, CR.TRUNCATE_UNIT))["parses"]
        self.assertIn(CR.TRUNCATE_UNIT, out["plan"]["skip"])
        self.assertEqual(out["plan"]["redispatch"], [])
        self.assertFalse(out["receipt_dir_changed"])
        self.assertTrue(still_corrupt)

    def test_suite_entry_points_report_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            both = CR.run_both_states(Path(td) / "both")
            mut = CR.run_mutation_truncate(Path(td) / "mut")
        self.assertTrue(both["pass"])
        self.assertTrue(both["both_states"]["intact_claims_skip"])
        self.assertTrue(both["both_states"]["corrupted_claims_redispatch"])
        self.assertTrue(mut["pass"])
        self.assertTrue(mut["both_states"]["honest_truncate_redispatches"])
        self.assertTrue(mut["both_states"]["mutant_silently_skips"])


if __name__ == "__main__":
    unittest.main()
