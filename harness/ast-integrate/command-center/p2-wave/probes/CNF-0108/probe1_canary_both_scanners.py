#!/usr/bin/env python3
"""Probe 1: both scanners find the planted canary in history; working-tree-only misses.

Rebuilds an independent tempfile git repository. Does not print the canary body.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_scenario  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0108-history-secret-scan.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0108-probe1 artifact missing")
        return 1
    with tempfile.TemporaryDirectory(prefix="cnf0108-p1-") as tmp:
        run = run_scenario(Path(tmp))
    body = run.pop("_canary_body", "")
    if body and body in json.dumps(run):
        print("FAILED:CNF-0108-probe1 canary body leaked into scenario result")
        return 1
    summary = {
        "probe": "probe1-canary-both-scanners",
        "unit_id": "CNF-0108",
        "pattern_found": run["pattern_found"],
        "entropy_found": run["entropy_found"],
        "both_scanners_found": run["both_scanners_found"],
        "working_tree_only_insufficient": run["working_tree_only_insufficient"],
        "packed_objects_contained_canary_blob": run["packed_objects_contained_canary_blob"],
        "head_working_tree_has_canary_file": run["meta"]["head_working_tree_has_canary_file"],
        "commits_walked": run["history"]["commits_walked"],
        "findings_redacted": len(run["findings"]),
        "pass": run["pass"],
    }
    print(json.dumps(summary, sort_keys=True))
    if not run["pattern_found"]:
        print("FAILED:CNF-0108-probe1 pattern scanner missed planted canary")
        return 1
    if not run["entropy_found"]:
        print("FAILED:CNF-0108-probe1 entropy scanner missed planted canary")
        return 1
    if not run["working_tree_only_insufficient"]:
        print("FAILED:CNF-0108-probe1 working-tree-only incorrectly found canary at HEAD")
        return 1
    if not run["packed_objects_contained_canary_blob"]:
        print("FAILED:CNF-0108-probe1 packed objects did not contain canary blob")
        return 1
    if run["meta"]["head_working_tree_has_canary_file"]:
        print("FAILED:CNF-0108-probe1 canary file still in HEAD working tree")
        return 1
    if not run["pass"]:
        print("FAILED:CNF-0108-probe1 scenario pass=false")
        return 1
    print("SUCCESS:CNF-0108-probe1 both scanners found planted canary in history")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
