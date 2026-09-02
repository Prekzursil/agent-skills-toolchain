#!/usr/bin/env python3
"""Probe 1: live rename-rotate exact-match vs offline concat.

Signal (a) is the FollowReader consumed list. Signal (b) is complete
lines of monitor.log.1 + monitor.log concatenated in that order.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0155.json"
SENTINEL = "SUCCESS:TST-0155"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0155-probe1 {msg}")
    return 1


def main() -> int:
    H._wipe_runtime()
    row = H.rotation_between_writes(H.FollowReader)
    printable = {
        "reader": row["reader"],
        "scenario": row["scenario"],
        "monitor_count": row["monitor_count"],
        "offline_count": row["offline_count"],
        "match": row["match"],
        "crashed": row["crashed"],
        "crash_exc": row["crash_exc"],
        "inode_changed": row.get("inode_changed"),
        "rotated_is_old_live": row.get("rotated_is_old_live"),
        "live_inode_before": row.get("live_inode_before"),
        "live_inode_after": row.get("live_inode_after"),
        "rotated_inode": row.get("rotated_inode"),
        "rotations": row["rotations"],
        "first": (row["monitor_lines"] or [None])[0],
        "last": (row["monitor_lines"] or [None])[-1],
        "pass": row["pass"],
    }
    print(json.dumps(printable, sort_keys=True))
    if row["crashed"]:
        return fail(f"reader crashed {row['crash_exc']}")
    if not row["match"]:
        return fail(
            f"monitor_count={row['monitor_count']} "
            f"offline_count={row['offline_count']} lists differ"
        )
    if row["monitor_count"] != H.N1 + H.N2:
        return fail(f"count {row['monitor_count']} != {H.N1 + H.N2}")
    if not row.get("inode_changed"):
        return fail("rotation did not change live inode")
    if not row.get("rotated_is_old_live"):
        return fail("rotated file is not the pre-rotate inode")
    if row["monitor_lines"][: H.N1] != [H.PRE.format(i=i) for i in range(H.N1)]:
        return fail("pre-rotation lines recapped or mutated")
    if row["monitor_lines"][H.N1 :] != [H.POST.format(i=i) for i in range(H.N2)]:
        return fail("post-rotation lines missing or mutated")
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared {doc.get('state')}")
        if SENTINEL not in text:
            return fail("sentinel-absent")
        target = ((doc.get("target_result") or {}).get("between_writes") or {})
        if target and int(target.get("monitor_count") or -1) != row["monitor_count"]:
            return fail("artifact monitor_count disagrees with live re-run")
        if target and int(target.get("offline_count") or -1) != row["offline_count"]:
            return fail("artifact offline_count disagrees with live re-run")
    print(
        "SUCCESS:TST-0155-probe1 rotation exact-match "
        f"monitor={row['monitor_count']} offline={row['offline_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
