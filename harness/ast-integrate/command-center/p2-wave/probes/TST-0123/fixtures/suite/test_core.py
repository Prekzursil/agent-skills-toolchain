"""Fixture suite for TST-0123 set-difference controls.

Two collectible tests. A third id is never defined here so a registry that
names it is a planted registry-only orphan.
"""

from __future__ import annotations

import unittest


class TestCore(unittest.TestCase):
    def test_alpha(self) -> None:
        self.assertEqual(1, 1)

    def test_beta(self) -> None:
        self.assertEqual(2, 2)
