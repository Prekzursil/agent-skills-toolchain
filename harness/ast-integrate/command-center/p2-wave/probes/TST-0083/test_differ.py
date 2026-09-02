#!/usr/bin/env python3
"""Catalog tests for TST-0083.

test_differ_finds_a_planted_repo_only_skill
test_all_three_directions_are_reported
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from differ import reconcile, route  # noqa: E402
from fixtures import (  # noqa: E402
    DIVERGENT_ID,
    EOL_ID,
    IDENTICAL_ID,
    LIVE_ONLY_ID,
    REPO_ONLY_ID,
    build_planted_pair,
)


class TestSkillDiffer(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="tst0083-")
        roots = build_planted_pair(Path(self._tmp.name))
        self.repo = roots["repo"]
        self.live = roots["live"]
        self.report = reconcile(self.repo, self.live)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_differ_finds_a_planted_repo_only_skill(self) -> None:
        ids = [row["skill_id"] for row in self.report["repo_only"]]
        self.assertIn(REPO_ONLY_ID, ids)
        self.assertNotIn(LIVE_ONLY_ID, ids)
        self.assertGreaterEqual(self.report["counts"]["repo_only"], 1)
        planted = next(r for r in self.report["repo_only"] if r["skill_id"] == REPO_ONLY_ID)
        self.assertIn("SKILL.md", planted["file_list"])
        self.assertEqual(
            route(REPO_ONLY_ID, self.report)["status"],
            "UNAVAILABLE",
        )
        self.assertEqual(route(IDENTICAL_ID, self.report)["status"], "AVAILABLE")

    def test_all_three_directions_are_reported(self) -> None:
        counts = self.report["counts"]
        self.assertGreaterEqual(counts["repo_only"], 1)
        self.assertGreaterEqual(counts["live_only"], 1)
        self.assertGreaterEqual(counts["divergent"], 1)
        repo_ids = [r["skill_id"] for r in self.report["repo_only"]]
        live_ids = [r["skill_id"] for r in self.report["live_only"]]
        div_ids = [r["skill_id"] for r in self.report["divergent"]]
        self.assertEqual(repo_ids, [REPO_ONLY_ID])
        self.assertEqual(live_ids, [LIVE_ONLY_ID])
        self.assertEqual(div_ids, [DIVERGENT_ID])
        self.assertIn(IDENTICAL_ID, self.report["identical"])
        self.assertIn(EOL_ID, self.report["identical"])
        self.assertNotIn(EOL_ID, div_ids)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestSkillDiffer)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        print("FAILED:TST-0083-tests")
        return 1
    print("SUCCESS:TST-0083-tests both catalog tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
