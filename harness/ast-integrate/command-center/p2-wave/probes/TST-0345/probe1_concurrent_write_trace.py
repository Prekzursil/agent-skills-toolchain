#!/usr/bin/env python3
"""Probe 1: real concurrent workers, write-path map, empty intersection.

Mechanically this is a live multiprocessing run with a barrier, not a
sequential loop and not a re-read of the receipt's stored map.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import isolation as I  # noqa: E402

ART = REPO / "command-center/receipts/TST-0345.json"
SENTINEL = "SUCCESS:TST-0345"


def artifact_error() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    return None


def main() -> int:
    err = artifact_error()
    if err:
        print(f"FAILED:TST-0345-probe1 {err}")
        return 1

    result = I.run_isolated_concurrent(n_workers=4, n_writes=16)
    audit = result["audit"]
    wmap = result["write_path_map"]

    if len(wmap) != 4:
        print(f"FAILED:TST-0345-probe1 worker count {len(wmap)}")
        return 1
    if not audit["distinct_pids"]:
        print("FAILED:TST-0345-probe1 workers did not run as distinct processes")
        return 1
    if not audit["overlapped"]:
        print(
            "FAILED:TST-0345-probe1 write windows did not overlap "
            f"t0_max={audit['t0_ns_max']} t1_min={audit['t1_ns_min']}"
        )
        return 1
    if audit["shared_temp_roots"]:
        print("FAILED:TST-0345-probe1 workers shared a temp root")
        return 1
    if audit["shared_worktrees"]:
        print("FAILED:TST-0345-probe1 workers shared a worktree")
        return 1
    if audit["shared_git_dirs"] or audit["shared_indexes"]:
        print("FAILED:TST-0345-probe1 workers shared git dir or index")
        return 1
    if not audit["write_path_intersection_empty"]:
        print(
            "FAILED:TST-0345-probe1 write-path intersection "
            f"{audit['write_path_intersection']}"
        )
        return 1
    if audit["escapes"]:
        print(f"FAILED:TST-0345-probe1 writes escaped temp root {audit['escapes']}")
        return 1
    if not audit["isolated"]:
        print("FAILED:TST-0345-probe1 audit.isolated is false")
        return 1
    for wid, row in wmap.items():
        if row["write_count"] != 16:
            print(f"FAILED:TST-0345-probe1 {wid} write_count={row['write_count']}")
            return 1
        root = row["temp_root"].rstrip("/") + "/"
        wt = row["worktree"].rstrip("/") + "/"
        if not row["worktree"].startswith(root):
            print(f"FAILED:TST-0345-probe1 {wid} worktree not under temp_root")
            return 1
        for path in row["writes"]:
            if not path.startswith(wt):
                print(f"FAILED:TST-0345-probe1 {wid} write outside worktree {path}")
                return 1

    summary = {
        "pass": True,
        "probe": "probe1-concurrent-write-trace",
        "unit_id": "TST-0345",
        "n_workers": 4,
        "n_writes": 16,
        "distinct_pids": audit["distinct_pids"],
        "overlapped": audit["overlapped"],
        "write_path_intersection_empty": True,
        "shared_temp_roots": False,
        "shared_worktrees": False,
        "isolated": True,
        "write_counts": {k: v["write_count"] for k, v in wmap.items()},
        "temp_roots": {k: v["temp_root"] for k, v in wmap.items()},
        "worktrees": {k: v["worktree"] for k, v in wmap.items()},
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"workers=4 pids_distinct=True overlapped=True intersection=empty "
        f"isolated={audit['isolated']}"
    )
    print("SUCCESS:TST-0345-probe1 concurrent write trace empty intersection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
