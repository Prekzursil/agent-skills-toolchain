"""Cancelling-pair BEFORE state.

Visible counts: passed=2, failed=2, skipped=1.
test_beta is passing; test_gamma is failing.
"""
from __future__ import annotations

import unittest


class OutcomeSet(unittest.TestCase):
    def test_alpha_stable_pass(self) -> None:
        self.assertEqual(1, 1)

    def test_beta_was_pass(self) -> None:
        self.assertTrue(True)

    def test_gamma_was_fail(self) -> None:
        self.assertEqual(1, 0)

    def test_delta_stable_fail(self) -> None:
        self.assertFalse(True)

    def test_epsilon_stable_skip(self) -> None:
        self.skipTest("platform-conditional skip stays a skip")
