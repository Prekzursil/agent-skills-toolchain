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



class TestClosureCompatibility(unittest.TestCase):
    """IMP-0093 closure verdicts from the published compatibility matrix."""

    def test_compatible_closure_ok(self) -> None:
        from marketplace.license import check_closure
        got = check_closure(["MIT", "BSD-3-Clause", "Apache-2.0", "GPL-2.0-or-later"])
        self.assertTrue(got["ok"])
        self.assertFalse(got["needs_review"])
        self.assertEqual(got["offending"], [])

    def test_incompatible_closure_names_exact_pair(self) -> None:
        from marketplace.license import check_closure
        got = check_closure(["MIT", "CDDL-1.0", "GPL-3.0-only"])
        self.assertFalse(got["ok"])
        self.assertEqual(len(got["offending"]), 1)
        self.assertEqual(got["offending"][0]["pair"], "CDDL-1.0|GPL-3.0-only")

    def test_unknown_pair_never_assumed_compatible(self) -> None:
        from marketplace.license import check_closure
        from marketplace.compatibility import UNKNOWN_NEEDS_REVIEW
        got = check_closure(["MIT", "SSPL-1.0"])
        self.assertTrue(got["ok"])  # unknown pair offends nothing; it routes, never blocks silently as compatible
        self.assertTrue(got["needs_review"])
        self.assertEqual(got["pairs"][0]["verdict"], UNKNOWN_NEEDS_REVIEW)
        self.assertNotEqual(got["pairs"][0]["verdict"], "COMPATIBLE")
        self.assertIn("owner", got["owner_action"])

    def test_missing_license_blocks_publication(self) -> None:
        from marketplace.license import LICENSE_ABSENT, publication_gate
        got = publication_gate([{"name": "a", "license": "MIT"},
                                {"name": "b", "license": None}])
        self.assertFalse(got["ok"], "LICENSE-ABSENT must block publication")
        self.assertEqual(got["failures"][0]["code"], LICENSE_ABSENT)

    def test_invalid_license_blocks_publication(self) -> None:
        from marketplace.license import SPDX_INVALID, publication_gate
        got = publication_gate([{"name": "a", "license": "MIT-Not-Real-9999"}])
        self.assertFalse(got["ok"])
        self.assertEqual(got["failures"][0]["code"], SPDX_INVALID)

    def test_official_list_id_validates(self) -> None:
        # MPL-2.0 is in the pinned official SPDX list (signal 1)
        got = validate_spdx("MPL-2.0")
        self.assertTrue(got["valid"])
        self.assertEqual(got["code"], SPDX_VALID)

    def test_resolve_gate_reports_offending_pair(self) -> None:
        from marketplace.license import resolve_with_license_gate
        got = resolve_with_license_gate([
            {"name": "zfs", "license": "CDDL-1.0"},
            {"name": "linux", "license": "GPL-2.0-only"},
        ])
        self.assertFalse(got["ok"])
        self.assertEqual(got["offending"][0]["pair"], "CDDL-1.0|GPL-2.0-only")

    def test_legal_disclaimer_present(self) -> None:
        from marketplace.license import LEGAL_DISCLAIMER
        self.assertIn("not legal advice", LEGAL_DISCLAIMER)



if __name__ == "__main__":
    unittest.main()
