#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import conformance as C  # noqa: E402
import fixture_tree as F  # noqa: E402


class ConformanceTests(unittest.TestCase):
    def test_good_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            git_dir, tree = F.build_tree(F.good_files(), Path(td))
            report = C.run_conformance(git_dir, tree)
            self.assertEqual(report["verdict"], "PASS")

    def test_each_mutation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            for code, _how, fn in F.MUTATIONS:
                git_dir, tree = F.build_tree(fn(F.good_files()), Path(td) / code)
                report = C.run_conformance(git_dir, tree)
                codes = [v["code"] for v in report["violations"]]
                self.assertEqual(report["verdict"], "FAIL", code)
                self.assertIn(code, codes, codes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
