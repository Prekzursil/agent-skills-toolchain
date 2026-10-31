#!/usr/bin/env python3
"""Catalog tests for IMP-0004 secret gate."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

from canary import leak_in, synthetic_body, synthetic_github_pat  # noqa: E402
from secret_gate import build_report, write_report  # noqa: E402


class SecretGateTests(unittest.TestCase):
    def test_planted_token_blocked_and_redacted(self) -> None:
        token = synthetic_github_pat()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "payload").mkdir()
            (root / "payload" / "config.env").write_text(
                f"GITHUB_TOKEN={token}\n", encoding="utf-8"
            )
            report = build_report(root)
            path = Path(td) / "report.json"
            write_report(report, path)
            text = path.read_text(encoding="utf-8")
            self.assertTrue(report["blocked"])
            self.assertEqual(report["exit_code"], 1)
            self.assertGreaterEqual(report["detectors"]["gitleaks_rules"]["findings_count"], 1)
            self.assertGreaterEqual(report["detectors"]["shannon_entropy"]["findings_count"], 1)
            self.assertFalse(leak_in(text))
            self.assertNotIn(synthetic_body(), text)
            self.assertIn("ghp_", text)

    def test_clean_bundle_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "payload").mkdir()
            (root / "payload" / "plugin.json").write_text(
                '{"name":"demo","version":"1.0.0"}\n', encoding="utf-8"
            )
            report = build_report(root)
            self.assertFalse(report["blocked"])
            self.assertEqual(report["exit_code"], 0)
            self.assertEqual(report["findings"], [])


if __name__ == "__main__":
    unittest.main()
