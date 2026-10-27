#!/usr/bin/env python3
"""IMP-0038 probe1: reconciliation scenario over the planted control trees.

Contract: planted repo-only AND live-only capabilities are both reported (the
live-only direction is MEASURED, non-empty, not assumed empty); shared
capabilities land in in_both; in_sync is refused while any gap exists; the
reconciler never auto-deploys and never mutates the live tree; a missing live
root is measured empty and still refuses in_sync.
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

import registration_fixture as fx  # noqa: E402
import registration_reconciler as rr  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0038-p1-"))
    try:
        checks: dict[str, bool] = {}

        # Complete control trees.
        trees = fx.build_control_trees(tmp / "complete", omit_forgotten_from_repo_manifest=False)
        before = rr.snapshot_tree(trees["live"])
        report = rr.reconcile(trees["repo"], trees["live"])
        after = rr.snapshot_tree(trees["live"])

        repo_ids = set(report["repo_only"])
        live_ids = set(report["live_only"])
        checks["repo_only_planted"] = all(
            fx.PLANTED[k] in repo_ids
            for k in ("repo_only_skill", "repo_only_hook", "repo_only_rule", "repo_only_command")
        )
        checks["live_only_planted"] = all(
            fx.PLANTED[k] in live_ids
            for k in ("live_only_skill", "live_only_hook", "live_only_rule", "live_only_command")
        )
        checks["shared_in_both"] = all(
            fx.PLANTED[k] in set(report["in_both"])
            for k in ("shared_skill", "shared_hook", "shared_rule", "shared_command")
        )
        checks["in_sync_refused"] = report["in_sync"] is False
        checks["no_auto_deploy"] = report["auto_deploy"] is False and report["writes"] == []
        checks["live_tree_untouched"] = before == after
        checks["live_only_measured"] = (
            report["live_only_measured"] is True and report["live_only_assumed_empty"] is False
        )

        # Gap control: skill omitted from the repo manifest.
        gap = fx.build_control_trees(tmp / "gap", omit_forgotten_from_repo_manifest=True)
        gap_report = rr.reconcile(gap["repo"], gap["live"])
        checks["gap_sets_disagree"] = gap_report["sets_agree"] is False
        checks["forgotten_on_disk"] = (
            fx.PLANTED["forgotten_skill"] in rr.flatten(rr.enumerate_fs(gap["repo"]))
        )
        checks["forgotten_not_in_manifest"] = (
            fx.PLANTED["forgotten_skill"]
            not in rr.flatten(rr.enumerate_manifest(gap["repo"]))
        )

        # Absent live root: measured empty, in_sync still refused.
        absent_report = rr.reconcile(trees["repo"], tmp / "does-not-exist")
        checks["absent_live_measured_empty"] = absent_report["live_only"] == []
        checks["absent_live_refuses_in_sync"] = absent_report["in_sync"] is False
        checks["absent_live_repo_only_present"] = bool(absent_report["repo_only"])

        out = {
            "unit_id": "IMP-0038",
            "probe": "probe1-scenario",
            "counts": report["counts"],
            "checks": checks,
            "pass": all(checks.values()),
        }
        print(json.dumps(out, sort_keys=True))
        print(
            "repo_only="
            + json.dumps(sorted(x for x in report["repo_only"]))
            + " live_only="
            + json.dumps(sorted(x for x in report["live_only"]))
        )
        if not all(checks.values()):
            print(f"FAILED:IMP-0038-probe1 {[k for k, v in checks.items() if not v]}")
            return 1
        print("SUCCESS:IMP-0038-probe1 both directions planted, in_sync refused")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
