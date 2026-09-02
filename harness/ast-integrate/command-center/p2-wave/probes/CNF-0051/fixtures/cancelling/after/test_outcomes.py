"""Cancelling-pair AFTER state.

Visible counts remain passed=2, failed=2, skipped=1.
test_beta flipped pass->fail; test_gamma flipped fail->pass.
Aggregate totals are unchanged; the per-id set difference is not.
"""
from __future__ import annotations

import unittest


class OutcomeSet(unittest.TestCase):
    def test_alpha_stable_pass(self) -> None:
        self.assertEqual(1, 1)

    def test_beta_was_pass(self) -> None:
        self.assertTrue(False)

    def test_gamma_was_fail(self) -> None:
        self.assertEqual(1, 1)

    def test_delta_stable_fail(self) -> None:
        self.assertFalse(True)

    def test_epsilon_stable_skip(self) -> None:
        self.skipTest("platform-conditional skip stays a skip")
