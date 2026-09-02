#!/usr/bin/env python3
"""Probe 2: reserved-device-name and long-path walks must not truncate.

A crashed walker that reports zero looks like a clean tree. The live walker
must visit NUL and a 260+ path, keep walking after them, and fail closed on
an unreadable directory instead of returning an empty success.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from test_discovery.collect import collect_tree  # noqa: E402
from test_discovery.plants import plant_hostile_tree  # noqa: E402
from test_discovery.walker import WalkResult, walk_tree  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0326-probe2 {msg}")
    return 1


def crash_as_zero(root: Path, scandir) -> WalkResult:
    """Mutant: incomplete walk becomes a successful empty tree."""
    try:
        result = walk_tree(root, scandir=scandir)
        if result.errors or not result.complete:
            raise RuntimeError("incomplete-walk")
        return result
    except Exception:  # noqa: BLE001 - the anti-pattern under test
        return WalkResult(root=str(root), complete=True, paths_visited=0)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0326-p2-") as raw:
        info = plant_hostile_tree(Path(raw) / "hostile")
        root = Path(info["root"])
        walk = walk_tree(root)
        if walk.paths_visited <= 0:
            return fail("hostile walk visited zero paths")
        if not walk.complete:
            return fail(f"hostile walk incomplete: {walk.errors}")
        names = {r.relpath.replace("\\", "/") for r in walk.files}
        if "NUL" not in names:
            return fail(f"NUL not visited: {sorted(names)}")
        if not walk.reserved_device_names:
            return fail("reserved_device_names empty")
        if info["long_leaf_len"] < 260 and not walk.long_paths:
            return fail(
                f"long path not recorded leaf_len={info['long_leaf_len']} "
                f"long_paths={walk.long_paths}"
            )
        if not any("test_after_nul.py" in n for n in names):
            return fail("walk truncated before after_nul")
        if not any("test_long_path.py" in n for n in names):
            return fail("walk truncated before long-path leaf")

        collected = collect_tree(root)
        nodeids = collected.nodeids()
        if not any("test_after_nul" in n for n in nodeids):
            return fail(f"after_nul test not collected: {nodeids}")
        if not any("test_long_path" in n for n in nodeids):
            return fail(f"long-path test not collected: {nodeids}")

        boom = root / "BOOM"
        boom.mkdir()
        (boom / "hidden.txt").write_text("unread\n", encoding="utf-8")

        def exploding(path):  # noqa: ANN001
            if Path(path).name == "BOOM":
                raise OSError("planted-unread")
            return os.scandir(path)

        unread = walk_tree(root, scandir=exploding)
        if unread.complete:
            return fail("unreadable dir was reported complete")
        if not unread.errors:
            return fail("unreadable dir produced no error")
        if unread.paths_visited <= 0:
            return fail("unreadable dir collapsed the walk to zero")
        unread_names = {r.relpath.replace("\\", "/") for r in unread.files}
        if "NUL" not in unread_names:
            return fail("fail-closed walk dropped NUL")

        mutant = crash_as_zero(root, exploding)
        if not (mutant.complete and mutant.paths_visited == 0):
            return fail("crash-as-zero mutant did not exhibit the bug")
        if unread.paths_visited == 0 and unread.complete:
            return fail("live walker matched the crash-as-zero mutant")

        payload = {
            "probe": "probe2-walker-hostile",
            "unit_id": "TST-0326",
            "paths_visited": walk.paths_visited,
            "reserved_device_names": walk.reserved_device_names,
            "long_paths": walk.long_paths,
            "long_leaf_len": info["long_leaf_len"],
            "nul_visited": True,
            "after_nul_collected": True,
            "long_path_collected": True,
            "cycle": info["cycle"],
            "symlink_count": len(walk.symlinks),
            "fail_closed": {
                "complete": unread.complete,
                "error_count": len(unread.errors),
                "paths_visited": unread.paths_visited,
            },
            "crash_as_zero_mutant": {
                "complete": mutant.complete,
                "paths_visited": mutant.paths_visited,
            },
            "collected_nodeids": nodeids,
            "pass": True,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"nul=True long_leaf_len={info['long_leaf_len']} "
            f"paths_visited={walk.paths_visited} "
            f"fail_closed_errors={len(unread.errors)} "
            "mutant_zero=True"
        )
        print(
            "SUCCESS:TST-0326-probe2 reserved-name and long-path walked; "
            "unread fail-closed"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
