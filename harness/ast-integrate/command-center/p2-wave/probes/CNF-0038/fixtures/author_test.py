"""Author test — the synthesizer must never read this file.

AUTHOR_TEST_UNIQUE_MARKER_CNF0038
"""
from __future__ import annotations

import unittest

from receipt_gate import validate_receipt


class AuthorReceiptTests(unittest.TestCase):
    def test_absent_key_is_not_ok(self):
        result = validate_receipt(
            {
                "verdict": "CONFIRMED",
                "verifier_probe": "author-only-probe-id",
            }
        )
        self.assertFalse(result.get("ok"))


if __name__ == "__main__":
    raise SystemExit(0 if unittest.main(verbosity=2, exit=False).result.wasSuccessful() else 1)
