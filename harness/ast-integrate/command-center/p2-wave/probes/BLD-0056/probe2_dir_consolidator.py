#!/usr/bin/env python3
"""Probe 2: 20480-file list/glob + always-skip consolidator control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    DIR_BUDGET_MS,
    DIR_N,
    PATHOLOGY_BYTES,
    consolidation_control,
    measure_dir_scale,
    ntfs_mounts,
    primary_fs_base,
    second_fs_base,
)

ART = REPO / "command-center" / "receipts" / "BLD-0056.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0056-probe2 {msg}")
    return 1


def main() -> int:
    primary = measure_dir_scale(primary_fs_base(), DIR_N)
    if primary["status"] != "MEASURED":
        return fail(f"primary dir scale {primary}")
    if primary["n"] != DIR_N:
        return fail(f"n={primary['n']} want={DIR_N}")
    if not primary.get("within_budget"):
        return fail(
            f"listdir={primary.get('listdir_ms')} glob={primary.get('glob_ms')} "
            f"over budget {DIR_BUDGET_MS} ms"
        )
    second = measure_dir_scale(second_fs_base(), DIR_N)
    if second["status"] == "MEASURED" and not second.get("within_budget"):
        return fail(f"second filesystem over budget {second}")

    consol = consolidation_control()
    skip = consol["always_skip"]
    compact = consol["compacting"]
    if skip["bytes"] < PATHOLOGY_BYTES:
        return fail(f"always-skip size {skip['bytes']} < {PATHOLOGY_BYTES}")
    if skip["compacts"] != 0:
        return fail("always-skip performed a compact")
    if not skip["detected_as_always_skip"]:
        return fail("detector missed always-skip")
    if compact["detected_as_always_skip"]:
        return fail("detector false-positive on compacting twin")
    if compact["compacts"] < 1:
        return fail("compacting twin never compacted")
    if compact["bytes"] >= PATHOLOGY_BYTES:
        return fail("compacting twin reached pathology size")
    if not consol["detector"]["control_pass"]:
        return fail("control_pass false")

    mounts = ntfs_mounts()
    if mounts:
        print(f"ntfs_measured={mounts!r}")
    else:
        print("ntfs=NOT-CHECKED no NTFS mount on this Linux worktree")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        ds = doc.get("directory_scale") or {}
        if ds.get("n") != DIR_N:
            return fail("receipt directory n mismatch")
        cc = doc.get("consolidation_control") or {}
        if not (cc.get("detector") or {}).get("control_pass"):
            return fail("receipt consolidation control_pass is not true")
        first = (doc.get("first_to_degrade") or {}).get("store_id")
        if first != "consolidation-log":
            return fail(f"receipt first_to_degrade={first}")

    print(
        json.dumps(
            {
                "primary": {
                    "fstype": primary.get("fstype"),
                    "listdir_ms": primary.get("listdir_ms"),
                    "glob_ms": primary.get("glob_ms"),
                    "n": primary.get("n"),
                },
                "second": {
                    "status": second.get("status"),
                    "fstype": second.get("fstype"),
                    "listdir_ms": second.get("listdir_ms"),
                    "glob_ms": second.get("glob_ms"),
                },
                "skip_bytes": skip["bytes"],
                "skip_compacts": skip["compacts"],
                "compact_bytes": compact["bytes"],
                "compact_compacts": compact["compacts"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:BLD-0056-probe2 dir-20480 + always-skip-774kb")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
