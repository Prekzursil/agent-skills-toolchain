#!/usr/bin/env python3
"""Probe 2: disk-to-manifest coverage under command-center/ (hashes, not names only)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0036/probe2_disk_to_manifest.py"
)


def main() -> int:
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    snap = E.snapshot()
    planted = snap["planted_control"]
    d2m = snap["disk_to_manifest"]
    man = snap["manifest"]
    git_dir = (E.REPO / ".git").exists()
    slim = {
        "probe": "probe2-disk-to-manifest",
        "unit_id": E.UNIT,
        "command": P2,
        "dot_git_exists": git_dir,
        "manifest_present": man["present"],
        "manifest_entry_count": man["entry_count"],
        "disk_file_count": d2m["disk_file_count"],
        "in_manifest_by_path_count": d2m["in_manifest_by_path_count"],
        "absent_from_manifest_by_path_count": d2m["absent_from_manifest_by_path_count"],
        "same_hash_different_path_count": d2m["same_hash_different_path_count"],
        "merkle_sha256_lf": d2m["merkle_sha256_lf"],
        "absent_sample": d2m["absent_sample"],
        "planted_control": planted,
        "pass": bool(planted["control_pass"]) and d2m["disk_file_count"] > 0,
    }
    print(json.dumps(slim, sort_keys=True))
    if not planted["control_pass"]:
        print("FAILED:AUD-0036-probe2 planted missing/extra detector")
        return 1
    if d2m["disk_file_count"] <= 0:
        print("FAILED:AUD-0036-probe2 walked zero files under command-center/")
        return 1
    if man["present"] is False and d2m["in_manifest_by_path_count"] != 0:
        print("FAILED:AUD-0036-probe2 absent manifest still has path hits")
        return 1
    if man["present"] is False and d2m["absent_from_manifest_by_path_count"] != d2m[
        "disk_file_count"
    ]:
        print("FAILED:AUD-0036-probe2 absent manifest coverage arithmetic")
        return 1
    print(
        "SUCCESS:AUD-0036-probe2 "
        f"disk_files={d2m['disk_file_count']} "
        f"absent_from_manifest={d2m['absent_from_manifest_by_path_count']} "
        f"in_manifest={d2m['in_manifest_by_path_count']} "
        f"merkle={d2m['merkle_sha256_lf'][:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
