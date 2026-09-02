#!/usr/bin/env python3
"""Probe 2: fail-closed unread accounting and junction-loop termination.

Mechanically different from probe 1: plants unreadable entries and a cycle,
compares the hardened walker to the naive swallow/follow twins, and requires
both states (green complete tree vs red incomplete tree).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from harness_walker.baseline import naive_walk_follow_unlimited, naive_walk_silent_skip
from harness_walker.fixtures import build_hostile_tree
from harness_walker.walker import (
    FsOps,
    IncompleteWalk,
    require_complete,
    result_fingerprint,
    walk_tree,
)

UNIT = "TST-0335"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def deny_basename(name: str) -> FsOps:
    base = FsOps()
    orig = base.lstat

    def lstat(path: str, *, _orig=orig, _name=name):
        if os.path.basename(path) == _name:
            raise PermissionError(13, "Permission denied", path)
        return _orig(path)

    return FsOps(lstat=lstat, follow_stat=base.follow_stat, scandir=base.scandir)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0335-p2-") as raw:
        # Both-states control: a plain complete tree stays complete.
        green_meta = build_hostile_tree(
            Path(raw) / "green",
            include_nul=False,
            include_long=False,
            include_cycle=False,
        )
        green = walk_tree(green_meta["root"])

        # Planted unreadable via the production FsOps seam (root bypasses chmod).
        unread_root = Path(raw) / "unread"
        unread_meta = build_hostile_tree(
            unread_root,
            include_nul=False,
            include_long=False,
            include_cycle=False,
            include_secret=True,
            include_dangling=True,
        )
        planted = walk_tree(unread_meta["root"], ops=deny_basename("secret.txt"))
        dangling_only = walk_tree(unread_meta["root"])  # dangling is a live OS unread

        # Junction cycle vs naive followlinks fuse.
        cycle_root = Path(raw) / "cycle"
        build_hostile_tree(
            cycle_root,
            include_nul=False,
            include_long=False,
            include_plain=True,
        )
        cycled = walk_tree(cycle_root)
        naive_cycle = naive_walk_follow_unlimited(cycle_root, max_steps=30)

        skip = naive_walk_silent_skip(Path(raw) / "green")

        raised_incomplete = False
        try:
            require_complete(planted)
        except IncompleteWalk:
            raised_incomplete = True

        fp_green_a = result_fingerprint(green)
        fp_green_b = result_fingerprint(walk_tree(green_meta["root"]))

        payload = {
            "probe": "probe2-fail-closed-and-loops",
            "unit_id": UNIT,
            "green_complete": green.complete,
            "green_unread": green.unread_count,
            "green_files": green.readable_file_relpaths(),
            "planted_complete": planted.complete,
            "planted_unread_count": planted.unread_count,
            "planted_unread_rels": [u["relpath"] for u in planted.unread],
            "dangling_complete": dangling_only.complete,
            "dangling_unread_count": dangling_only.unread_count,
            "dangling_unread_rels": [u["relpath"] for u in dangling_only.unread],
            "require_complete_raised": raised_incomplete,
            "cycle_loop_detected": cycled.loop_detected,
            "cycle_loops": cycled.loops,
            "cycle_complete": cycled.complete,
            "cycle_files": cycled.readable_file_relpaths(),
            "naive_follow_hit_cap": naive_cycle["hit_cap"],
            "naive_follow_steps": naive_cycle["steps"],
            "naive_skip_complete": skip["complete"],
            "naive_skip_unread": skip["unread_count"],
            "fingerprints_match": fp_green_a == fp_green_b,
            "fingerprint": fp_green_a,
            "platform": os.name,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"green_complete={green.complete} planted_unread={planted.unread_count} "
            f"dangling_unread={dangling_only.unread_count} "
            f"loop={cycled.loop_detected} naive_cap={naive_cycle['hit_cap']}"
        )

        if not green.complete or green.unread_count != 0:
            return fail("green control tree was not complete")
        if planted.complete or planted.unread_count < 1:
            return fail("planted EACCES was not fail-closed")
        if not any("secret.txt" in r for r in payload["planted_unread_rels"]):
            return fail("secret.txt missing from unread list")
        if "unreadable/secret.txt" in planted.readable_file_relpaths():
            return fail("unreadable secret appeared in the readable file count")
        if dangling_only.complete or dangling_only.unread_count < 1:
            return fail("dangling symlink was silently omitted")
        if not raised_incomplete:
            return fail("require_complete did not raise on unread")
        if not cycled.loop_detected:
            return fail("junction cycle did not set loop_detected")
        if not naive_cycle["hit_cap"]:
            return fail("naive followlinks walk terminated without hitting the cap")
        if skip["unread_count"] != 0 or not skip["complete"]:
            return fail("naive silent-skip twin is not the known-broken complete=True state")
        if fp_green_a != fp_green_b:
            return fail("green fingerprints diverged")

        print(f"SUCCESS:{UNIT}-probe2 fail-closed unread and loop termination")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
