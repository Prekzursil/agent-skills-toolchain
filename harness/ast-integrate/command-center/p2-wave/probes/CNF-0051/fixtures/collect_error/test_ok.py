"""One test that collects and passes. Sibling test_syntax.py cannot collect."""
from __future__ import annotations

import unittest


class Ok(unittest.TestCase):
    def test_ok(self) -> None:
        self.assertEqual(2, 2)
