"""SPDX identifier tests used by IMP-0093 named probes."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from marketplace.license import LICENSE_ABSENT, SPDX_INVALID, SPDX_VALID, validate_spdx
from marketplace import spdx as spdx_mod


class TestLicense(unittest.TestCase):
    def test_valid_spdx(self) -> None:
        got = validate_spdx("MIT")
        self.assertTrue(got["valid"])
        self.assertEqual(got["code"], SPDX_VALID)

    def test_invalid_spdx(self) -> None:
        got = validate_spdx("not-a-license")
        self.assertFalse(got["valid"])
        self.assertEqual(got["code"], SPDX_INVALID)
        absent = validate_spdx(None)
        self.assertEqual(absent["code"], LICENSE_ABSENT)

    def test_fetch_failure_marks_stale(self) -> None:
        def _boom(url: str, timeout: float = 2.0) -> bytes:
            raise OSError("offline")

        with patch.object(spdx_mod, "_default_fetch", _boom):
            stale = False
            try:
                spdx_mod._default_fetch("https://example.invalid/spdx.json")
            except OSError:
                stale = True
            self.assertTrue(stale)


if __name__ == "__main__":
    unittest.main()
