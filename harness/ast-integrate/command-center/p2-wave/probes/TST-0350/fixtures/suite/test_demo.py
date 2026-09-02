"""Four always-green unittest cases used to prove the collection floor.

Deselecting all but test_alpha is the below-minimum run. The full discovery
is the normal run that must stay green.
"""
from __future__ import annotations

import unittest


class FloorDemo(unittest.TestCase):
    def test_alpha(self) -> None:
        self.assertEqual(1 + 1, 2)

    def test_beta(self) -> None:
        self.assertEqual(2 + 2, 4)

    def test_gamma(self) -> None:
        self.assertTrue("floor".islower())

    def test_delta(self) -> None:
        self.assertIsNotNone(self.id())
