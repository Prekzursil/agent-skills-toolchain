#!/usr/bin/env python3
"""Both-direction planted control for the registration reconciler."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
sys.path.insert(0, str(PLUGIN))

import registration_fixture as fx  # noqa: E402
import registration_reconciler as rr  # noqa: E402


class BothDirectionSets(unittest.TestCase):
    def test_both_direction_sets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="imp0038-") as raw:
            dest = Path(raw) / "complete"
            trees = fx.build_control_trees(dest, omit_forgotten_from_repo_manifest=False)
            before = rr.snapshot_tree(trees["live"])
            report = rr.reconcile(trees["repo"], trees["live"])
            after = rr.snapshot_tree(trees["live"])
            self.assertEqual(before, after)
            self.assertFalse(report["auto_deploy"])
            self.assertFalse(report["in_sync"])
            self.assertTrue(report["live_only_measured"])
            self.assertFalse(report["live_only_assumed_empty"])
            repo_ids = set(report["repo_only"])
            live_ids = set(report["live_only"])
            self.assertIn(fx.PLANTED["repo_only_skill"], repo_ids)
            self.assertIn(fx.PLANTED["live_only_skill"], live_ids)
            self.assertIn(fx.PLANTED["shared_skill"], set(report["in_both"]))
            self.assertNotIn(fx.PLANTED["shared_skill"], repo_ids)
            self.assertNotIn(fx.PLANTED["shared_skill"], live_ids)

    def test_forgotten_manifest_disagrees(self) -> None:
        with tempfile.TemporaryDirectory(prefix="imp0038-gap-") as raw:
            dest = Path(raw) / "gap"
            trees = fx.build_control_trees(dest, omit_forgotten_from_repo_manifest=True)
            report = rr.reconcile(trees["repo"], trees["live"])
            self.assertFalse(report["sets_agree"])
            self.assertIn(fx.PLANTED["forgotten_skill"], rr.flatten(rr.enumerate_fs(trees["repo"])))
            self.assertNotIn(
                fx.PLANTED["forgotten_skill"],
                rr.flatten(rr.enumerate_manifest(trees["repo"])),
            )


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
