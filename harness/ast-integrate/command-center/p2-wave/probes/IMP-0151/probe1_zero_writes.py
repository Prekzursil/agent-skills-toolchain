#!/usr/bin/env python3
"""Probe 1: filesystem audit — adapter leaves live trees untouched.

Signals: (1) mtime/size/ino/sha256 snapshot equality before vs after discover();
(2) host ~/.claude and ~/.agents are not created if they were absent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402
import fixtures as F  # noqa: E402

OUT = HERE / "probe1-zero-writes.raw.json"


def _host_existence() -> list[dict]:
    rows = []
    for p in A.host_live_roots():
        rows.append({"path": p.as_posix(), "exists": p.exists(), "is_dir": p.is_dir()})
    return rows


def main() -> int:
    host_before = _host_existence()
    repo, live = F.build_readonly_estate()
    F.make_tree_readonly(live)
    try:
        before_live = A.snapshot_tree(live)
        before_repo = A.snapshot_tree(repo)
        if len(before_live) < 8:
            print("FAILED:IMP-0151-probe1 live fixture too small")
            return 1
        host_snaps_before = {p.as_posix(): A.snapshot_tree(p) for p in A.host_live_roots()}
        report = A.discover(live, repo, protect_host=True)
        after_live = A.snapshot_tree(live)
        after_repo = A.snapshot_tree(repo)
        host_snaps_after = {p.as_posix(): A.snapshot_tree(p) for p in A.host_live_roots()}
    finally:
        F.restore_tree_writable(live)

    host_after = _host_existence()
    live_ok = A.snapshots_equal(before_live, after_live)
    repo_ok = A.snapshots_equal(before_repo, after_repo)
    host_ok = host_snaps_before == host_snaps_after and host_before == host_after
    created_host = [
        b["path"]
        for b, a in zip(host_before, host_after)
        if (not b["exists"]) and a["exists"]
    ]

    doc = {
        "probe": "probe1-zero-writes",
        "unit_id": "IMP-0151",
        "live_files_snapshotted": len(before_live),
        "live_mtime_set_equal": live_ok,
        "repo_mtime_set_equal": repo_ok,
        "host_existence_equal": host_before == host_after,
        "host_created": created_host,
        "host_before": host_before,
        "host_after": host_after,
        "counts": report["counts"],
        "union": report["union"],
        "read_only": report["read_only"],
        "cited_historical_5_of_88": report["cited_historical_5_of_88"],
        "pass": bool(live_ok and repo_ok and host_ok and not created_host),
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"live_equal={live_ok} repo_equal={repo_ok} host_created={created_host} "
        f"files={len(before_live)} union={report['union']} "
        f"repo-only={report['counts']['repo-only']} "
        f"live-only={report['counts']['live-only']}"
    )
    if not doc["pass"]:
        print("FAILED:IMP-0151-probe1 live-tree mutation or host creation")
        return 1
    print("SUCCESS:IMP-0151-probe1 zero live-tree writes (mtime set equality)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
