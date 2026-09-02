#!/usr/bin/env python3
"""Named probe 1: dry-run rollback, no live writes, two-directional table."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixtures import materialize  # noqa: E402
from host import host_census  # noqa: E402
from rollback import fingerprint_path, plan_rollback  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:CNF-0045-probe1 {msg}")
    return 1


def main() -> int:
    host_before = host_census()
    with tempfile.TemporaryDirectory(prefix="cnf0045-p1-") as tmp:
        spec = materialize(Path(tmp))
        repo = Path(spec["repo_root"])
        live = Path(spec["live_root"])
        live_fp_before = fingerprint_path(live)
        plan = plan_rollback(repo, live, dry_run=True, apply=False)
        live_fp_after = fingerprint_path(live)

    host_after = host_census()
    if plan.get("hard_failure"):
        return _fail(plan.get("error", "hard_failure"))
    if not plan.get("dry_run"):
        return _fail("not dry-run")
    if plan.get("writes_executed") != 0:
        return _fail(f"writes_executed={plan.get('writes_executed')}")
    if not plan.get("live_tree_unchanged") or not plan.get("repo_tree_unchanged"):
        return _fail("fixture tree mutated")
    if live_fp_before != live_fp_after:
        return _fail("live fingerprint changed")
    if host_before != host_after:
        return _fail("host live tree fingerprint changed")
    table = plan["classification_table"]
    if table["union_files"] != spec["expected_union"]:
        return _fail(f"union={table['union_files']} want={spec['expected_union']}")
    if table["identical"] < 1:
        return _fail("no identical control files")
    if table["eol_only"] < 1:
        return _fail("no EOL-only rows (newline translation likely ate CRLF)")
    if table["needs_reconcile"] < 1:
        return _fail("no NEEDS-RECONCILE rows")
    if table["repo_larger"] < 1 or table["live_larger"] < 1:
        return _fail("not two-directional on content-differing files")
    if not plan.get("two_directional_detected_before_write"):
        return _fail("did not detect two-directional divergence before write")
    if plan["naive_would_destroy_count"] < 1:
        return _fail("naive transcript empty; cannot show live-only overwrite risk")
    if not plan["identical_noop_paths"]:
        return _fail("identical files were not classified no-op")
    refused = set(plan["refused_paths"])
    needs = set(plan["needs_reconcile_paths"])
    if not needs or not needs <= refused:
        return _fail("NEEDS-RECONCILE was auto-resolved")

    out = {
        "probe": "probe1-dry-run-divergence",
        "unit_id": "CNF-0045",
        "dry_run": True,
        "writes_executed": 0,
        "live_tree_unchanged": True,
        "host_present_nonempty_trees": host_after["present_nonempty_trees"],
        "union_files": table["union_files"],
        "identical": table["identical"],
        "eol_only": table["eol_only"],
        "content_differing": table["content_differing"],
        "repo_larger": table["repo_larger"],
        "live_larger": table["live_larger"],
        "needs_reconcile": table["needs_reconcile"],
        "naive_would_destroy_count": plan["naive_would_destroy_count"],
        "two_directional_detected_before_write": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "dry_run=True writes=0 union="
        f"{table['union_files']} identical={table['identical']} "
        f"eol_only={table['eol_only']} content_differing={table['content_differing']} "
        f"repo_larger={table['repo_larger']} live_larger={table['live_larger']} "
        f"needs_reconcile={table['needs_reconcile']} "
        f"naive_destroy={plan['naive_would_destroy_count']}"
    )
    print("SUCCESS:CNF-0045-probe1 dry-run two-directional rollback detection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
