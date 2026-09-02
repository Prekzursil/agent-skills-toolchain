"""Tests for tools/marketplace/evidence_lint.py (TST-0315)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from marketplace import evidence_lint as el  # noqa: E402

FIXT = HERE / "fixtures" / "evidence"


class EvidenceLintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.book = el.ResultsLedger.load()

    def lint(self, name: str) -> el.LintDecision:
        return el.lint_listing(el.load_json(FIXT / name), self.book)

    def test_good_listing_accepted_and_trusted(self) -> None:
        d = self.lint("good-listing.json")
        self.assertEqual(d.decision, el.DECISION_ACCEPTED)
        self.assertTrue(d.accepted and d.trusted)
        self.assertEqual(d.resolved_run_id, "run-2026-08-20-alpha")
        self.assertEqual(d.rule_ids, [])

    def test_fabricated_run_rejected(self) -> None:
        d = self.lint("fabricated-run.json")
        self.assertEqual(d.decision, el.DECISION_REJECTED)
        self.assertIn(el.RULE_RUN_UNRESOLVED, d.rule_ids)
        self.assertIsNone(d.resolved_run_id)

    def test_expired_b09_is_stale_not_accepted(self) -> None:
        d = self.lint("expired-b09.json")
        self.assertEqual(d.decision, el.DECISION_STALE)
        self.assertFalse(d.accepted)
        self.assertIn(el.RULE_STALE_B09, d.rule_ids)
        self.assertEqual(d.resolved_run_id, "run-2026-01-01-expired")

    def test_third_party_is_unverified_not_trusted(self) -> None:
        d = self.lint("third-party.json")
        self.assertEqual(d.decision, el.DECISION_UNVERIFIED)
        self.assertFalse(d.trusted)
        self.assertIn(el.RULE_THIRD_PARTY, d.rule_ids)

    def test_unsupported_harness_rejected(self) -> None:
        d = self.lint("unsupported-harness.json")
        self.assertEqual(d.decision, el.DECISION_REJECTED)
        self.assertIn(el.RULE_HARNESS_UNSUPPORTED, d.rule_ids)

    def test_free_text_and_extra_claim_rejected(self) -> None:
        self.assertIn(el.RULE_NOT_A_REFERENCE, self.lint("freetext-evidence.json").rule_ids)
        self.assertIn(el.RULE_ADDITIONAL_PROPERTIES, self.lint("extra-claim.json").rule_ids)

    def test_shipped_schema_closed_planted_schema_holey(self) -> None:
        self.assertTrue(el.evidence_schema_is_closed())
        self.assertEqual(el.inspect_schema_holes(), [])
        holes = el.planted_holey_schema_holes()
        self.assertIn("evidence-type-allows-string", holes)
        self.assertIn("evidence-additionalProperties-not-false", holes)

    def test_lint_path_matches_lint_listing(self) -> None:
        a = el.lint_path(FIXT / "good-listing.json")
        b = self.lint("good-listing.json")
        self.assertEqual(a.to_dict(), b.to_dict())


if __name__ == "__main__":
    unittest.main()
