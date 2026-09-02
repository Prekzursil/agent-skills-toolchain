#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(TOOLS))
from marketplace.permission_analysis import (  # noqa: E402
    NET,
    analyze_catalog_triplet,
)


class PermissionAnalysisTests(unittest.TestCase):
    def test_excessive_fixture(self) -> None:
        excessive = analyze_catalog_triplet()["excessive-kit"]
        self.assertIn("net:connect", excessive.excessive)
        self.assertIn("spawn:python", excessive.excessive)

    def test_undeclared_fixture(self) -> None:
        undeclared = analyze_catalog_triplet()["undeclared-kit"]
        self.assertIn(NET, undeclared.undeclared)
        self.assertNotEqual(undeclared.verdict, "CLEAN")

    def test_exact_match_fixture(self) -> None:
        exact = analyze_catalog_triplet()["exact-kit"]
        self.assertEqual(exact.findings_count, 0)
        self.assertEqual(exact.verdict, "CLEAN")

    def test_detector_control_undeclared_network_blocks_clean(self) -> None:
        undeclared = analyze_catalog_triplet()["undeclared-kit"]
        self.assertIn(NET, undeclared.undeclared)
        self.assertNotEqual(undeclared.verdict, "CLEAN")
        self.assertEqual(
            undeclared.detector_control,
            "undeclared-network-caught-before-clean",
        )

    def test_negative_control_exact_match_zero_findings_same_run(self) -> None:
        reports = analyze_catalog_triplet()
        self.assertEqual(reports["exact-kit"].findings_count, 0)
        self.assertIn(NET, reports["undeclared-kit"].undeclared)


if __name__ == "__main__":
    unittest.main(verbosity=2)
