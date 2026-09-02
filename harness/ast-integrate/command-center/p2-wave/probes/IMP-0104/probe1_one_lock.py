#!/usr/bin/env python3
"""Probe 1: a collection resolves to one lockfile whose member set equals the declared set."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.collections import (  # noqa: E402
    build_demo_index,
    define_collection,
    dumps_lockfile,
    re_toolchain_collection,
)


def main() -> int:
    index = build_demo_index()
    col = re_toolchain_collection()
    declared = {m["name"] for m in col["members"]}
    with tempfile.TemporaryDirectory() as td:
        defined = define_collection(col, index, lock_dir=Path(td))
        locks = list(Path(td).glob("*.lock.json"))
        locked = set(defined.member_names)
        shuffled = dict(col)
        shuffled["members"] = list(reversed(list(col["members"])))
        again = define_collection(shuffled, index)
        payload = {
            "byte_identical_on_member_shuffle": defined.lockfile_bytes == again.lockfile_bytes,
            "declared_members": sorted(declared),
            "lock_bytes_match_dumps": dumps_lockfile(defined.lockfile) == defined.lockfile_bytes,
            "lockfiles_on_disk": len(locks),
            "lockfiles_written": defined.lockfiles_written,
            "locked_members": sorted(locked),
            "member_set_equals_declared": declared == locked,
            "resolved_versions": {
                p["name"]: p["version"] for p in defined.lockfile["packages"]
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if not (
            defined.lockfiles_written == 1
            and len(locks) == 1
            and declared == locked
            and declared == {"binwalk", "ghidra", "radare2"}
            and payload["byte_identical_on_member_shuffle"]
            and payload["lock_bytes_match_dumps"]
        ):
            print("FAILED:IMP-0104-probe1 collection did not resolve to one matching lockfile")
            return 1
        print("SUCCESS:IMP-0104-probe1 one lockfile, member set equals declared set")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
