"""Associated tests. The protocol must leave this file byte-identical."""

from __future__ import annotations

import unittest

from app import clamp_non_negative, divide_or_none, tag


class TestApp(unittest.TestCase):
    def test_clamp_negative(self) -> None:
        self.assertEqual(clamp_non_negative(-4), 0)

    def test_clamp_positive(self) -> None:
        self.assertEqual(clamp_non_negative(4), 4)

    def test_tag(self) -> None:
        self.assertEqual(tag(7), "n=7")

    def test_div_zero(self) -> None:
        self.assertIsNone(divide_or_none(3, 0))

    def test_div_ok(self) -> None:
        self.assertEqual(divide_or_none(6, 2), 3.0)


if __name__ == "__main__":
    unittest.main()
